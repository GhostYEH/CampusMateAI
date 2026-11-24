package com.example.campusai.data.classroom.nativeplayer

import com.example.campusai.data.remote.ClassroomApiException
import com.example.campusai.data.remote.MagicClassQuizAttemptRequest
import com.example.campusai.data.remote.MagicClassQuizAttemptResponseDto
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeoutOrNull

enum class NativeQuizSubmitState {
    Draft,
    Submitting,
    Confirmed,
    Failed,
    Unknown,
}

data class NativeQuizUiState(
    val sceneId: String = "",
    val attemptId: String? = null,
    val phase: String = "draft",
    val submitState: NativeQuizSubmitState = NativeQuizSubmitState.Draft,
    val answers: Map<String, NativeAnswer> = emptyMap(),
    val results: Map<String, NativeQuizResult> = emptyMap(),
    val selfChecks: Map<String, Boolean> = emptyMap(),
    val loading: Boolean = false,
    val saving: Boolean = false,
    val error: String? = null,
) {
    /** 只有服务器已确认的提交才展示结果；提交中的本地判分不冒充最终报告。 */
    val showReport: Boolean
        get() = phase == "submitted" || phase == "reviewed" ||
            submitState == NativeQuizSubmitState.Confirmed
    val reviewed: Boolean get() = phase == "reviewed"
}

/**
 * 单个测验场景的读取、草稿、提交和重做协调器。
 *
 * 并发规则：
 * - 所有写入经过同一把互斥锁串行发送，服务端按发送顺序落库；
 * - 每次本地作答递增 [editVersion]，响应回来时只有代次未变才允许回显答案；
 * - 每次重做递增 [round]，重做前发出的旧写入不能改写新一轮状态；
 * - 提交会排在已在途的草稿之后；409 统一回读服务端当前作答。
 *
 * 协调器不依赖 Android API，JVM 测试可用可控延迟的假存储复现 A→B→A 等竞态。
 */
class ClassroomQuizCoordinator(
    private val sceneId: String,
    private val quiz: NativeQuiz,
    /** 整个播放会话共享一把写锁，保证跨场景/跨轮次的草稿也按发送顺序落库。 */
    private val writeMutex: Mutex,
    private val isAccountCurrent: () -> Boolean,
    /** 仅当发起本次提交的播放会话仍然有效时才回调奖励结算。 */
    private val isSessionCurrent: () -> Boolean = { true },
    private val loadAttempt: suspend (sceneId: String) -> Result<MagicClassQuizAttemptResponseDto>,
    private val saveAttempt: suspend (sceneId: String, request: MagicClassQuizAttemptRequest) -> Result<MagicClassQuizAttemptResponseDto>,
    private val scope: CoroutineScope,
    private val onState: (NativeQuizUiState) -> Unit,
    private val onSettled: (correct: Int, total: Int) -> Unit,
    /** 学生主动点击交卷且通过本地校验后触发；用于课堂观察事件计数。 */
    private val onSubmitted: () -> Unit = {},
) {
    private var state = NativeQuizUiState(sceneId = sceneId, loading = true)
    private var editVersion = 0
    private var round = 0
    private var lastNotifyKey: String? = null
    private var loadGeneration = 0
    private var draftDirty = false
    private var startNewOnNextSave = false
    private var closed = false
    private var debounceJob: Job? = null
    private var loadJob: Job? = null
    private var writeJob: Job? = null

    private enum class SubmitOutcome {
        Confirmed,
        Failed,
        Unknown,
        Cancelled,
    }

    private data class PendingSubmit(
        val outcome: CompletableDeferred<SubmitOutcome>,
        val answers: Map<String, NativeAnswer>,
        val attemptId: String?,
        val version: Int,
        val round: Int,
        val startNewAttempt: Boolean,
    )

    private var pendingSubmit: PendingSubmit? = null

    init {
        publish()
    }

    fun load() {
        if (closed) return
        val generation = ++loadGeneration
        update { it.copy(loading = true) }
        loadJob?.cancel()
        loadJob = scope.launch {
            val versionAtStart = editVersion
            val result = loadAttempt(sceneId)
            if (closed || generation != loadGeneration || !isAccountCurrent()) return@launch
            result.onSuccess { dto ->
                val phase = dto.state?.phase ?: "draft"
                val results = decodeResults(dto.state?.results.orEmpty())
                update {
                    it.copy(
                        attemptId = dto.attemptId ?: dto.state?.sessionId ?: it.attemptId,
                        phase = phase,
                        submitState = if (phase == "submitted" || phase == "reviewed") {
                            NativeQuizSubmitState.Confirmed
                        } else {
                            NativeQuizSubmitState.Draft
                        },
                        answers = if (versionAtStart == editVersion) {
                            decodeAnswers(quiz, dto.state?.answers.orEmpty())
                        } else {
                            it.answers
                        },
                        results = results,
                        loading = false,
                        error = null,
                    )
                }
                if (phase == "reviewed" && results.isNotEmpty() && canSettleRewards()) {
                    onSettled(results.values.count { it.correct == true }, results.size)
                }
            }.onFailure { error ->
                if (!closed) update { it.copy(loading = false, error = error.message ?: "测验读取失败") }
            }
        }
    }

    fun setAnswer(questionId: String, answer: NativeAnswer) {
        if (closed || state.loading || state.saving || state.showReport) return
        if (state.submitState == NativeQuizSubmitState.Submitting ||
            state.submitState == NativeQuizSubmitState.Unknown
        ) return
        editVersion++
        draftDirty = true
        update { it.copy(answers = it.answers + (questionId to answer), error = null) }
        scheduleDraft()
    }

    fun setShortAnswerSelfCheck(questionId: String, correct: Boolean) {
        if (closed || state.saving) return
        if (state.submitState == NativeQuizSubmitState.Submitting ||
            state.submitState == NativeQuizSubmitState.Unknown
        ) return
        update { it.copy(selfChecks = it.selfChecks + (questionId to correct)) }
    }

    private fun scheduleDraft(delayMs: Long = 700L) {
        debounceJob?.cancel()
        debounceJob = scope.launch {
            delay(delayMs)
            // 防抖只负责等待；真正写入作为同级任务发送，后续输入不能取消已在途的保存。
            val version = editVersion
            val writeRound = round
            scope.launch { persistDraft(version, writeRound) }
        }
    }

    private suspend fun persistDraft(version: Int, writeRound: Int) {
        writeMutex.withLock {
            if (closed || !isAccountCurrent() || version != editVersion || writeRound != round) return
            val current = state
            if (current.sceneId != sceneId || current.showReport) return
            if (current.submitState == NativeQuizSubmitState.Submitting ||
                current.submitState == NativeQuizSubmitState.Unknown
            ) return
            val request = MagicClassQuizAttemptRequest(
                attemptId = current.attemptId,
                phase = "draft",
                answers = encodeAnswers(quiz, current.answers),
                startNewAttempt = startNewOnNextSave,
            )
            val response = saveAttempt(sceneId, request)
            if (closed || !isAccountCurrent() || writeRound != round) return
            response.onSuccess { dto ->
                if (startNewOnNextSave) startNewOnNextSave = false
                val echoIsFresh = version == editVersion
                if (echoIsFresh) draftDirty = false
                update {
                    it.copy(
                        attemptId = dto.attemptId ?: it.attemptId,
                        answers = if (echoIsFresh) {
                            decodeAnswers(quiz, dto.state?.answers.orEmpty())
                        } else {
                            it.answers
                        },
                        loading = false,
                        error = if (echoIsFresh) null else it.error,
                    )
                }
            }.onFailure { error ->
                if (isAttemptConflict(error)) {
                    draftDirty = false
                    update { it.copy(error = "答题记录已变化，正在重新读取。") }
                    load()
                } else if (version == editVersion && !closed) {
                    update { it.copy(error = error.message ?: "测验草稿保存失败") }
                }
            }
        }
    }

    fun submit() {
        if (closed || state.saving || state.submitState == NativeQuizSubmitState.Submitting) return
        if (state.showReport || state.phase == "reviewed") return
        quiz.issue?.let {
            update { state -> state.copy(error = it) }
            return
        }
        val unanswered = quiz.questions.count { question -> !state.answers[question.id]?.hasValue.orFalse() }
        if (unanswered > 0) {
            update { it.copy(error = "还有 $unanswered 道题未作答") }
            return
        }
        val answers = state.answers
        val results = gradeQuiz(quiz, answers)
        val hasShort = quiz.questions.any { it.isShortAnswer }
        val submitVersion = ++editVersion
        val submitRound = round
        val attemptId = state.attemptId
        val startNew = startNewOnNextSave
        // 同一次作答失败后的原样重试是重复事件；只有改答案或开始新作答才重新计数。
        val notifyKey = "${attemptId.orEmpty()}|$startNew|${answers.hashCode()}"
        if (notifyKey != lastNotifyKey) {
            lastNotifyKey = notifyKey
            onSubmitted()
        }
        val outcome = CompletableDeferred<SubmitOutcome>()
        pendingSubmit = PendingSubmit(
            outcome = outcome,
            answers = answers,
            attemptId = attemptId,
            version = submitVersion,
            round = submitRound,
            startNewAttempt = startNew,
        )
        debounceJob?.cancel()
        // 草稿标记保留到提交确认成功；提交结果不确定时退出仍会尝试落一份草稿。
        draftDirty = true
        update {
            it.copy(
                saving = true,
                phase = "draft",
                submitState = NativeQuizSubmitState.Submitting,
                results = results,
                error = null,
            )
        }
        writeJob?.cancel()
        writeJob = scope.launch {
            try {
                val phase = if (hasShort) "submitted" else "reviewed"
                val response = try {
                    writeMutex.withLock {
                        if (!isAccountCurrent() || submitRound != round || submitVersion != editVersion) {
                            outcome.complete(SubmitOutcome.Cancelled)
                            return@launch
                        }
                        saveAttempt(
                            sceneId,
                            MagicClassQuizAttemptRequest(
                                attemptId = attemptId,
                                phase = phase,
                                answers = encodeAnswers(quiz, answers),
                                results = if (phase == "reviewed") encodeResults(results.values) else emptyList(),
                                startNewAttempt = startNew,
                            ),
                        )
                    }
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (error: Exception) {
                    Result.failure(error)
                }
                if (!isAccountCurrent() || submitRound != round || submitVersion != editVersion) {
                    if (!outcome.isCompleted) outcome.complete(SubmitOutcome.Unknown)
                    return@launch
                }
                response.onSuccess { dto ->
                    startNewOnNextSave = false
                    draftDirty = false
                    pendingSubmit = null
                    update {
                        it.copy(
                            saving = false,
                            phase = phase,
                            submitState = NativeQuizSubmitState.Confirmed,
                            attemptId = dto.attemptId ?: it.attemptId,
                            results = results,
                            error = null,
                        )
                    }
                    if (!outcome.isCompleted) outcome.complete(SubmitOutcome.Confirmed)
                    if (phase == "reviewed" && canSettleRewards()) {
                        onSettled(results.values.count { it.correct == true }, results.size)
                    }
                }.onFailure { error ->
                    if (isAttemptConflict(error)) {
                        draftDirty = false
                        pendingSubmit = null
                        update {
                            it.copy(
                                saving = false,
                                phase = "draft",
                                submitState = NativeQuizSubmitState.Unknown,
                                error = "答题记录已变化，正在重新读取。",
                            )
                        }
                        if (!outcome.isCompleted) outcome.complete(SubmitOutcome.Unknown)
                        load()
                    } else if (isDefinitiveRejection(error)) {
                        draftDirty = true
                        update {
                            it.copy(
                                saving = false,
                                phase = "draft",
                                submitState = NativeQuizSubmitState.Failed,
                                results = results,
                                error = error.message ?: "测验提交失败，答案仍保留在本机",
                            )
                        }
                        if (!outcome.isCompleted) outcome.complete(SubmitOutcome.Failed)
                    } else {
                        draftDirty = true
                        update {
                            it.copy(
                                saving = false,
                                phase = "draft",
                                submitState = NativeQuizSubmitState.Unknown,
                                results = results,
                                error = "提交结果未确认，重新进入课堂会核对服务器记录。",
                            )
                        }
                        if (!outcome.isCompleted) outcome.complete(SubmitOutcome.Unknown)
                    }
                }
            } finally {
                if (!outcome.isCompleted) outcome.complete(SubmitOutcome.Cancelled)
            }
        }
    }

    fun finishReview() {
        if (closed || state.saving) return
        if (state.submitState == NativeQuizSubmitState.Submitting ||
            state.submitState == NativeQuizSubmitState.Unknown
        ) return
        val shorts = quiz.questions.filter { it.isShortAnswer }
        if (shorts.any { state.selfChecks[it.id] == null }) {
            update { it.copy(error = "还有主观题没有完成核对") }
            return
        }
        val updated = state.results.toMutableMap()
        shorts.forEach { question ->
            val correct = state.selfChecks[question.id] == true
            updated[question.id] = NativeQuizResult(
                questionId = question.id,
                correct = correct,
                earned = if (correct) question.points else 0.0,
                comment = "已按参考答案自行核对",
                selfChecked = true,
            )
        }
        val answers = state.answers
        val attemptId = state.attemptId
        val reviewVersion = ++editVersion
        val reviewRound = round
        val reviewPhase = state.phase
        update {
            it.copy(
                saving = true,
                phase = reviewPhase,
                submitState = NativeQuizSubmitState.Submitting,
                results = updated,
                error = null,
            )
        }
        writeJob?.cancel()
        writeJob = scope.launch {
            val response = writeMutex.withLock {
                if (!isAccountCurrent() || reviewRound != round || reviewVersion != editVersion) {
                    return@launch
                }
                saveAttempt(
                    sceneId,
                    MagicClassQuizAttemptRequest(
                        attemptId = attemptId,
                        phase = "reviewed",
                        answers = encodeAnswers(quiz, answers),
                        results = encodeResults(updated.values),
                    ),
                )
            }
            if (!isAccountCurrent() || reviewRound != round) return@launch
            response.onSuccess { dto ->
                draftDirty = false
                update {
                    it.copy(
                        saving = false,
                        phase = "reviewed",
                        submitState = NativeQuizSubmitState.Confirmed,
                        attemptId = dto.attemptId ?: it.attemptId,
                        results = updated,
                        error = null,
                    )
                }
                if (canSettleRewards()) {
                    onSettled(updated.values.count { it.correct == true }, updated.size)
                }
            }.onFailure { error ->
                if (isAttemptConflict(error)) {
                    update {
                        it.copy(
                            saving = false,
                            phase = "submitted",
                            submitState = NativeQuizSubmitState.Unknown,
                            error = "答题记录已变化，正在重新读取。",
                        )
                    }
                    load()
                } else if (isDefinitiveRejection(error)) {
                    update {
                        it.copy(
                            saving = false,
                            phase = reviewPhase,
                            submitState = NativeQuizSubmitState.Failed,
                            results = updated,
                            error = error.message ?: "测验报告保存失败",
                        )
                    }
                } else {
                    update {
                        it.copy(
                            saving = false,
                            phase = reviewPhase,
                            submitState = NativeQuizSubmitState.Unknown,
                            results = updated,
                            error = "报告保存结果未确认，重新进入课堂会核对服务器记录。",
                        )
                    }
                }
            }
        }
    }

    /**
     * 开始新一轮作答。立即在写锁内申请新的根 attempt：
     * 即使请求还没返回，本轮也已用 [round] 与上一轮隔离。
     */
    fun retry() {
        if (closed || state.saving) return
        if (state.submitState == NativeQuizSubmitState.Submitting) return
        debounceJob?.cancel()
        editVersion++
        round++
        draftDirty = true
        startNewOnNextSave = true
        pendingSubmit = null
        update {
            NativeQuizUiState(
                sceneId = sceneId,
                attemptId = it.attemptId,
                phase = "draft",
                loading = false,
            )
        }
        allocateAttempt()
    }

    private fun allocateAttempt() {
        val allocationRound = round
        writeJob?.cancel()
        writeJob = scope.launch {
            val response = writeMutex.withLock {
                if (closed || !isAccountCurrent() || allocationRound != round) return@launch
                saveAttempt(
                    sceneId,
                    MagicClassQuizAttemptRequest(
                        attemptId = state.attemptId,
                        phase = "draft",
                        answers = encodeAnswers(quiz, state.answers),
                        startNewAttempt = true,
                    ),
                )
            }
            if (closed || !isAccountCurrent() || allocationRound != round) return@launch
            response.onSuccess { dto ->
                startNewOnNextSave = false
                update { it.copy(attemptId = dto.attemptId ?: it.attemptId, loading = false) }
            }.onFailure { error ->
                if (!closed) update { it.copy(error = error.message ?: "重新答题失败") }
            }
        }
    }

    /** 会话结束时取一份可靠落盘任务；没有待保存草稿或待确认提交时返回 null。 */
    fun takeDraftFlush(): (suspend () -> Unit)? {
        if (closed || state.loading || state.phase == "reviewed") return null
        val pending = pendingSubmit
        if (!draftDirty && pending == null) return null
        val version = pending?.version ?: editVersion
        val flushRound = pending?.round ?: round
        val attempt = pending?.attemptId ?: state.attemptId
        val answers = pending?.answers ?: state.answers
        val newAttempt = if (pending != null) false else startNewOnNextSave
        return {
            // 先给在途提交一小段完成窗口；剩余时间留给补草稿，整体仍受退出落盘预算约束。
            val outcome = pending?.let { inFlight ->
                withTimeoutOrNull(1_000L) { inFlight.outcome.await() }
            }
            if (outcome == SubmitOutcome.Confirmed) {
                // 已确认的提交不需要再发草稿；返回成功，不把服务端记录回写成草稿。
                Unit
            } else {
                writeMutex.withLock {
                    // 拿到写锁、即将发送时再核对账号与作答代次。
                    if (!isAccountCurrent()) throw ClassroomWriteAccountChangedException()
                    if (version != editVersion || flushRound != round) {
                        throw ClassroomWriteStaleException()
                    }
                    if (state.phase != "reviewed") {
                        // 服务器已确认提交时草稿回退会返回 409；保留服务端记录，不覆盖。
                        val result = saveAttempt(
                            sceneId,
                            MagicClassQuizAttemptRequest(
                                attemptId = attempt,
                                phase = "draft",
                                answers = encodeAnswers(quiz, answers),
                                startNewAttempt = newAttempt,
                            ),
                        )
                        result.exceptionOrNull()?.let { error ->
                            if (isAttemptConflict(error)) throw ClassroomWriteConflictException()
                            throw error
                        }
                    }
                    Unit
                }
            }
        }
    }

    fun close(cancelInFlight: Boolean = true) {
        if (closed) return
        closed = true
        debounceJob?.cancel()
        debounceJob = null
        loadJob?.cancel()
        loadJob = null
        if (cancelInFlight) {
            writeJob?.cancel()
            writeJob = null
        }
    }

    private fun publish() {
        if (!closed) onState(state)
    }

    private fun update(transform: (NativeQuizUiState) -> NativeQuizUiState) {
        if (closed) return
        val next = transform(state)
        if (next == state) return
        state = next
        publish()
    }

    /** 结算必须同时属于仍打开的协调器和仍有效的播放会话。 */
    private fun canSettleRewards(): Boolean = !closed && isSessionCurrent()

    private fun isAttemptConflict(error: Throwable): Boolean =
        error is ClassroomApiException &&
            (error.statusCode == 409 || error.code == "QUIZ_ATTEMPT_CONFLICT")

    /** 明确的 4xx 拒绝说明请求未被受理；408/429/5xx/IO 失败仍属于结果不确定。 */
    private fun isDefinitiveRejection(error: Throwable): Boolean =
        error is ClassroomApiException &&
            error.statusCode in 400..499 &&
            error.statusCode !in setOf(408, 409, 429)
}

internal fun gradeQuiz(quiz: NativeQuiz, answers: Map<String, NativeAnswer>): Map<String, NativeQuizResult> {
    return quiz.questions.associate { question ->
        val result = when {
            question.isShortAnswer -> NativeQuizResult(
                questionId = question.id,
                correct = null,
                earned = 0.0,
                comment = "主观题请对照参考答案自行核对",
            )
            !question.autoGradable -> NativeQuizResult(
                questionId = question.id,
                correct = null,
                earned = 0.0,
                comment = "本题没有下发标准答案，请对照解析",
            )
            else -> {
                val selected = answers[question.id]?.selected.orEmpty()
                val correct = if (question.isMultiple) {
                    selected == question.answerKey.toSet()
                } else {
                    selected.size == 1 && selected.first() in question.answerKey
                }
                NativeQuizResult(
                    questionId = question.id,
                    correct = correct,
                    earned = if (correct) question.points else 0.0,
                    comment = if (correct) null else question.analysis.ifBlank { null },
                )
            }
        }
        question.id to result
    }
}

internal fun decodeAnswers(quiz: NativeQuiz, raw: Map<String, Any?>): Map<String, NativeAnswer> {
    return quiz.questions.associate { question ->
        val value = raw[question.id]
        val answer = when {
            question.isShortAnswer -> NativeAnswer(text = value.asText())
            value is List<*> -> NativeAnswer(
                selected = value.mapNotNull { it.asText().takeIf { text -> text.isNotBlank() } }.toSet(),
            )
            else -> NativeAnswer(selected = value.asText().takeIf { it.isNotBlank() }?.let { setOf(it) }.orEmpty())
        }
        question.id to answer
    }
}

internal fun encodeAnswers(quiz: NativeQuiz, answers: Map<String, NativeAnswer>): Map<String, Any?> {
    return quiz.questions.mapNotNull { question ->
        val answer = answers[question.id] ?: return@mapNotNull null
        if (!answer.hasValue) return@mapNotNull null
        val value: Any = when {
            question.isShortAnswer -> answer.text
            question.isMultiple -> answer.selected.toList()
            else -> answer.selected.firstOrNull().orEmpty()
        }
        question.id to value
    }.toMap()
}

internal fun decodeResults(raw: List<Map<String, Any?>>): Map<String, NativeQuizResult> {
    return raw.mapNotNull { item ->
        val id = item["questionId"].asText().ifBlank { item["question_id"].asText() }
        if (id.isBlank()) return@mapNotNull null
        val correct = when (item["correct"]) {
            is Boolean -> item["correct"] as Boolean
            is Number -> (item["correct"] as Number).toInt() != 0
            else -> when (item["status"].asText()) {
                "correct" -> true
                "incorrect" -> false
                else -> null
            }
        }
        id to NativeQuizResult(
            questionId = id,
            correct = correct,
            earned = item["earned"].asDouble()?.takeIf { value -> value >= 0 } ?: 0.0,
            comment = item["aiComment"].asText().ifBlank { item["comment"].asText() }.ifBlank { null },
            selfChecked = item["selfChecked"] as? Boolean ?: false,
        )
    }.toMap()
}

internal fun encodeResults(results: Collection<NativeQuizResult>): List<Map<String, Any?>> =
    results.map { result ->
        mapOf(
            "questionId" to result.questionId,
            "correct" to result.correct,
            "status" to when (result.correct) {
                true -> "correct"
                false -> "incorrect"
                null -> "ungraded"
            },
            "earned" to result.earned,
            "aiComment" to result.comment,
            "selfChecked" to result.selfChecked,
        )
    }

internal fun Boolean?.orFalse(): Boolean = this == true

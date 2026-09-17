package com.example.campusai.ui.screens.counselor

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.viewmodel.CreationExtras
import androidx.lifecycle.viewModelScope
import com.example.campusai.data.classroom.ClassroomJobMachine
import com.example.campusai.data.classroom.ClassroomJobState
import com.example.campusai.data.classroom.ClassroomProposalScope
import com.example.campusai.data.classroom.ClassroomRestoreRecord
import com.example.campusai.data.classroom.JobSnapshot
import com.example.campusai.data.remote.agent.AgentApprovalDto
import com.example.campusai.data.remote.agent.AgentJobDto
import com.example.campusai.data.remote.agent.CounselorFinalMetaDto
import com.example.campusai.data.remote.agent.InteractiveClassroomProposalDto
import com.example.campusai.data.model.ExpressionResult
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.AgentRuntimeRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

fun interface CpmChatStreamer {
    suspend fun stream(question: String, expression: ExpressionResult?, courseId: String?, onChunk: (String) -> Unit)
}

/** Narrow seam for CPM's interactive classroom action; easy to exercise in JVM tests. */
interface CpmClassroomGateway {
    suspend fun create(courseId: String, mode: String, idempotencyKey: String): Result<AgentJobDto>
    suspend fun get(jobId: String): Result<AgentJobDto>
    suspend fun decide(approvalId: String, approved: Boolean): Result<AgentApprovalDto>
}

private class AgentRuntimeCpmClassroomGateway(
    private val repository: AgentRuntimeRepository,
) : CpmClassroomGateway {
    override suspend fun create(courseId: String, mode: String, idempotencyKey: String): Result<AgentJobDto> =
        repository.createJob(
            jobKind = "interactive_classroom",
            payload = mapOf("course_id" to courseId, "mode" to mode),
            idempotencyKey = idempotencyKey,
        )

    override suspend fun get(jobId: String): Result<AgentJobDto> = repository.getJob(jobId)

    override suspend fun decide(approvalId: String, approved: Boolean): Result<AgentApprovalDto> =
        repository.decideApproval(approvalId, if (approved) "APPROVED" else "REJECTED")
}

fun interface CpmChatMetadataStreamer {
    suspend fun stream(
        question: String,
        expression: ExpressionResult?,
        courseId: String?,
        onChunk: (String) -> Unit,
        onMeta: (CounselorFinalMetaDto) -> Unit,
    )
}

class CounselorViewModel(
    private val streamer: CpmChatStreamer,
    private val clock: () -> Long = System::currentTimeMillis,
    initialCourse: CpmCourseContext? = null,
    private val metadataStreamer: CpmChatMetadataStreamer? = null,
    private val classroomGateway: CpmClassroomGateway? = null,
    private val savedStateHandle: SavedStateHandle = SavedStateHandle(),
    private val classroomDelay: suspend (Long) -> Unit = { delay(it) },
    private val classroomMaxWaitMs: Long = 15 * 60 * 1000L,
    private val autoObserveClassroomJobs: Boolean = true,
    /** 当前登录身份（账号 id）。用于把课堂任务严格隔离到"这个账号 + 这个提案"。 */
    private val identityProvider: () -> String = { "" },
) : ViewModel() {
    private val _uiState = MutableStateFlow(
        if (initialCourse != null) CpmCounselorUiState().copy(courseContext = initialCourse)
        else CpmCounselorUiState(),
    )
    val uiState: StateFlow<CpmCounselorUiState> = _uiState.asStateFlow()
    private var expression: ExpressionResult? = null
    private var classroomPolling: Job? = null
    private var classroomObservationAllowed = true
    /**
     * 代次：每个新提案 +1，用于作废所有旧的在途请求与旧轮询。
     *
     * 只靠"取消 Job"是不够的：已经拿到响应的协程仍会继续执行 `.onSuccess`，
     * 把旧提案的 job / 深链 / 错误写进新提案的界面。
     */
    private var classroomGeneration = 0
    private var classroomFingerprint = ""

    init {
        // 进程重建后不在这里恢复：恢复必须绑定到"具体提案"，
        // 而提案要等下一次 SSE 到达才知道（见 acceptClassroomProposal）。
        // 身份已经变化（换账号/登出）时立刻作废整条记录。
        ClassroomRestoreRecord.clearIfIdentityChanged(savedStateHandle, identityProvider())
    }

    fun updateInput(value: String) = _uiState.update { it.copy(input = value) }

    fun updateExpression(value: ExpressionResult?) {
        expression = value
    }

    /**
     * 新建普通会话：清空课程上下文，避免上一个课程的旧 courseId 泄漏到
     * 来源中不含课程的新会话。
     */
    fun startPlainSession() {
        if (_uiState.value.courseContext != null || _uiState.value.chatActive) {
            resetClassroomScope()
            _uiState.value = CpmCounselorUiState()
        }
    }

    fun send(prompt: String = _uiState.value.input) {
        val question = prompt.trim()
        if (question.isEmpty() || _uiState.value.sending) return
        val submitted = CpmCounselorStateReducer.submit(_uiState.value, question, clock())
        val assistantId = submitted.messages.last().id
        val sentCourseId = submitted.courseContext?.courseId
        _uiState.value = submitted
        viewModelScope.launch {
            try {
                var received = false
                val onChunk: (String) -> Unit = { chunk ->
                    if (chunk.isNotEmpty()) {
                        received = true
                        _uiState.update { CpmCounselorStateReducer.appendChunk(it, assistantId, chunk) }
                    }
                }
                if (metadataStreamer != null) {
                    metadataStreamer.stream(question, expression, sentCourseId, onChunk) { meta ->
                        val proposal = meta.suggestedActions
                            .asSequence()
                            .mapNotNull { action -> action.interactiveClassroomProposal() }
                            .firstOrNull()
                        _uiState.update { it.copy(suggestedActions = meta.suggestedActions) }
                        // 提案走 acceptClassroomProposal：它负责跨提案/跨账号的状态隔离。
                        if (proposal != null) acceptClassroomProposal(proposal)
                    }
                } else {
                    streamer.stream(question, expression, sentCourseId, onChunk)
                }
                if (!received) throw IllegalStateException("empty AI stream")
                _uiState.update { CpmCounselorStateReducer.complete(it, assistantId) }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                _uiState.update {
                    CpmCounselorStateReducer.fail(
                        it,
                        assistantId,
                        error.message ?: "AI 服务暂时不可用",
                    )
                }
            }
        }
    }

    fun retryLast() {
        val prompt = _uiState.value.messages.lastOrNull { it.role == "user" }?.content.orEmpty()
        send(prompt)
    }

    fun shuffleRecommendations() = _uiState.update { state ->
        state.copy(recommendationOffset = (state.recommendationOffset + 4).mod(CpmPromptCatalog.all.size))
    }

    fun sendPlaybackCommand(command: DigitalHumanCommand) = _uiState.update { state ->
        state.copy(playbackCommand = command, playbackCommandId = state.playbackCommandId + 1)
    }

    // ===== 互动课堂提案 =====

    /**
     * 接收一个新提案。
     *
     * - **同一个提案**（组件重挂载、同一条 SSE 重放）：只刷新展示，绝不动 job / 轮询 / 幂等键。
     * - **新提案**：取消旧轮询、作废旧代次、清空旧 job 与错误、换新幂等键，
     *   绝不显示上一节课的深链。
     * - 进程重建后重新拿到同一个提案（同一账号 + 同一课程 + 同一模式，且任务仍在途）：
     *   继续同一个 job，**不重复生成**。
     */
    fun acceptClassroomProposal(proposal: InteractiveClassroomProposalDto) {
        val identity = identityProvider()
        val fingerprint = ClassroomProposalScope.fingerprint(identity, proposal)
        if (fingerprint == classroomFingerprint && _uiState.value.classroomProposal != null) {
            _uiState.update { it.copy(classroomProposal = proposal) }
            return
        }

        // 新提案：先把旧的彻底作废
        cancelClassroomPolling()
        classroomGeneration += 1
        classroomFingerprint = fingerprint

        val resumable = resumableClassroomRecord(identity, proposal)
        if (resumable != null) {
            val jobId = resumable.jobId!! // resumableClassroomRecord 已保证非空
            resumable.copy(fingerprint = fingerprint).writeTo(savedStateHandle)
            _uiState.value = _uiState.value.copy(
                classroomProposal = proposal,
                classroomJob = ClassroomJobMachine.restored(jobId, resumable.phase),
            )
            if (autoObserveClassroomJobs && classroomObservationAllowed) observeClassroomJob(jobId)
            return
        }

        ClassroomRestoreRecord.clearFrom(savedStateHandle)
        newClassroomRecord(fingerprint, identity, proposal.courseId, proposal.mode)
            .writeTo(savedStateHandle)
        _uiState.value = _uiState.value.copy(
            classroomProposal = proposal,
            // 全新提案必须干净：不显示旧 job、旧错误、旧深链
            classroomJob = ClassroomJobState(),
        )
    }

    /** 学生确认是唯一可能创建 Agent Job 的入口。 */
    fun confirmClassroomProposal() {
        val proposal = _uiState.value.classroomProposal ?: return
        val gateway = classroomGateway ?: return
        if (!proposal.available || !proposal.requiresConfirmation) return
        val generation = classroomGeneration
        val fingerprint = classroomFingerprint
        val current = _uiState.value.classroomJob
        val requested = ClassroomJobMachine.confirmRequested(current)
        if (requested == current) return
        _uiState.value = _uiState.value.copy(classroomJob = requested)

        // 同一提案内重试（例如网络错误后重新点击）必须复用**同一个**幂等键，
        // 否则一次确认会变成两次上游生成。
        val record = ClassroomRestoreRecord.read(savedStateHandle)
        val key = record?.takeIf { it.belongsTo(fingerprint) }?.idempotencyKey
            ?: newClassroomRecord(fingerprint, identityProvider(), proposal.courseId, proposal.mode)
                .idempotencyKey
        recordFor(fingerprint, proposal.courseId, proposal.mode, key, phase = "CREATING_JOB")

        viewModelScope.launch {
            gateway.create(proposal.courseId, proposal.mode, key)
                .onSuccess { job ->
                    if (!isCurrentClassroom(generation, fingerprint, null)) return@onSuccess
                    val next = ClassroomJobMachine.jobCreated(requested, job.toJobSnapshot())
                    _uiState.value = _uiState.value.copy(classroomJob = next)
                    job.jobId.takeIf { it.isNotBlank() }?.let { jobId ->
                        recordFor(fingerprint, proposal.courseId, proposal.mode, key, jobId, next.phase.name)
                        if (autoObserveClassroomJobs && classroomObservationAllowed) {
                            observeClassroomJob(jobId)
                        }
                    }
                }
                .onFailure { error ->
                    if (!isCurrentClassroom(generation, fingerprint, null)) return@onFailure
                    _uiState.value = _uiState.value.copy(
                        classroomJob = ClassroomJobMachine.createFailed(
                            requested,
                            error.message ?: "互动课堂任务创建失败",
                        ),
                    )
                }
        }
    }

    fun refreshClassroomJob() {
        val jobId = _uiState.value.classroomJob.jobId ?: return
        val generation = classroomGeneration
        val fingerprint = classroomFingerprint
        viewModelScope.launch { fetchClassroomJobOnce(generation, fingerprint, jobId) }
    }

    fun approveClassroomProposal() {
        val gateway = classroomGateway ?: return
        val current = _uiState.value.classroomJob
        val approvalId = current.approvalId ?: return
        val jobId = current.jobId
        val requested = ClassroomJobMachine.approveRequested(current)
        if (requested == current) return
        val generation = classroomGeneration
        val fingerprint = classroomFingerprint
        _uiState.value = _uiState.value.copy(classroomJob = requested)
        viewModelScope.launch {
            gateway.decide(approvalId, approved = true)
                .onSuccess {
                    if (!isCurrentClassroom(generation, fingerprint, jobId)) return@onSuccess
                    val state = _uiState.value.classroomJob
                    val next = ClassroomJobMachine.approveDone(
                        state,
                        JobSnapshot(jobId = state.jobId, runId = state.runId, status = "QUEUED"),
                    )
                    _uiState.value = _uiState.value.copy(classroomJob = next)
                    // 后端已把**原 Run** 重新排队 —— 继续订阅同一个 job。
                    if (autoObserveClassroomJobs && classroomObservationAllowed) {
                        state.jobId?.let(::observeClassroomJob)
                    }
                }
                .onFailure { error ->
                    if (!isCurrentClassroom(generation, fingerprint, jobId)) return@onFailure
                    _uiState.value = _uiState.value.copy(
                        classroomJob = ClassroomJobMachine.approveFailed(
                            requested,
                            error.message ?: "确认失败，请重试",
                        ),
                    )
                    // 审批响应丢失：靠**查询同一个 job** 恢复真实状态，
                    // 绝不重新创建任务（那会变成两次上游生成）。
                    if (jobId != null && autoObserveClassroomJobs && classroomObservationAllowed) {
                        observeClassroomJob(jobId)
                    }
                }
        }
    }

    fun rejectClassroomProposal() {
        val gateway = classroomGateway ?: return
        val current = _uiState.value.classroomJob
        val approvalId = current.approvalId ?: return
        if (!current.canApprove) return
        val jobId = current.jobId
        val generation = classroomGeneration
        val fingerprint = classroomFingerprint
        viewModelScope.launch {
            gateway.decide(approvalId, approved = false)
            if (!isCurrentClassroom(generation, fingerprint, jobId)) return@launch
            cancelClassroomPolling()
            _uiState.update { ClassroomJobStateHolder.reject(it) }
        }
    }

    fun stopClassroomObservation() {
        cancelClassroomPolling()
        classroomObservationAllowed = false
    }

    fun resumeClassroomObservation() {
        classroomObservationAllowed = true
        val jobId = _uiState.value.classroomJob.jobId ?: return
        if (_uiState.value.classroomJob.needsPolling) observeClassroomJob(jobId)
    }

    fun openClassroomDeepLink(): String? = _uiState.value.classroomJob.deepLink

    /**
     * 身份变化（登录 / 换账号）。恢复记录不再属于当前账号时整条作废，
     * 否则新账号会恢复出上一个账号的课堂任务与深链。
     */
    fun onClassroomIdentityChanged(identity: String) {
        if (ClassroomRestoreRecord.clearIfIdentityChanged(savedStateHandle, identity)) {
            resetClassroomScope()
        }
    }

    /** 登出 / 身份失效：立即清除恢复记录并停掉轮询。 */
    fun onClassroomSessionEnded() {
        ClassroomRestoreRecord.clearFrom(savedStateHandle)
        resetClassroomScope()
    }

    private fun resetClassroomScope() {
        cancelClassroomPolling()
        classroomGeneration += 1
        classroomFingerprint = ""
        _uiState.update { it.copy(classroomProposal = null, classroomJob = ClassroomJobState()) }
    }

    private fun cancelClassroomPolling() {
        classroomPolling?.cancel()
        classroomPolling = null
    }

    private fun newClassroomRecord(
        fingerprint: String,
        identity: String,
        courseId: String,
        mode: String,
        phase: String = "IDLE",
    ): ClassroomRestoreRecord = ClassroomRestoreRecord(
        fingerprint = fingerprint,
        identity = identity,
        courseId = courseId,
        mode = mode,
        jobId = null,
        idempotencyKey = "android-cpm-classroom-" + java.util.UUID.randomUUID().toString(),
        phase = phase,
    )

    /** 就地更新恢复记录；指纹不属于当前提案时**不写**，避免污染。 */
    private fun recordFor(
        fingerprint: String,
        courseId: String,
        mode: String,
        idempotencyKey: String,
        jobId: String? = null,
        phase: String = "IDLE",
    ) {
        if (fingerprint != classroomFingerprint) return
        ClassroomRestoreRecord(
            fingerprint = fingerprint,
            identity = identityProvider(),
            courseId = courseId,
            mode = mode,
            jobId = jobId,
            idempotencyKey = idempotencyKey,
            phase = phase,
        ).writeTo(savedStateHandle)
    }

    /**
     * 进程重建后能否续跑：同一账号 + 同一课程 + 同一模式，且任务**仍在途**。
     *
     * 终态任务不复用：新提案应当干净开始（旧深链仍可在课程详情的历史课堂里打开）。
     */
    private fun resumableClassroomRecord(
        identity: String,
        proposal: InteractiveClassroomProposalDto,
    ): ClassroomRestoreRecord? {
        val record = ClassroomRestoreRecord.read(savedStateHandle) ?: return null
        if (record.identity != identity) return null
        if (record.courseId != proposal.courseId) return null
        if (record.mode != proposal.mode) return null
        if (record.jobId.isNullOrBlank()) return null
        if (ClassroomJobMachine.isTerminalPhase(ClassroomJobMachine.phaseOfName(record.phase))) return null
        return record
    }

    /**
     * 迟到回写防护：代次 + 提案指纹 + jobId 三者同时校验。
     * 只校验代次挡不住"同一代次里旧 job 的迟到响应"，只校验 jobId 挡不住跨提案串状态。
     */
    private fun isCurrentClassroom(generation: Int, fingerprint: String, jobId: String?): Boolean {
        if (generation != classroomGeneration) return false
        if (fingerprint != classroomFingerprint) return false
        if (jobId != null) {
            val current = _uiState.value.classroomJob.jobId
            if (current != null && current != jobId) return false
        }
        return true
    }

    private fun observeClassroomJob(jobId: String) {
        cancelClassroomPolling()
        val generation = classroomGeneration
        val fingerprint = classroomFingerprint
        classroomPolling = viewModelScope.launch {
            val startedAt = clock()
            while (true) {
                if (!isCurrentClassroom(generation, fingerprint, jobId)) return@launch
                if (clock() - startedAt > classroomMaxWaitMs) {
                    _uiState.update { it.copy(classroomJob = it.classroomJob.copy(error = "生成等待时间过长，请稍后回到本页查看")) }
                    return@launch
                }
                fetchClassroomJobOnce(generation, fingerprint, jobId)
                val state = _uiState.value.classroomJob
                if (state.isTerminal && !state.awaitingOutcome) {
                    // 终态：归档恢复记录，避免下一次提案复用已完成的 job
                    if (fingerprint == classroomFingerprint) {
                        ClassroomRestoreRecord.clearFrom(savedStateHandle)
                    }
                    return@launch
                }
                classroomDelay(3000L)
            }
        }
    }

    private suspend fun fetchClassroomJobOnce(generation: Int, fingerprint: String, jobId: String) {
        val gateway = classroomGateway ?: return
        gateway.get(jobId)
            .onSuccess { job ->
                if (!isCurrentClassroom(generation, fingerprint, jobId)) return@onSuccess
                val next = ClassroomJobMachine.pollResult(_uiState.value.classroomJob, job.toJobSnapshot())
                _uiState.value = _uiState.value.copy(classroomJob = next)
                val record = ClassroomRestoreRecord.read(savedStateHandle)
                if (record != null && record.belongsTo(fingerprint)) {
                    record.copy(phase = next.phase.name).writeTo(savedStateHandle)
                }
            }
            .onFailure { error ->
                if (!isCurrentClassroom(generation, fingerprint, jobId)) return@onFailure
                _uiState.value = _uiState.value.copy(
                    classroomJob = ClassroomJobMachine.pollFailed(
                        _uiState.value.classroomJob,
                        error.message ?: "进度查询失败，正在重试",
                    ),
                )
            }
    }
}

private object ClassroomJobStateHolder {
    fun reject(state: CpmCounselorUiState): CpmCounselorUiState =
        state.copy(classroomJob = ClassroomJobMachine.approveRejected(state.classroomJob))
}

private fun AgentJobDto.toJobSnapshot(): JobSnapshot {
    fun value(key: String): String? = inputRef[key]?.toString()?.takeIf { it.isNotBlank() }
    return JobSnapshot(
        jobId = jobId,
        runId = latestRunId,
        status = status,
        pendingApprovalId = pendingApprovalId,
        sessionId = value("session_id"),
        deepLink = value("deep_link"),
    )
}

class CounselorViewModelFactory(
    private val repository: AppRepository,
    private val initialCourse: CpmCourseContext? = null,
    private val agentRuntimeRepository: AgentRuntimeRepository? = null,
) : ViewModelProvider.Factory {
    /** 当前登录身份：账号 id 优先，退化到学号；未登录时为空串。 */
    private fun identity(): String {
        val user = repository.session.value
        return user?.accountId?.takeIf { it.isNotBlank() }
            ?: user?.studentId?.takeIf { it.isNotBlank() }
            ?: ""
    }

    @Suppress("UNCHECKED_CAST")
    private fun <T : ViewModel> createWithHandle(handle: SavedStateHandle): T = CounselorViewModel(
        streamer = CpmChatStreamer { question, expression, courseId, onChunk ->
            repository.streamChat(
                message = question,
                expression = expression,
                courseId = courseId,
                onChunk = { chunk -> onChunk(chunk) },
            )
        },
        metadataStreamer = CpmChatMetadataStreamer { question, expression, courseId, onChunk, onMeta ->
            repository.streamChat(
                message = question,
                expression = expression,
                courseId = courseId,
                onChunk = { chunk -> onChunk(chunk) },
                onMeta = { meta -> onMeta(meta) },
            )
        },
        classroomGateway = agentRuntimeRepository?.let(::AgentRuntimeCpmClassroomGateway),
        initialCourse = initialCourse,
        savedStateHandle = handle,
        identityProvider = ::identity,
    ) as T

    override fun <T : ViewModel> create(modelClass: Class<T>): T = createWithHandle(SavedStateHandle())

    override fun <T : ViewModel> create(modelClass: Class<T>, extras: CreationExtras): T =
        createWithHandle(extras.createSavedStateHandle())
}

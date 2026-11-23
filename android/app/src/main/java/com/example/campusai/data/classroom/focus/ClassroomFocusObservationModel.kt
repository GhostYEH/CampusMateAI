package com.example.campusai.data.classroom.focus

import kotlin.math.sqrt

/**
 * 原生课堂「课堂观察」第一阶段的纯规则与窗口聚合。
 *
 * 这一层不接触 CameraX、ML Kit、Compose 或系统时钟；所有时间由调用方传入单调时钟
 * （[android.os.SystemClock.elapsedRealtime]）。因此采样、10 秒窗口、事件归属和
 * 无效信号可以用普通 JVM 测试完整覆盖。
 *
 * 产品边界：
 * - 只记录可观察事实，不输出专注度、分心结论或学习效果判断。
 * - 低头、转头、安静听课和暂时没有操作都不是分心判据；窗口只保留头部角度统计。
 * - 只记录学生主动翻页、提交答案和发送提问；自动翻页和重放事件由事件来源过滤。
 */
object ClassroomFocusObservationConfig {
    /** 约 4 次每秒。 */
    const val SAMPLE_INTERVAL_MS = 250L
    /** 窗口长度；首版固定 10 秒非重叠窗口。 */
    const val WINDOW_MS = 10_000L
    /** 连续检测到人脸满 2 秒才确认。 */
    const val FACE_CONFIRM_MS = 2_000L
    /** 确认后连续 12 秒有效画面没有脸才显示无法判断。 */
    const val FACE_MISSING_MS = 12_000L
    /** 主动课堂操作有效期 15 秒。 */
    const val ACTIVITY_VALID_MS = 15_000L
    /** 弱光判定：Y 平面平均亮度低于该值（0-255）。 */
    const val LOW_LIGHT_LUMA_THRESHOLD = 38.0
    /** 弱光持续 1 秒才标为暂不可观察，避免自动曝光抖动。 */
    const val LOW_LIGHT_GRACE_MS = 1_000L
    /** 连续 3 秒没有新帧视为视频冻结。 */
    const val VIDEO_FREEZE_MS = 3_000L
    /** 采样间隔超过 1.2 秒视为采样中断。 */
    const val SAMPLE_GAP_MS = 1_200L
    /** ML Kit 快速模式的最低人脸尺寸。 */
    const val MIN_FACE_SIZE = 0.2f
    /** 只留在本课内存的事件上限。 */
    const val EVENT_HISTORY_LIMIT = 100
    /** 只留在本课内存的窗口上限（约 30 分钟）。 */
    const val WINDOW_HISTORY_LIMIT = 180
    /** 一个 10 秒窗口内有效采样少于一半时，窗口不可判断。 */
    const val MIN_VALID_SAMPLE_COVERAGE = 0.5
    /** 窗口内人脸可见比例低于该值时不判断。 */
    const val MIN_FACE_VISIBLE_RATIO = 0.2
}

/** 对外状态；文案即契约。无脸与暂不可观察都显示「无法判断」并附原因。 */
enum class ClassroomFocusStatus(val label: String) {
    OBSERVING("正在观察"),
    RECENT_ACTIVITY("近期有课堂操作"),
    FACE_PRESENT("检测到人脸"),
    FACE_MISSING("无法判断"),
    UNAVAILABLE("无法判断"),
}

/** 只有三类学生主动操作会被记录。 */
enum class ClassroomFocusEventType {
    PAGE_TURN,
    SUBMIT_ANSWER,
    ASK_QUESTION,
}

/** 事件来源；只有学生主动操作进入窗口计数。 */
enum class ClassroomFocusEventSource {
    STUDENT,
    AUTOMATIC,
    REPLAY,
}

/** 无效信号/启动失败的内部原因。code 用于本地导出，不随课堂接口发送。 */
enum class ClassroomFocusReason(val code: String, val label: String) {
    PERMISSION_DENIED("permission_denied", "摄像头权限被拒绝"),
    CAMERA_UNAVAILABLE("camera_unavailable", "没有可用的摄像头"),
    CAMERA_BUSY("camera_busy", "摄像头被其他应用占用"),
    MODEL_UNAVAILABLE("model_unavailable", "人脸检测器未能启动"),
    LOW_LIGHT("low_light", "画面太暗，暂时无法判断"),
    MULTIPLE_FACES("multiple_faces", "画面中出现多张人脸"),
    NO_FACE("no_face", "持续未检测到人脸"),
    INSUFFICIENT_FACE("insufficient_face", "有效人脸不足"),
    INSUFFICIENT_SAMPLES("insufficient_samples", "有效采样不足"),
    VIDEO_FROZEN("video_frozen", "课堂画面已冻结"),
    SAMPLING_INTERRUPTED("sampling_interrupted", "检测采样中断"),
    DETECTION_FAILED("detection_failed", "人脸检测暂时失败"),
    INVALID_SIGNAL("invalid_signal", "检测信号无效"),
    START_FAILED("start_failed", "无法开启摄像头");

    companion object {
        fun fromCode(code: String?): ClassroomFocusReason? = entries.firstOrNull { it.code == code }
    }
}

enum class ClassroomFocusPhase { IDLE, RUNNING, UNAVAILABLE }

data class ClassroomFocusEvent(
    val type: ClassroomFocusEventType,
    val atMs: Long,
    val source: ClassroomFocusEventSource = ClassroomFocusEventSource.STUDENT,
)

/** 窗口的可判断性；首版不产生 on-task/off-task 结论。 */
enum class ClassroomObservationVerdict(val code: String) {
    OBSERVABLE("observable"),
    UNOBSERVABLE("unobservable"),
}

/** 单个头部角度的窗口统计；标准差按总体标准差计算。 */
data class ClassroomAxisStats(
    val mean: Double,
    val standardDeviation: Double,
    val min: Double,
    val max: Double,
    val samples: Int,
)

data class ClassroomAxisAccumulator(
    val count: Int = 0,
    val sum: Double = 0.0,
    val squareSum: Double = 0.0,
    val min: Double? = null,
    val max: Double? = null,
) {
    fun add(value: Double): ClassroomAxisAccumulator = ClassroomAxisAccumulator(
        count = count + 1,
        sum = sum + value,
        squareSum = squareSum + value * value,
        min = min?.let { minOf(it, value) } ?: value,
        max = max?.let { maxOf(it, value) } ?: value,
    )

    fun stats(): ClassroomAxisStats? {
        if (count == 0) return null
        val mean = sum / count
        val variance = (squareSum / count - mean * mean).coerceAtLeast(0.0)
        return ClassroomAxisStats(
            mean = mean,
            standardDeviation = sqrt(variance),
            min = min ?: 0.0,
            max = max ?: 0.0,
            samples = count,
        )
    }
}

/** 正在累积的窗口；只在内存中保留，不落原始帧。 */
data class ClassroomObservationWindowDraft(
    val index: Int,
    val startedAtMs: Long,
    val endedAtMs: Long,
    val validSamples: Int = 0,
    val invalidSamples: Int = 0,
    val faceVisibleSamples: Int = 0,
    val yaw: ClassroomAxisAccumulator = ClassroomAxisAccumulator(),
    val pitch: ClassroomAxisAccumulator = ClassroomAxisAccumulator(),
    val stageCounts: Map<String, Int> = emptyMap(),
    val reasonCounts: Map<ClassroomFocusReason, Int> = emptyMap(),
) {
    val sampleCount: Int get() = validSamples + invalidSamples
}

/** 已关闭（或复盘导出时截断）的窗口级事实。 */
data class ClassroomObservationWindow(
    val index: Int,
    val startOffsetMs: Long,
    val endOffsetMs: Long,
    val complete: Boolean,
    val validSampleCount: Int,
    val invalidSampleCount: Int,
    val faceVisibleSampleCount: Int,
    val faceVisibleRatio: Double,
    val yaw: ClassroomAxisStats?,
    val pitch: ClassroomAxisStats?,
    val stageCounts: Map<String, Int>,
    val dominantStage: String?,
    val manualPageTurns: Int,
    val quizSubmissions: Int,
    val questions: Int,
    val reasonCounts: Map<ClassroomFocusReason, Int>,
    val verdict: ClassroomObservationVerdict,
    val unavailableReason: ClassroomFocusReason?,
) {
    val sampleCount: Int get() = validSampleCount + invalidSampleCount
}

data class ClassroomFocusState(
    val sessionId: Long = 0L,
    val phase: ClassroomFocusPhase = ClassroomFocusPhase.IDLE,
    val startedAtMs: Long? = null,
    val unavailableReason: ClassroomFocusReason? = null,
    val unavailableSinceMs: Long? = null,
    val faceSinceMs: Long? = null,
    val faceConfirmed: Boolean = false,
    val noFaceSinceMs: Long? = null,
    val lastActivityAtMs: Long? = null,
    val events: List<ClassroomFocusEvent> = emptyList(),
    val stage: String? = null,
    val lastSampleAtMs: Long? = null,
    val windows: List<ClassroomObservationWindow> = emptyList(),
    val currentWindow: ClassroomObservationWindowDraft? = null,
)

object ClassroomFocusObservation {
    fun begin(atMs: Long, sessionId: Long = 0L): ClassroomFocusState = ClassroomFocusState(
        sessionId = sessionId,
        phase = ClassroomFocusPhase.RUNNING,
        startedAtMs = atMs,
    )

    fun stop(): ClassroomFocusState = ClassroomFocusState()

    /**
     * 记录一次课堂操作。自动翻页、重放和全局触摸移动不应进入这里；即使误传，
     * [ClassroomFocusEventSource] 也会把它们挡在窗口计数之外。
     */
    fun recordEvent(
        state: ClassroomFocusState,
        type: ClassroomFocusEventType,
        atMs: Long,
        source: ClassroomFocusEventSource = ClassroomFocusEventSource.STUDENT,
    ): ClassroomFocusState {
        if (state.phase == ClassroomFocusPhase.IDLE) return state
        if (source != ClassroomFocusEventSource.STUDENT) return state
        val events = (state.events + ClassroomFocusEvent(type, atMs, source))
            .takeLast(ClassroomFocusObservationConfig.EVENT_HISTORY_LIMIT)
        return state.copy(
            lastActivityAtMs = atMs,
            noFaceSinceMs = null,
            events = events,
        )
    }

    /** 无效信号：暂不可观察并清空状态时间窗；已完成的窗口与当前窗口事实保留。 */
    fun markUnavailable(
        state: ClassroomFocusState,
        reason: ClassroomFocusReason,
        atMs: Long,
    ): ClassroomFocusState {
        if (state.phase == ClassroomFocusPhase.IDLE) return state
        return state.copy(
            phase = ClassroomFocusPhase.UNAVAILABLE,
            unavailableReason = reason,
            unavailableSinceMs = atMs,
            faceSinceMs = null,
            faceConfirmed = false,
            noFaceSinceMs = null,
            lastActivityAtMs = null,
        )
    }

    /**
     * 只把一个无效采样记入当前窗口，不改变对外状态。弱光宽限期内和看门狗
     * 首次报告时使用，避免为了记录事实而提前显示「无法判断」。
     */
    fun noteInvalidSample(
        state: ClassroomFocusState,
        atMs: Long,
        reason: ClassroomFocusReason,
        stage: String? = null,
        sessionId: Long = state.sessionId,
    ): ClassroomFocusState = appendSample(
        state = state,
        atMs = atMs,
        valid = false,
        faceCount = 0,
        reason = reason,
        yawDegrees = null,
        pitchDegrees = null,
        stage = stage,
        sessionId = sessionId,
    )

    /**
     * 应用一帧检测结果。
     *
     * `valid = false` 表示这一帧不能用于判断（弱光、冻结、采样中断等），立即进入
     * 暂不可观察并记入窗口。之后收到有效帧时从零恢复，需要重新连续 2 秒确认人脸。
     *
     * 单帧漏检不改变状态：确认后第一次 `faceCount == 0` 只开始累计 `noFaceSinceMs`，
     * 下一帧重新检测到人脸就把累计清空。
     *
     * [sessionId] 必须等于 [ClassroomFocusState.sessionId]；关闭后重开的旧会话回调
     * 即使误传到新状态也会被忽略。
     */
    fun applySample(
        state: ClassroomFocusState,
        atMs: Long,
        faceCount: Int,
        valid: Boolean = true,
        invalidReason: ClassroomFocusReason? = null,
        yawDegrees: Double? = null,
        pitchDegrees: Double? = null,
        stage: String? = null,
        sessionId: Long = state.sessionId,
    ): ClassroomFocusState {
        if (state.phase == ClassroomFocusPhase.IDLE) return state
        if (sessionId != state.sessionId) return state

        val appended = appendSample(
            state = state,
            atMs = atMs,
            valid = valid,
            faceCount = faceCount,
            reason = invalidReason,
            yawDegrees = yawDegrees,
            pitchDegrees = pitchDegrees,
            stage = stage,
            sessionId = sessionId,
        )
        if (!valid) {
            return markUnavailable(
                appended,
                invalidReason ?: ClassroomFocusReason.INVALID_SIGNAL,
                atMs,
            )
        }
        if (faceCount < 0) {
            return markUnavailable(appended, ClassroomFocusReason.INVALID_SIGNAL, atMs)
        }
        if (faceCount > 1) {
            return markUnavailable(appended, ClassroomFocusReason.MULTIPLE_FACES, atMs)
        }

        val base = if (appended.phase == ClassroomFocusPhase.UNAVAILABLE) {
            appended.copy(
                phase = ClassroomFocusPhase.RUNNING,
                unavailableReason = null,
                unavailableSinceMs = null,
                faceSinceMs = null,
                faceConfirmed = false,
                noFaceSinceMs = null,
            )
        } else {
            appended
        }

        if (faceCount == 1) {
            val faceSince = base.faceSinceMs ?: atMs
            return base.copy(
                faceSinceMs = faceSince,
                faceConfirmed = base.faceConfirmed ||
                    atMs - faceSince >= ClassroomFocusObservationConfig.FACE_CONFIRM_MS,
                noFaceSinceMs = null,
            )
        }

        if (!base.faceConfirmed) {
            return base.copy(faceSinceMs = null, noFaceSinceMs = null)
        }

        return base.copy(noFaceSinceMs = base.noFaceSinceMs ?: atMs)
    }

    /**
     * 由时间窗推导状态。优先级：
     * 暂不可观察 > 持续未检测到人脸 > 近期有课堂操作 > 检测到人脸 > 正在观察。
     */
    fun statusOf(state: ClassroomFocusState, atMs: Long): ClassroomFocusStatus? {
        if (state.phase == ClassroomFocusPhase.IDLE) return null
        if (state.phase == ClassroomFocusPhase.UNAVAILABLE) return ClassroomFocusStatus.UNAVAILABLE

        // 从未确认到人脸时，也要让第一个已关闭窗口的无脸事实反映到状态条，
        // 不能一直停留在「正在观察」。
        val latest = state.windows.lastOrNull()
        if (!state.faceConfirmed && latest != null &&
            latest.verdict == ClassroomObservationVerdict.UNOBSERVABLE &&
            (latest.unavailableReason == ClassroomFocusReason.NO_FACE ||
                latest.unavailableReason == ClassroomFocusReason.INSUFFICIENT_FACE)
        ) {
            return ClassroomFocusStatus.FACE_MISSING
        }

        val noFaceSince = state.noFaceSinceMs
        if (state.faceConfirmed && noFaceSince != null &&
            atMs - noFaceSince >= ClassroomFocusObservationConfig.FACE_MISSING_MS
        ) {
            return ClassroomFocusStatus.FACE_MISSING
        }
        val lastActivity = state.lastActivityAtMs
        if (lastActivity != null &&
            atMs - lastActivity < ClassroomFocusObservationConfig.ACTIVITY_VALID_MS
        ) {
            return ClassroomFocusStatus.RECENT_ACTIVITY
        }
        if (state.faceConfirmed) return ClassroomFocusStatus.FACE_PRESENT
        return ClassroomFocusStatus.OBSERVING
    }

    /** 状态对应的不可判断原因；可观察状态返回 null。 */
    fun reasonOf(state: ClassroomFocusState, atMs: Long): ClassroomFocusReason? =
        when (statusOf(state, atMs)) {
            ClassroomFocusStatus.UNAVAILABLE -> state.unavailableReason
            ClassroomFocusStatus.FACE_MISSING -> {
                val latest = state.windows.lastOrNull()
                latest?.unavailableReason?.takeIf {
                    it == ClassroomFocusReason.NO_FACE ||
                        it == ClassroomFocusReason.INSUFFICIENT_FACE
                } ?: ClassroomFocusReason.NO_FACE
            }
            else -> null
        }

    /** 已关闭的最近窗口；当前未满窗口不进入对外状态条。 */
    fun latestWindow(state: ClassroomFocusState): ClassroomObservationWindow? = state.windows.lastOrNull()

    /**
     * 复盘导出用窗口列表：已关闭窗口 + 当前未满窗口（若已有采样）。
     * 不改写会话状态，也不包含任何原始帧。
     */
    fun windowsForExport(
        state: ClassroomFocusState,
        atMs: Long,
    ): List<ClassroomObservationWindow> {
        val draft = state.currentWindow ?: return state.windows
        if (draft.sampleCount == 0) return state.windows
        val cutoff = atMs.coerceIn(draft.startedAtMs, draft.endedAtMs)
        val window = buildWindow(
            state = state,
            draft = draft,
            cutoffMs = cutoff,
            complete = atMs >= draft.endedAtMs,
        )
        return (state.windows + window)
            .takeLast(ClassroomFocusObservationConfig.WINDOW_HISTORY_LIMIT)
    }

    private fun appendSample(
        state: ClassroomFocusState,
        atMs: Long,
        valid: Boolean,
        faceCount: Int,
        reason: ClassroomFocusReason?,
        yawDegrees: Double?,
        pitchDegrees: Double?,
        stage: String?,
        sessionId: Long,
    ): ClassroomFocusState {
        if (state.phase == ClassroomFocusPhase.IDLE) return state
        if (sessionId != state.sessionId) return state
        val startedAt = state.startedAtMs ?: return state

        val advanced = advanceWindows(state, atMs, startedAt)
        val draft = advanced.currentWindow ?: return advanced
        val stageValue = stage?.takeIf { it.isNotBlank() } ?: advanced.stage
        val stageCounts = if (stageValue == null) {
            draft.stageCounts
        } else {
            draft.stageCounts + (stageValue to (draft.stageCounts[stageValue] ?: 0) + 1)
        }

        val invalid = !valid || faceCount < 0 || faceCount > 1
        val invalidReason = when {
            !valid -> reason ?: ClassroomFocusReason.INVALID_SIGNAL
            faceCount < 0 -> ClassroomFocusReason.INVALID_SIGNAL
            faceCount > 1 -> ClassroomFocusReason.MULTIPLE_FACES
            else -> null
        }

        val updatedDraft = if (invalid) {
            val reasonKey = invalidReason ?: ClassroomFocusReason.INVALID_SIGNAL
            draft.copy(
                invalidSamples = draft.invalidSamples + 1,
                stageCounts = stageCounts,
                reasonCounts = draft.reasonCounts +
                    (reasonKey to (draft.reasonCounts[reasonKey] ?: 0) + 1),
            )
        } else if (faceCount == 0) {
            draft.copy(
                validSamples = draft.validSamples + 1,
                stageCounts = stageCounts,
                reasonCounts = draft.reasonCounts +
                    (ClassroomFocusReason.NO_FACE to
                        (draft.reasonCounts[ClassroomFocusReason.NO_FACE] ?: 0) + 1),
            )
        } else {
            draft.copy(
                validSamples = draft.validSamples + 1,
                faceVisibleSamples = draft.faceVisibleSamples + 1,
                yaw = yawDegrees?.let(draft.yaw::add) ?: draft.yaw,
                pitch = pitchDegrees?.let(draft.pitch::add) ?: draft.pitch,
                stageCounts = stageCounts,
            )
        }

        return advanced.copy(
            currentWindow = updatedDraft,
            stage = stageValue,
            lastSampleAtMs = atMs,
        )
    }

    /**
     * 按单调时钟推进窗口。跨越窗口边界时先封窗；如果采样跳跃导致整窗缺失，
     * 缺失窗口仍会以「检测采样中断」进入事实列表，而不是静默消失。
     */
    private fun advanceWindows(
        state: ClassroomFocusState,
        atMs: Long,
        startedAtMs: Long,
    ): ClassroomFocusState {
        val targetIndex = windowIndexOf(atMs, startedAtMs)
        // 首个采样迟到时也从窗口 0 起算，让启动阶段缺帧以「采样中断」被记录，
        // 而不是把 20 秒前的窗口静默折叠掉。
        val draft = state.currentWindow ?: newDraft(startedAtMs, 0)
        if (targetIndex <= draft.index) {
            return state.copy(currentWindow = draft)
        }

        var windows = state.windows
        var current = draft
        while (current.index < targetIndex) {
            windows = appendWindow(
                windows,
                buildWindow(
                    state = state,
                    draft = current,
                    cutoffMs = current.startedAtMs + ClassroomFocusObservationConfig.WINDOW_MS,
                    complete = true,
                ),
            )
            current = newDraft(startedAtMs, current.index + 1)
        }
        return state.copy(windows = windows, currentWindow = current)
    }

    private fun windowIndexOf(atMs: Long, startedAtMs: Long): Int =
        (((atMs - startedAtMs).coerceAtLeast(0L)) /
            ClassroomFocusObservationConfig.WINDOW_MS).toInt()

    private fun newDraft(
        startedAtMs: Long,
        index: Int,
    ): ClassroomObservationWindowDraft {
        val start = startedAtMs + index * ClassroomFocusObservationConfig.WINDOW_MS
        return ClassroomObservationWindowDraft(
            index = index,
            startedAtMs = start,
            endedAtMs = start + ClassroomFocusObservationConfig.WINDOW_MS,
        )
    }

    private fun appendWindow(
        windows: List<ClassroomObservationWindow>,
        window: ClassroomObservationWindow,
    ): List<ClassroomObservationWindow> =
        (windows + window).takeLast(ClassroomFocusObservationConfig.WINDOW_HISTORY_LIMIT)

    private fun buildWindow(
        state: ClassroomFocusState,
        draft: ClassroomObservationWindowDraft,
        cutoffMs: Long,
        complete: Boolean,
    ): ClassroomObservationWindow {
        val sessionStart = state.startedAtMs ?: draft.startedAtMs
        val cutoff = cutoffMs.coerceIn(draft.startedAtMs, draft.endedAtMs)
        val startOffset = (draft.startedAtMs - sessionStart).coerceAtLeast(0L)
        val endOffset = (cutoff - sessionStart).coerceAtLeast(startOffset)
        val duration = (cutoff - draft.startedAtMs).coerceAtLeast(0L)
        val expectedSamples = maxOf(
            1,
            (duration / ClassroomFocusObservationConfig.SAMPLE_INTERVAL_MS).toInt(),
        )

        val windowEvents = state.events.filter { event ->
            event.atMs <= cutoff && (
                if (draft.index == 0) {
                    event.atMs >= draft.startedAtMs
                } else {
                    event.atMs > draft.startedAtMs
                }
                )
        }
        val pageTurns = windowEvents.count { it.type == ClassroomFocusEventType.PAGE_TURN }
        val submissions = windowEvents.count { it.type == ClassroomFocusEventType.SUBMIT_ANSWER }
        val questions = windowEvents.count { it.type == ClassroomFocusEventType.ASK_QUESTION }

        val faceRatio = if (draft.validSamples == 0) {
            0.0
        } else {
            draft.faceVisibleSamples.toDouble() / draft.validSamples
        }
        val validCoverage = draft.validSamples.toDouble() / expectedSamples
        val dominantReason = draft.reasonCounts.maxByOrNull { it.value }?.key
        val fallbackReason = if (draft.sampleCount == 0) {
            ClassroomFocusReason.SAMPLING_INTERRUPTED
        } else {
            ClassroomFocusReason.INSUFFICIENT_SAMPLES
        }
        val (verdict, unavailableReason) = when {
            validCoverage < ClassroomFocusObservationConfig.MIN_VALID_SAMPLE_COVERAGE ->
                ClassroomObservationVerdict.UNOBSERVABLE to (dominantReason ?: fallbackReason)
            draft.faceVisibleSamples == 0 ->
                ClassroomObservationVerdict.UNOBSERVABLE to ClassroomFocusReason.NO_FACE
            faceRatio < ClassroomFocusObservationConfig.MIN_FACE_VISIBLE_RATIO ->
                ClassroomObservationVerdict.UNOBSERVABLE to ClassroomFocusReason.INSUFFICIENT_FACE
            else -> ClassroomObservationVerdict.OBSERVABLE to null
        }

        return ClassroomObservationWindow(
            index = draft.index,
            startOffsetMs = startOffset,
            endOffsetMs = endOffset,
            complete = complete,
            validSampleCount = draft.validSamples,
            invalidSampleCount = draft.invalidSamples,
            faceVisibleSampleCount = draft.faceVisibleSamples,
            faceVisibleRatio = faceRatio,
            yaw = draft.yaw.stats(),
            pitch = draft.pitch.stats(),
            stageCounts = draft.stageCounts.toSortedMap(),
            dominantStage = draft.stageCounts.maxByOrNull { it.value }?.key,
            manualPageTurns = pageTurns,
            quizSubmissions = submissions,
            questions = questions,
            reasonCounts = draft.reasonCounts.toSortedMap(compareBy { it.code }),
            verdict = verdict,
            unavailableReason = unavailableReason,
        )
    }
}

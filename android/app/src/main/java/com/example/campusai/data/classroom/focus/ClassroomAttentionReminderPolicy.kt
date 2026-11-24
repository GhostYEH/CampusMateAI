package com.example.campusai.data.classroom.focus

/**
 * 学生提醒的纯规则：连续证据、讲解/测验抑制、冷却、暂停与反馈。
 *
 * 全部使用 10 秒窗口偏移，便于用连续窗口回放验证阈值、冷却和实际提示延迟；
 * 不依赖真实时钟，也不把提醒写成专注度评分或心理判断。
 */
data class ClassroomAttentionReminder(
    val windowIndex: Int,
    val startOffsetMs: Long,
    val endOffsetMs: Long,
    val probability: Double,
    val modelVersion: String,
)

data class ClassroomAttentionReminderState(
    val enabled: Boolean = false,
    val preview: Boolean = false,
    val paused: Boolean = false,
    val snoozeUntilOffsetMs: Long? = null,
    /** 上一条提醒对应窗口的结束偏移；首条提醒前为 null，不能用 -1 参与冷却比较。 */
    val lastAlertEndOffsetMs: Long? = null,
    val lastWindowEndOffsetMs: Long? = null,
    val consecutiveWindows: Int = 0,
    val reminder: ClassroomAttentionReminder? = null,
    val notice: String? = null,
    val lastProbability: Double? = null,
    val falsePositiveCount: Int = 0,
    val noteTakingCount: Int = 0,
) {
    val processing: Boolean get() = enabled || preview
}

object ClassroomAttentionReminderPolicy {
    const val CONSECUTIVE_WINDOWS = 2
    const val COOLDOWN_MS = 120_000L
    const val NOTE_TAKING_SNOOZE_MS = 300_000L
    const val FALSE_POSITIVE_SNOOZE_MS = 600_000L
    val SUPPRESSED_STAGES = setOf("lecture", "quiz")

    fun initial(): ClassroomAttentionReminderState = ClassroomAttentionReminderState()

    fun setEnabled(
        state: ClassroomAttentionReminderState,
        enabled: Boolean,
    ): ClassroomAttentionReminderState = state.copy(
        enabled = enabled,
        preview = false,
        paused = false,
        snoozeUntilOffsetMs = null,
        consecutiveWindows = 0,
        reminder = null,
        notice = if (enabled) "课堂提醒已开启，只在本机判断" else null,
    )

    fun setPreview(
        state: ClassroomAttentionReminderState,
        preview: Boolean,
    ): ClassroomAttentionReminderState = state.copy(
        preview = preview,
        enabled = false,
        paused = false,
        snoozeUntilOffsetMs = null,
        consecutiveWindows = 0,
        reminder = null,
        notice = if (preview) "调试预览：测试权重不参与正式判断" else null,
    )

    fun reset(state: ClassroomAttentionReminderState): ClassroomAttentionReminderState =
        ClassroomAttentionReminderState(
            falsePositiveCount = state.falsePositiveCount,
            noteTakingCount = state.noteTakingCount,
        )

    fun onWindow(
        state: ClassroomAttentionReminderState,
        prediction: ClassroomAttentionPrediction?,
        window: ClassroomObservationWindow,
    ): ClassroomAttentionReminderState {
        val previousEnd = state.lastWindowEndOffsetMs
        if (!window.complete || (previousEnd != null && window.startOffsetMs < previousEnd)) return state
        val current = state.copy(
            lastWindowEndOffsetMs = window.endOffsetMs,
            lastProbability = prediction?.probability,
        )
        val snoozed = current.snoozeUntilOffsetMs?.let { window.endOffsetMs < it } == true
        if (!current.processing || current.paused || snoozed || prediction == null ||
            !prediction.offTask || window.dominantStage in SUPPRESSED_STAGES
        ) {
            return current.copy(consecutiveWindows = 0)
        }
        val run = if (window.startOffsetMs == previousEnd) current.consecutiveWindows + 1 else 1
        if (run < CONSECUTIVE_WINDOWS) {
            return current.copy(consecutiveWindows = run)
        }
        val cooldownUntil = current.lastAlertEndOffsetMs?.plus(COOLDOWN_MS)
        if (cooldownUntil != null && window.endOffsetMs < cooldownUntil) {
            return current.copy(consecutiveWindows = run)
        }
        return current.copy(
            consecutiveWindows = 0,
            lastAlertEndOffsetMs = window.endOffsetMs,
            reminder = ClassroomAttentionReminder(
                windowIndex = window.index,
                startOffsetMs = window.startOffsetMs,
                endOffsetMs = window.endOffsetMs,
                probability = prediction.probability,
                modelVersion = prediction.modelVersion,
            ),
            notice = null,
        )
    }

    fun dismiss(state: ClassroomAttentionReminderState): ClassroomAttentionReminderState =
        state.copy(reminder = null)

    fun pause(state: ClassroomAttentionReminderState): ClassroomAttentionReminderState =
        state.copy(
            paused = true,
            reminder = null,
            consecutiveWindows = 0,
            notice = "已暂停本堂课堂提醒",
        )

    fun resume(state: ClassroomAttentionReminderState): ClassroomAttentionReminderState =
        state.copy(
            paused = false,
            snoozeUntilOffsetMs = null,
            consecutiveWindows = 0,
            notice = "课堂提醒已恢复",
        )

    fun noteTaking(
        state: ClassroomAttentionReminderState,
        atOffsetMs: Long,
    ): ClassroomAttentionReminderState = state.copy(
        reminder = null,
        consecutiveWindows = 0,
        snoozeUntilOffsetMs = atOffsetMs + NOTE_TAKING_SNOOZE_MS,
        noteTakingCount = state.noteTakingCount + 1,
        notice = "已记录「我在记笔记」，5 分钟内不再提醒",
    )

    fun falsePositive(
        state: ClassroomAttentionReminderState,
        atOffsetMs: Long,
    ): ClassroomAttentionReminderState = state.copy(
        reminder = null,
        consecutiveWindows = 0,
        snoozeUntilOffsetMs = atOffsetMs + FALSE_POSITIVE_SNOOZE_MS,
        falsePositiveCount = state.falsePositiveCount + 1,
        notice = "已记录误报，10 分钟内不再提醒",
    )
}

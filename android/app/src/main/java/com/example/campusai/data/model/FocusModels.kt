package com.example.campusai.data.model

/** 番茄钟模式。 */
enum class FocusMode(val minutes: Int, val label: String) {
    FOCUS(25, "专注"),
    SHORT_BREAK(5, "短休息"),
    LONG_BREAK(15, "长休息");

    val totalSeconds: Int get() = minutes * 60

    companion object {
        fun byName(name: String?): FocusMode = entries.firstOrNull { it.name == name } ?: FOCUS
    }
}

/** 一次完成的专注 / 休息记录。 */
data class FocusRecord(
    val id: Long,
    val date: String,
    val mode: String,
    val plannedMinutes: Int,
    val actualMinutes: Int,
    val finished: Boolean,
    val endedAt: String,
    val observationSummary: FocusSessionSummary? = null,
)

/** 番茄钟持久化状态，用于页面退出 / 应用重启后恢复。 */
data class FocusTimerState(
    val mode: String,
    val remainingSeconds: Int,
    val running: Boolean,
    val savedAtEpochMillis: Long,
) {
    /** 根据保存时刻推算当前剩余秒数（运行中按墙钟流逝）。 */
    fun currentRemaining(nowMillis: Long): Int {
        if (!running) return remainingSeconds
        val elapsed = ((nowMillis - savedAtEpochMillis) / 1000).toInt()
        return (remainingSeconds - elapsed).coerceAtLeast(0)
    }
}

/** 今日统计。 */
data class FocusStats(
    val todayMinutes: Int,
    val todayCount: Int,
    val streakDays: Int,
    val goalMinutes: Int,
)

/** 本地持久化快照。 */
data class FocusSnapshot(
    val records: List<FocusRecord> = emptyList(),
    val timer: FocusTimerState? = null,
    val goalMinutes: Int = 60,
)

/** 单次本机辅助观察的结构化摘要；不含照片、视频或逐帧结果。 */
data class FocusSessionSummary(
    val actualFocusMinutes: Int,
    val noFaceEventCount: Int,
    val possibleDistractionDurationSeconds: Long,
    val breakSuggestionCount: Int,
    val stableExpressionDistribution: Map<String, Int>,
    val modelVersion: String,
)

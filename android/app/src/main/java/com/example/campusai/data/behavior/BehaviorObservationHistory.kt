package com.example.campusai.data.behavior

private const val FIVE_MINUTES_MS = 5 * 60 * 1_000L

data class BehaviorObservationSegment(val state: LearningContinuityState, val startedAtMs: Long)
data class BehaviorObservationWindowSegment(val state: LearningContinuityState, val durationMs: Long)

data class BehaviorObservationSummary(
    val sessionElapsedMs: Long,
    val recentSegments: List<BehaviorObservationWindowSegment>,
    val recentStudyMs: Long,
    val recentPausedMs: Long,
    val totalStudyMs: Long,
    val totalPausedMs: Long,
    val longestContinuousStudyMs: Long,
    val currentContinuousStudyMs: Long,
    val meaningfulSwitchCount: Int,
)

/** UI-only, in-memory product-state history for one Focus session. */
data class BehaviorObservationSnapshot(
    val sessionStartedAtMs: Long = 0L,
    val segments: List<BehaviorObservationSegment> = emptyList(),
) {
    fun summary(nowMs: Long, windowMs: Long = FIVE_MINUTES_MS): BehaviorObservationSummary {
        if (segments.isEmpty() || nowMs <= sessionStartedAtMs) {
            return BehaviorObservationSummary(0L, emptyList(), 0L, 0L, 0L, 0L, 0L, 0L, 0)
        }
        val completed = segments.mapIndexed { index, segment ->
            segment to (segments.getOrNull(index + 1)?.startedAtMs ?: nowMs).coerceAtLeast(segment.startedAtMs)
        }
        val windowStart = (nowMs - windowMs).coerceAtLeast(sessionStartedAtMs)
        val recent = completed.mapNotNull { (segment, endedAtMs) ->
            val start = segment.startedAtMs.coerceAtLeast(windowStart)
            val end = endedAtMs.coerceAtMost(nowMs)
            if (end > start) BehaviorObservationWindowSegment(segment.state, end - start) else null
        }
        var totalStudy = 0L
        var totalPaused = 0L
        var longestStudy = 0L
        var currentStudyStart: Long? = null
        var lastMeaningful: Boolean? = null
        var switches = 0
        completed.forEach { (segment, endedAtMs) ->
            val duration = endedAtMs - segment.startedAtMs
            if (segment.state in LEARNING_CONTEXT_STATES) totalStudy += duration
            if (segment.state == LearningContinuityState.PAUSED) totalPaused += duration
            if (segment.state == LearningContinuityState.PAUSED) {
                currentStudyStart?.let { start ->
                    longestStudy = maxOf(longestStudy, segment.startedAtMs - start)
                    currentStudyStart = null
                }
            } else if (segment.state in LEARNING_CONTEXT_STATES && currentStudyStart == null) {
                currentStudyStart = segment.startedAtMs
            }
            val meaningful = when (segment.state) {
                LearningContinuityState.PAUSED -> false
                LearningContinuityState.STUDYING, LearningContinuityState.THINKING_OR_ADJUSTING -> true
                LearningContinuityState.OBSERVING -> null
            }
            if (meaningful != null) {
                if (lastMeaningful != null && lastMeaningful != meaningful) switches += 1
                lastMeaningful = meaningful
            }
        }
        currentStudyStart?.let { longestStudy = maxOf(longestStudy, nowMs - it) }
        val currentStudy = if (segments.last().state in LEARNING_CONTEXT_STATES) nowMs - (currentStudyStart ?: nowMs) else 0L
        return BehaviorObservationSummary(
            sessionElapsedMs = nowMs - sessionStartedAtMs,
            recentSegments = recent,
            recentStudyMs = recent.filter { it.state in LEARNING_CONTEXT_STATES }.sumOf { it.durationMs },
            recentPausedMs = recent.filter { it.state == LearningContinuityState.PAUSED }.sumOf { it.durationMs },
            totalStudyMs = totalStudy,
            totalPausedMs = totalPaused,
            longestContinuousStudyMs = longestStudy,
            currentContinuousStudyMs = currentStudy,
            meaningfulSwitchCount = switches,
        )
    }

    private companion object {
        val LEARNING_CONTEXT_STATES = setOf(LearningContinuityState.STUDYING, LearningContinuityState.THINKING_OR_ADJUSTING)
    }
}

class BehaviorObservationHistory {
    private var sessionStartedAtMs = 0L
    private val segments = mutableListOf<BehaviorObservationSegment>()

    fun reset(startedAtMs: Long) {
        sessionStartedAtMs = startedAtMs
        segments.clear()
        segments += BehaviorObservationSegment(LearningContinuityState.OBSERVING, startedAtMs)
    }

    fun record(state: LearningContinuityState, timestampMs: Long) {
        if (sessionStartedAtMs == 0L) reset(timestampMs)
        if (segments.lastOrNull()?.state != state) {
            segments += BehaviorObservationSegment(state, timestampMs.coerceAtLeast(segments.last().startedAtMs))
        }
    }

    fun snapshot(): BehaviorObservationSnapshot = BehaviorObservationSnapshot(sessionStartedAtMs, segments.toList())
}

package com.example.campusai.data.behavior

/** Product-layer continuity state. It never changes the underlying model labels. */
enum class LearningContinuityState {
    OBSERVING,
    STUDYING,
    THINKING_OR_ADJUSTING,
    PAUSED,
}

data class LearningContinuityConfig(
    val gracePeriodMs: Long = 8_000L,
    val thinkingWindowEndMs: Long = 20_000L,
    val pausedAfterMs: Long = 20_000L,
)

data class LearningContinuityResult(
    val state: LearningContinuityState,
    val continuousStudyStartedAtMs: Long? = null,
)

/** Absorbs short stable-IDLE/UNKNOWN intervals after clearly visible study. */
class LearningContinuityStateMachine(
    private val config: LearningContinuityConfig = LearningContinuityConfig(),
) {
    private var state = LearningContinuityState.OBSERVING
    private var idleStartedAtMs: Long? = null
    private var continuousStudyStartedAtMs: Long? = null

    fun reset() {
        state = LearningContinuityState.OBSERVING
        idleStartedAtMs = null
        continuousStudyStartedAtMs = null
    }

    fun process(displayState: BehaviorDisplayState, timestampMs: Long): LearningContinuityResult {
        when (displayState) {
            is BehaviorDisplayState.Stable -> when (displayState.behavior) {
                StudyBehavior.VISIBLE_STUDY,
                StudyBehavior.READING,
                StudyBehavior.WRITING,
                StudyBehavior.COMPUTER -> {
                    if (state == LearningContinuityState.OBSERVING || state == LearningContinuityState.PAUSED) {
                        continuousStudyStartedAtMs = timestampMs
                    }
                    state = LearningContinuityState.STUDYING
                    idleStartedAtMs = null
                }
                StudyBehavior.IDLE -> handleIdle(timestampMs)
                else -> Unit
            }
            BehaviorDisplayState.Observing,
            BehaviorDisplayState.NoStableBehavior -> Unit // Retain the last explicit product state.
        }
        return LearningContinuityResult(state, continuousStudyStartedAtMs)
    }

    private fun handleIdle(timestampMs: Long) {
        when (state) {
            LearningContinuityState.STUDYING,
            LearningContinuityState.THINKING_OR_ADJUSTING -> {
                val idleStartedAt = idleStartedAtMs ?: timestampMs.also { idleStartedAtMs = it }
                val idleDuration = (timestampMs - idleStartedAt).coerceAtLeast(0L)
                state = when {
                    idleDuration < config.gracePeriodMs -> LearningContinuityState.STUDYING
                    idleDuration < config.thinkingWindowEndMs -> LearningContinuityState.THINKING_OR_ADJUSTING
                    idleDuration >= config.pausedAfterMs -> LearningContinuityState.PAUSED
                    else -> LearningContinuityState.THINKING_OR_ADJUSTING
                }
                if (state == LearningContinuityState.PAUSED) continuousStudyStartedAtMs = null
            }
            LearningContinuityState.OBSERVING,
            LearningContinuityState.PAUSED -> {
                state = LearningContinuityState.PAUSED
                idleStartedAtMs = timestampMs
                continuousStudyStartedAtMs = null
            }
        }
    }
}

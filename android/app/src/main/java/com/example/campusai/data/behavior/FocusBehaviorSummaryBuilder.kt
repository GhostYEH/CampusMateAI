package com.example.campusai.data.behavior

import com.example.campusai.data.model.FocusBehaviorSummary

/** Converts in-memory behavior observations into a privacy-safe session aggregate. */
object FocusBehaviorSummaryBuilder {
    fun build(
        observation: BehaviorObservationSummary,
        events: List<FocusSupervisionEvent>,
        modelVersion: String,
    ): FocusBehaviorSummary {
        val phoneCount = events.count { it.type == FocusSupervisionEventType.PHONE_DISTRACTION }
        val possibleDistractionCount = events.count {
            it.type == FocusSupervisionEventType.POSSIBLE_DISTRACTION ||
                it.type == FocusSupervisionEventType.LONG_LOOK_AWAY
        }
        return FocusBehaviorSummary(
            observedSeconds = observation.sessionElapsedMs.toSeconds(),
            studySeconds = observation.totalStudyMs.toSeconds(),
            pausedSeconds = observation.totalPausedMs.toSeconds(),
            longestContinuousStudySeconds = observation.longestContinuousStudyMs.toSeconds(),
            meaningfulSwitchCount = observation.meaningfulSwitchCount,
            phoneInteractionCount = phoneCount,
            possibleDistractionCount = possibleDistractionCount,
            absentCount = events.count { it.type == FocusSupervisionEventType.STUDENT_ABSENT },
            reminderCount = phoneCount + possibleDistractionCount,
            modelVersion = modelVersion.ifBlank { "MODEL_NOT_AVAILABLE" },
        )
    }

    private fun Long.toSeconds(): Int = (coerceAtLeast(0L) / 1_000L)
        .coerceAtMost(Int.MAX_VALUE.toLong())
        .toInt()
}

package com.example.campusai.data.behavior

import org.junit.Assert.assertEquals
import org.junit.Test

class FocusBehaviorSummaryTest {
    @Test
    fun buildsPrivacySafeAggregateFromObservationAndEvents() {
        val observation = BehaviorObservationSummary(
            sessionElapsedMs = 600_000,
            recentSegments = emptyList(),
            recentStudyMs = 0,
            recentPausedMs = 0,
            totalStudyMs = 510_900,
            totalPausedMs = 60_400,
            longestContinuousStudyMs = 330_800,
            currentContinuousStudyMs = 20_000,
            meaningfulSwitchCount = 2,
        )
        val events = listOf(
            event(FocusSupervisionEventType.PHONE_DISTRACTION),
            event(FocusSupervisionEventType.POSSIBLE_DISTRACTION),
            event(FocusSupervisionEventType.STUDENT_ABSENT),
        )

        val summary = FocusBehaviorSummaryBuilder.build(
            observation = observation,
            events = events,
            modelVersion = "READY_BEHAVIOR_HYBRID_V4",
        )

        assertEquals(600, summary.observedSeconds)
        assertEquals(510, summary.studySeconds)
        assertEquals(60, summary.pausedSeconds)
        assertEquals(330, summary.longestContinuousStudySeconds)
        assertEquals(2, summary.meaningfulSwitchCount)
        assertEquals(1, summary.phoneInteractionCount)
        assertEquals(1, summary.possibleDistractionCount)
        assertEquals(1, summary.absentCount)
        assertEquals(2, summary.reminderCount)
        assertEquals("READY_BEHAVIOR_HYBRID_V4", summary.modelVersion)
    }

    private fun event(type: FocusSupervisionEventType) = FocusSupervisionEvent(
        type = type,
        startedAt = 1L,
        durationMs = 0L,
        confidence = null,
        occurrenceCount = 1,
    )
}

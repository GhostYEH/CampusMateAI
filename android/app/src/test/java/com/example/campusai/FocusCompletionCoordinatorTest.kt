package com.example.campusai

import com.example.campusai.data.model.FocusSessionSummary
import com.example.campusai.ui.screens.focus.FocusCompletionCoordinator
import com.example.campusai.ui.screens.focus.FocusCompletionResult
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class FocusCompletionCoordinatorTest {
    @Test
    fun successfulCompletionCanOnlyBeConsumedOnce() = runBlocking {
        var observationFinishes = 0
        var remoteFinishes = 0
        val summary = FocusSessionSummary(10, 0, 0, 0, emptyMap(), "test")
        val coordinator = FocusCompletionCoordinator(
            finishObservation = {
                observationFinishes += 1
                summary
            },
            finishRemote = { _, _ ->
                remoteFinishes += 1
                true
            },
        )

        assertEquals(
            FocusCompletionResult(summary = summary, completePlanStep = true),
            coordinator.complete(
                actualFocusMinutes = 10,
                selfReport = "状态不错",
                completePlanStep = true,
            ),
        )
        assertNull(coordinator.complete(actualFocusMinutes = 10))
        assertEquals(1, observationFinishes)
        assertEquals(1, remoteFinishes)
    }

    @Test
    fun failedRemoteCompletionCanBeRetried() = runBlocking {
        var remoteFinishes = 0
        val summary = FocusSessionSummary(10, 0, 0, 0, emptyMap(), "test")
        val coordinator = FocusCompletionCoordinator(
            finishObservation = { summary },
            finishRemote = { _, _ ->
                remoteFinishes += 1
                remoteFinishes > 1
            },
        )

        assertNull(coordinator.complete(actualFocusMinutes = 10))
        assertEquals(
            FocusCompletionResult(summary = summary, completePlanStep = false),
            coordinator.complete(actualFocusMinutes = 10, completePlanStep = false),
        )
        assertEquals(2, remoteFinishes)
    }

    @Test
    fun selfReportIsForwardedToRemoteCompletion() = runBlocking {
        var receivedReport: String? = null
        val summary = FocusSessionSummary(10, 0, 0, 0, emptyMap(), "test")
        val coordinator = FocusCompletionCoordinator(
            finishObservation = { summary },
            finishRemote = { _, selfReport ->
                receivedReport = selfReport
                true
            },
        )

        coordinator.complete(actualFocusMinutes = 10, selfReport = "需要更多时间")

        assertEquals("需要更多时间", receivedReport)
    }

    @Test
    fun endingSessionWithoutStepConfirmationDoesNotCompletePlanStep() = runBlocking {
        val summary = FocusSessionSummary(10, 0, 0, 0, emptyMap(), "test")
        val coordinator = FocusCompletionCoordinator(
            finishObservation = { summary },
            finishRemote = { _, _ -> true },
        )

        val result = coordinator.complete(
            actualFocusMinutes = 10,
            completePlanStep = false,
        )

        assertEquals(false, result?.completePlanStep)
    }
}

package com.example.campusai

import com.example.campusai.data.model.FocusSessionSummary
import com.example.campusai.ui.screens.focus.FocusCompletionCoordinator
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
            finishRemote = {
                remoteFinishes += 1
                true
            },
        )

        assertEquals(summary, coordinator.complete(actualFocusMinutes = 10))
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
            finishRemote = {
                remoteFinishes += 1
                remoteFinishes > 1
            },
        )

        assertNull(coordinator.complete(actualFocusMinutes = 10))
        assertEquals(summary, coordinator.complete(actualFocusMinutes = 10))
        assertEquals(2, remoteFinishes)
    }
}

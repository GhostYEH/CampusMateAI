package com.example.campusai

import com.example.campusai.data.model.FocusMode
import com.example.campusai.data.repository.StudySessionSnapshot
import com.example.campusai.ui.screens.focus.resolveFocusTaskId
import org.junit.Assert.assertEquals
import org.junit.Test

class FocusSessionTaskBindingTest {
    @Test
    fun restoredSessionUsesServerTaskInsteadOfRequestedRouteTask() {
        val active = StudySessionSnapshot(
            id = "session-a",
            relatedTaskId = "task-a",
            startedAt = "2026-09-02T10:00:00Z",
            endedAt = null,
            durationSeconds = 0,
            status = "active",
            mode = FocusMode.FOCUS,
        )

        assertEquals("task-a", resolveFocusTaskId(active, "task-b"))
    }

    @Test
    fun unassociatedRestoredSessionDoesNotAdoptRequestedRouteTask() {
        val active = StudySessionSnapshot(
            id = "session-free",
            relatedTaskId = null,
            startedAt = "2026-09-02T10:00:00Z",
            endedAt = null,
            durationSeconds = 0,
            status = "active",
            mode = FocusMode.FOCUS,
        )

        assertEquals(null, resolveFocusTaskId(active, "task-b"))
    }

    @Test
    fun completedSnapshotDoesNotBlockTheRequestedNextTask() {
        val completed = StudySessionSnapshot(
            id = "session-a",
            relatedTaskId = "task-a",
            startedAt = "2026-09-02T10:00:00Z",
            endedAt = "2026-09-02T10:25:00Z",
            durationSeconds = 1_500,
            status = "completed",
            mode = FocusMode.FOCUS,
        )

        assertEquals("task-b", resolveFocusTaskId(completed, "task-b"))
    }
}

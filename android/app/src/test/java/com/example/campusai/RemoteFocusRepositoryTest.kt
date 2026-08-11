package com.example.campusai

import com.example.campusai.data.model.FocusMode
import com.example.campusai.data.repository.RemoteFocusRepository
import com.example.campusai.data.repository.StudySessionSnapshot
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

class RemoteFocusRepositoryTest {

    @Test
    fun `completed server focus sessions derive today's statistics`() {
        val now = Instant.parse("2026-08-11T12:00:00Z")
        val repository = RemoteFocusRepository(
            sessions = listOf(
                StudySessionSnapshot(
                    id = "study-1",
                    startedAt = "2026-08-11T10:00:00Z",
                    endedAt = "2026-08-11T10:25:00Z",
                    durationSeconds = 1_500,
                    status = "completed",
                    mode = FocusMode.FOCUS,
                ),
            ),
            goalMinutes = 60,
            now = { now },
        )

        assertEquals(25, repository.stats.todayMinutes)
        assertEquals(1, repository.stats.todayCount)
        assertEquals(1, repository.stats.streakDays)
        assertTrue(repository.records.single().finished)
    }
}

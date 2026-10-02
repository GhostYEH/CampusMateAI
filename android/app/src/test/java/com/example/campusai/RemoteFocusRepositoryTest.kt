package com.example.campusai

import com.example.campusai.data.model.FocusMode
import com.example.campusai.data.repository.RemoteFocusRepository
import com.example.campusai.data.repository.StudySessionSnapshot
import com.example.campusai.data.remote.StudySessionDto
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
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

    @Test
    fun `completed session retains the student's own reflection for history`() {
        val json = """{"id":"study-2","user_id":"u1","mode":"focus","goal":"完成两道题","started_at":"2026-08-11T10:00:00Z","ended_at":"2026-08-11T10:03:00Z","duration_seconds":180,"status":"completed","self_report":"做完两道习题"}"""
        val dto = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
            .adapter(StudySessionDto::class.java).fromJson(json)!!
        val history = RemoteFocusRepository(
            sessions = listOf(StudySessionSnapshot(
                id = dto.id,
                startedAt = dto.started_at,
                endedAt = dto.ended_at,
                durationSeconds = dto.duration_seconds,
                status = dto.status,
                mode = FocusMode.FOCUS,
                selfReport = dto.self_report,
                goal = dto.goal,
            )),
            goalMinutes = 60,
            now = { Instant.parse("2026-08-11T12:00:00Z") },
        )
        assertEquals("做完两道习题", history.records.single().selfReport)
        assertEquals("完成两道题", history.records.single().goal)
    }

    @Test
    fun `session shorter than a minute stays in history without inflating progress`() {
        val history = RemoteFocusRepository(
            sessions = listOf(StudySessionSnapshot(
                id = "brief",
                startedAt = "2026-08-11T10:00:00Z",
                endedAt = "2026-08-11T10:00:20Z",
                durationSeconds = 20,
                status = "completed",
                mode = FocusMode.FOCUS,
            )),
            goalMinutes = 60,
            now = { Instant.parse("2026-08-11T12:00:00Z") },
        )
        assertEquals(1, history.records.size)
        assertEquals(0, history.stats.todayCount)
        assertEquals(0, history.stats.streakDays)
    }
}

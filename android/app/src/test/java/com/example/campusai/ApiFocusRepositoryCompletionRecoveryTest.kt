package com.example.campusai

import com.example.campusai.data.model.FocusMode
import com.example.campusai.data.model.FocusSessionMode
import com.example.campusai.data.remote.ApiService
import com.example.campusai.data.remote.StudyGoalDto
import com.example.campusai.data.remote.StudySessionDto
import com.example.campusai.data.repository.ApiFocusRepository
import java.lang.reflect.Proxy
import kotlinx.coroutines.runBlocking
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertTrue
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import retrofit2.Response

class ApiFocusRepositoryCompletionRecoveryTest {
    @Test
    fun recoveredSessionRestoresItsSmartGuardMode() = runBlocking {
        val api = Proxy.newProxyInstance(
            ApiService::class.java.classLoader,
            arrayOf(ApiService::class.java),
        ) { _, method, _ ->
            when (method.name) {
                "activeStudySession" -> Response.success(session(status = "active", experienceMode = "SMART_GUARD"))
                else -> error("Unexpected API call: ${method.name}")
            }
        } as ApiService
        val repository = ApiFocusRepository(api)

        val result = repository.refreshActiveSession()

        assertTrue(result.isSuccess)
        assertEquals(FocusSessionMode.SMART_GUARD, repository.activeSession.value?.sessionMode)
    }

    @Test
    fun activeFailureRemainsVisibleWhenHistoryRefreshSucceeds() = runBlocking {
        val api = Proxy.newProxyInstance(
            ApiService::class.java.classLoader,
            arrayOf(ApiService::class.java),
        ) { _, method, _ ->
            when (method.name) {
                "activeStudySession" -> Response.error<StudySessionDto>(
                    503,
                    "unavailable".toResponseBody(),
                )
                "listStudySessions" -> Response.success(emptyList<StudySessionDto>())
                "getDailyStudyGoal" -> Response.success(StudyGoalDto(60, "2026-09-02T10:25:00Z"))
                else -> error("Unexpected API call: ${method.name}")
            }
        } as ApiService
        val repository = ApiFocusRepository(api)

        repository.refreshActiveSession()
        repository.refreshHistoryAndGoal()

        assertTrue(repository.error.value?.contains("恢复专注会话") == true)
    }

    @Test
    fun activeSessionIsPublishedEvenWhenHistoryRefreshFails() = runBlocking {
        val active = session(status = "active")
        val api = Proxy.newProxyInstance(
            ApiService::class.java.classLoader,
            arrayOf(ApiService::class.java),
        ) { _, method, _ ->
            when (method.name) {
                "activeStudySession" -> Response.success(active)
                "listStudySessions" -> Response.error<List<StudySessionDto>>(
                    503,
                    "unavailable".toResponseBody(),
                )
                "getDailyStudyGoal" -> Response.success(StudyGoalDto(60, "2026-09-02T10:25:00Z"))
                else -> error("Unexpected API call: ${method.name}")
            }
        } as ApiService
        val repository = ApiFocusRepository(api)

        val result = repository.refresh()

        assertTrue(result.isFailure)
        assertTrue(repository.activeSession.value?.id == "session-1")
    }

    @Test
    fun completedSessionIsRecoveredWhenFinishResponseWasLost() = runBlocking {
        val active = session(status = "active")
        val completed = session(status = "completed", endedAt = "2026-09-02T10:25:00Z")
        val api = Proxy.newProxyInstance(
            ApiService::class.java.classLoader,
            arrayOf(ApiService::class.java),
        ) { _, method, _ ->
            when (method.name) {
                "createStudySession" -> Response.success(active)
                "finishStudySession" -> Response.error<StudySessionDto>(
                    409,
                    "already completed".toResponseBody(),
                )
                "listStudySessions" -> Response.success(listOf(completed))
                "activeStudySession" -> Response.success<StudySessionDto?>(null)
                "getDailyStudyGoal" -> Response.success(StudyGoalDto(60, "2026-09-02T10:25:00Z"))
                else -> error("Unexpected API call: ${method.name}")
            }
        } as ApiService
        val repository = ApiFocusRepository(api)
        repository.start(FocusMode.FOCUS, "复习", "task-1", 1_500)

        val result = repository.finish()

        assertTrue(result.isSuccess)
        assertTrue(result.getOrNull()?.status == "completed")
        assertTrue(result.getOrNull()?.relatedTaskId == "task-1")
        assertNull(repository.activeSession.value)
    }

    private fun session(
        status: String,
        endedAt: String? = null,
        experienceMode: String = "QUIET",
    ) = StudySessionDto(
        id = "session-1",
        user_id = "user-1",
        mode = "focus",
        experience_mode = experienceMode,
        goal = "复习",
        related_task_id = "task-1",
        started_at = "2026-09-02T10:00:00Z",
        ended_at = endedAt,
        planned_duration_seconds = 1_500,
        duration_seconds = if (endedAt == null) 0 else 1_500,
        status = status,
    )
}

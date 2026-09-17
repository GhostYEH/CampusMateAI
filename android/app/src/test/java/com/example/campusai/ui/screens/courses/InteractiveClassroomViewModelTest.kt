package com.example.campusai.ui.screens.courses

import androidx.lifecycle.SavedStateHandle
import com.example.campusai.data.classroom.ClassroomPhase
import com.example.campusai.data.remote.InteractiveClassroomCompositionDto
import com.example.campusai.data.remote.InteractiveClassroomGenerateRequest
import com.example.campusai.data.remote.InteractiveClassroomGenerateResponse
import com.example.campusai.data.remote.InteractiveClassroomItemDto
import com.example.campusai.data.remote.InteractiveClassroomMaterialDto
import com.example.campusai.data.remote.InteractiveClassroomPlanDto
import com.example.campusai.data.remote.InteractiveClassroomSessionDto
import com.example.campusai.data.remote.InteractiveClassroomStatusDto
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class InteractiveClassroomViewModelTest {
    private val dispatcher = kotlinx.coroutines.test.StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `plan confirmation is required before generate and preserves course materials`() = runTest(dispatcher) {
        val source = FakeDataSource()
        val viewModel = create(source)

        advanceUntilIdle()
        assertEquals("course-42", source.lastPlanCourseId)
        assertEquals(InteractiveClassroomServiceState.AVAILABLE, viewModel.uiState.value.serviceState)
        assertEquals("old-1", viewModel.uiState.value.history.single().sessionId)
        assertFalse(viewModel.uiState.value.confirmed)

        viewModel.generate()
        advanceUntilIdle()
        assertEquals(0, source.generateCalls)

        viewModel.toggleMaterial("notes", true)
        viewModel.updateLearningObjective("掌握链表")
        viewModel.confirmPlan()
        assertTrue(viewModel.uiState.value.confirmed)
        viewModel.generate()
        advanceUntilIdle()

        assertEquals(1, source.generateCalls)
        assertEquals("course-42", source.lastGenerateCourseId)
        assertEquals("course-42", source.lastGenerateRequestCourseId)
        assertEquals(listOf("notes"), source.lastGenerateRequest?.selectedMaterialIds)
        assertEquals(ClassroomPhase.SUCCEEDED, viewModel.uiState.value.progress.phase)
        assertTrue(viewModel.uiState.value.composition != null)
    }

    @Test
    fun `failed retry creates a new session and reports readable failure`() = runTest(dispatcher) {
        val source = FakeDataSource(failFirstJob = true)
        val viewModel = create(source)
        advanceUntilIdle()
        viewModel.confirmPlan()
        viewModel.generate()
        advanceUntilIdle()

        assertEquals(ClassroomPhase.FAILED, viewModel.uiState.value.progress.phase)
        assertTrue(viewModel.uiState.value.progress.retryable)
        viewModel.retry()
        advanceUntilIdle()
        assertEquals(1, source.retryCalls)
        assertEquals("course-42", source.lastRetryCourseId)
        assertEquals(ClassroomPhase.SUCCEEDED, viewModel.uiState.value.progress.phase)
    }

    @Test
    fun `restored session polls the same session without creating again`() = runTest(dispatcher) {
        val source = FakeDataSource()
        val viewModel = InteractiveClassroomViewModel(
            courseId = "course-42",
            dataSource = source,
            savedStateHandle = SavedStateHandle(mapOf("interactive_classroom_session_id:course-42" to "session-restored")),
            wait = {},
        )
        advanceUntilIdle()

        assertEquals(0, source.generateCalls)
        assertEquals(listOf("session-restored"), source.jobSessionIds)
        assertEquals(ClassroomPhase.SUCCEEDED, viewModel.uiState.value.progress.phase)
    }

    @Test
    fun `service status keeps configured available incompatible and degraded distinct`() = runTest(dispatcher) {
        val cases = listOf(
            // 真实后端组合：configured=true 但连不上 → unavailable=true。
            // 修复前会先命中 configured 分支，错误显示成"已配置，正在准备"。
            InteractiveClassroomServiceState.UNAVAILABLE to InteractiveClassroomStatusDto(
                configured = true,
                available = false,
                unavailable = true,
            ),
            InteractiveClassroomServiceState.AVAILABLE to InteractiveClassroomStatusDto(
                enabled = true,
                configured = true,
                available = true,
                browserEmbedAvailable = true,
            ),
            InteractiveClassroomServiceState.INCOMPATIBLE to InteractiveClassroomStatusDto(
                configured = true,
                unavailable = true,
                incompatible = true,
            ),
            // 后端语义：degraded 只在 available=true 时有意义
            InteractiveClassroomServiceState.DEGRADED to InteractiveClassroomStatusDto(
                enabled = true,
                configured = true,
                available = true,
                degraded = true,
                browserEmbedAvailable = true,
            ),
            // 只置 degraded 而没置 available：契约上不会出现，也绝不宣称"可用"
            InteractiveClassroomServiceState.CONFIGURED to InteractiveClassroomStatusDto(
                configured = true,
                degraded = true,
            ),
            InteractiveClassroomServiceState.CONFIGURED to InteractiveClassroomStatusDto(
                configured = true,
                available = false,
                unavailable = false,
            ),
            InteractiveClassroomServiceState.NOT_CONFIGURED to InteractiveClassroomStatusDto(
                configured = false,
                enabled = false,
            ),
        )

        cases.forEach { (expected, status) ->
            val viewModel = create(FakeDataSource(serviceStatus = status))
            advanceUntilIdle()
            assertEquals(status.toString(), expected, viewModel.uiState.value.serviceState)
        }
    }

    @Test
    fun `unavailable outranks configured and incompatible outranks everything`() = runTest(dispatcher) {
        val unavailable = create(
            FakeDataSource(
                serviceStatus = InteractiveClassroomStatusDto(
                    enabled = false,
                    configured = true,
                    available = false,
                    unavailable = true,
                ),
            ),
        )
        advanceUntilIdle()
        assertEquals(InteractiveClassroomServiceState.UNAVAILABLE, unavailable.uiState.value.serviceState)

        val incompatible = create(
            FakeDataSource(
                serviceStatus = InteractiveClassroomStatusDto(
                    enabled = false,
                    configured = true,
                    available = false,
                    unavailable = true,
                    incompatible = true,
                    degraded = true,
                ),
            ),
        )
        advanceUntilIdle()
        assertEquals(InteractiveClassroomServiceState.INCOMPATIBLE, incompatible.uiState.value.serviceState)
    }

    @Test
    fun `every real DTO combination maps to a deterministic state`() = runTest(dispatcher) {
        // 穷尽 (configured, available, unavailable, incompatible, degraded) 的 32 种组合：
        // 任何组合都必须落到一个明确状态，绝不能落回默认值而"看起来没问题"。
        var checked = 0
        for (mask in 0 until 32) {
            val status = InteractiveClassroomStatusDto(
                configured = (mask and 1) != 0,
                available = (mask and 2) != 0,
                unavailable = (mask and 4) != 0,
                incompatible = (mask and 8) != 0,
                degraded = (mask and 16) != 0,
            )
            val viewModel = create(FakeDataSource(serviceStatus = status))
            advanceUntilIdle()
            assertEquals(status.toString(), expectedServiceState(status), viewModel.uiState.value.serviceState)
            checked += 1
        }
        assertEquals(32, checked)
    }

    private fun expectedServiceState(status: InteractiveClassroomStatusDto): InteractiveClassroomServiceState = when {
        status.incompatible -> InteractiveClassroomServiceState.INCOMPATIBLE
        status.unavailable -> InteractiveClassroomServiceState.UNAVAILABLE
        status.available && status.degraded -> InteractiveClassroomServiceState.DEGRADED
        status.available -> InteractiveClassroomServiceState.AVAILABLE
        status.configured -> InteractiveClassroomServiceState.CONFIGURED
        else -> InteractiveClassroomServiceState.NOT_CONFIGURED
    }

    private fun create(source: FakeDataSource) = InteractiveClassroomViewModel(
        courseId = "course-42",
        dataSource = source,
        wait = {},
    )

    private class FakeDataSource(
        private val failFirstJob: Boolean = false,
        private val serviceStatus: InteractiveClassroomStatusDto = InteractiveClassroomStatusDto(
            enabled = true,
            configured = true,
            available = true,
            embedOrigin = "https://classroom.example.edu",
            browserEmbedAvailable = true,
            pollIntervalMs = 1500,
        ),
    ) : InteractiveClassroomDataSource {
        var generateCalls = 0
        var retryCalls = 0
        var lastPlanCourseId: String? = null
        var lastGenerateCourseId: String? = null
        var lastGenerateRequestCourseId: String? = null
        var lastGenerateRequest: InteractiveClassroomGenerateRequest? = null
        var lastRetryCourseId: String? = null
        val jobSessionIds = mutableListOf<String>()

        override suspend fun status(courseId: String) = Result.success(serviceStatus)

        override suspend fun plan(courseId: String, mode: String): Result<InteractiveClassroomPlanDto> {
            lastPlanCourseId = courseId
            return Result.success(
                InteractiveClassroomPlanDto(
                    courseId = courseId,
                    courseName = "数据结构",
                    mode = mode,
                    modeLabel = "练习测验",
                    adaptiveReason = "先练后讲",
                    intentNote = "内容形态只是生成意图",
                    materials = listOf(InteractiveClassroomMaterialDto("notes", "课程讲义", "document")),
                    canGenerate = true,
                ),
            )
        }

        override suspend fun generate(courseId: String, request: InteractiveClassroomGenerateRequest): Result<InteractiveClassroomGenerateResponse> {
            generateCalls += 1
            lastGenerateCourseId = courseId
            lastGenerateRequestCourseId = courseId
            lastGenerateRequest = request
            return Result.success(response("session-1"))
        }

        override suspend fun job(courseId: String, sessionId: String): Result<InteractiveClassroomSessionDto> {
            jobSessionIds += sessionId
            if (failFirstJob && retryCalls == 0) {
                return Result.success(InteractiveClassroomSessionDto(sessionId, courseId, status = "failed", step = "failed", error = "上游暂时不可用", retryable = true))
            }
            return Result.success(InteractiveClassroomSessionDto(sessionId, courseId, status = "succeeded", step = "completed", progress = 100, url = "https://classroom.example.edu/classroom/r1"))
        }

        override suspend fun retry(courseId: String, sessionId: String, request: InteractiveClassroomGenerateRequest): Result<InteractiveClassroomGenerateResponse> {
            retryCalls += 1
            lastRetryCourseId = courseId
            return Result.success(response("session-2"))
        }

        override suspend fun composition(courseId: String, sessionId: String) = Result.success(InteractiveClassroomCompositionDto(classroomId = "r1", sceneTotal = 1))
        override suspend fun history(courseId: String) = Result.success(listOf(InteractiveClassroomItemDto(sessionId = "old-1", mode = "quiz")))

        private fun response(sessionId: String) = InteractiveClassroomGenerateResponse(
            session = InteractiveClassroomSessionDto(sessionId, "course-42", status = "queued", step = "queued"),
            pollIntervalMs = 1500,
        )
    }
}

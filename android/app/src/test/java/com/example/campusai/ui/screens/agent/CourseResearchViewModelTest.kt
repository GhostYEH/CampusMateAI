package com.example.campusai.ui.screens.agent

import com.example.campusai.data.remote.agent.CourseResearchRunCreateRequest
import com.example.campusai.data.remote.agent.CourseResearchRunDto
import com.example.campusai.data.repository.CourseResearchRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.mockito.Mockito
import org.mockito.kotlin.any
import org.mockito.kotlin.whenever

@OptIn(ExperimentalCoroutinesApi::class)
class CourseResearchViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    private lateinit var repository: CourseResearchRepository
    private lateinit var viewModel: CourseResearchViewModel

    @Before fun setUp() {
        Dispatchers.setMain(dispatcher)
        repository = Mockito.mock(CourseResearchRepository::class.java)
        viewModel = CourseResearchViewModel(repository)
    }
    @After fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `submitResearch sets active run on success`() = runTest(dispatcher) {
        val request = CourseResearchRunCreateRequest(question = "什么是递归", mode = "EXPLAIN")
        val run = CourseResearchRunDto(runId = "r1", question = "什么是递归", status = "RUNNING")
        whenever(repository.createRun(any())).thenReturn(Result.success(run))
        viewModel.submitResearch(request)
        advanceUntilIdle()
        assertEquals("r1", viewModel.state.value.activeRun?.runId)
        assertNull(viewModel.state.value.error)
    }

    @Test
    fun `submitResearch sets error on failure`() = runTest(dispatcher) {
        val request = CourseResearchRunCreateRequest(question = "test")
        whenever(repository.createRun(any())).thenReturn(Result.failure(RuntimeException("失败")))
        viewModel.submitResearch(request)
        advanceUntilIdle()
        assertEquals("失败", viewModel.state.value.error)
    }

    @Test
    fun `openRun loads run roles citations and artifacts`() = runTest(dispatcher) {
        val run = CourseResearchRunDto(runId = "r1", status = "PARTIAL")
        whenever(repository.getRun("r1")).thenReturn(Result.success(run))
        whenever(repository.listRoleProgress("r1")).thenReturn(Result.success(emptyList()))
        whenever(repository.listCitations("r1")).thenReturn(Result.success(emptyList()))
        whenever(repository.listArtifacts("r1")).thenReturn(Result.success(emptyList()))
        viewModel.openRun("r1")
        advanceUntilIdle()
        assertNotNull(viewModel.state.value.activeRun)
        assertEquals("PARTIAL", viewModel.state.value.activeRun?.status)
    }

    @Test
    fun `loadRuns populates runs list`() = runTest(dispatcher) {
        val runs = listOf(CourseResearchRunDto(runId = "r1"), CourseResearchRunDto(runId = "r2"))
        whenever(repository.listRuns()).thenReturn(Result.success(runs))
        viewModel.loadRuns()
        advanceUntilIdle()
        assertEquals(2, viewModel.state.value.runs.size)
    }
}
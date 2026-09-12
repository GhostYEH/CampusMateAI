package com.example.campusai.ui.screens.agent

import com.example.campusai.data.remote.agent.AgentRiskLevel
import com.example.campusai.data.remote.agent.NoticeActionStatus
import com.example.campusai.data.remote.agent.NoticeWorkflowActionDto
import com.example.campusai.data.remote.agent.NoticeWorkflowDto
import com.example.campusai.data.repository.NoticeWorkflowRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.mockito.Mockito
import org.mockito.kotlin.any
import org.mockito.kotlin.whenever

@OptIn(ExperimentalCoroutinesApi::class)
class NoticeWorkflowViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    private lateinit var repository: NoticeWorkflowRepository
    private lateinit var viewModel: NoticeWorkflowViewModel

    @Before fun setUp() {
        Dispatchers.setMain(dispatcher)
        repository = Mockito.mock(NoticeWorkflowRepository::class.java)
        viewModel = NoticeWorkflowViewModel(repository)
    }
    @After fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `createWorkflowFromText sets active workflow on success`() = runTest(dispatcher) {
        val workflow = NoticeWorkflowDto(workflowId = "w1", noticeId = "n1", status = "ANALYZING")
        whenever(repository.createWorkflowFromText("请提交作业", "manual_input", null)).thenReturn(Result.success(workflow))
        viewModel.updatePastedText("请提交作业")
        viewModel.createWorkflowFromText("请提交作业")
        advanceUntilIdle()
        assertEquals("w1", viewModel.state.value.activeWorkflow?.workflowId)
        assertEquals("", viewModel.state.value.pastedText)
    }

    @Test
    fun `createWorkflowFromText does nothing for blank text`() = runTest(dispatcher) {
        viewModel.createWorkflowFromText("")
        advanceUntilIdle()
        assertNull(viewModel.state.value.activeWorkflow)
    }

    @Test
    fun `approveAction calls repository with APPROVED`() = runTest(dispatcher) {
        val workflow = NoticeWorkflowDto(workflowId = "w1")
        whenever(repository.decideAction(any(), any(), any())).thenReturn(Result.success(
            NoticeWorkflowActionDto(actionId = "a1", status = "APPROVED")
        ))
        whenever(repository.getWorkflow("w1")).thenReturn(Result.success(workflow))
        viewModel.openWorkflow("w1")
        advanceUntilIdle()
        viewModel.approveAction("a1")
        advanceUntilIdle()
        Mockito.verify(repository).decideAction("a1", "APPROVED", null)
    }

    @Test
    fun `rejectAction calls repository with REJECTED`() = runTest(dispatcher) {
        val workflow = NoticeWorkflowDto(workflowId = "w1")
        whenever(repository.decideAction(any(), any(), any())).thenReturn(Result.success(
            NoticeWorkflowActionDto(actionId = "a1", status = "REJECTED")
        ))
        whenever(repository.getWorkflow("w1")).thenReturn(Result.success(workflow))
        viewModel.openWorkflow("w1")
        advanceUntilIdle()
        viewModel.rejectAction("a1")
        advanceUntilIdle()
        Mockito.verify(repository).decideAction("a1", "REJECTED", null)
    }

    @Test
    fun `updatePastedText updates state`() {
        viewModel.updatePastedText("新通知")
        assertEquals("新通知", viewModel.state.value.pastedText)
    }

    @Test
    fun `NoticeActionPresentation classifies AUTO_SAFE correctly`() {
        val action = NoticeWorkflowActionDto(riskLevel = "AUTO_SAFE", status = "APPROVED")
        assertTrue(NoticeActionPresentation.canAutoExecute(action))
        assertTrue(!NoticeActionPresentation.requiresConfirmation(action))
        assertTrue(!NoticeActionPresentation.isManualOnly(action))
    }

    @Test
    fun `NoticeActionPresentation classifies CONFIRM_REQUIRED correctly`() {
        val action = NoticeWorkflowActionDto(riskLevel = "CONFIRM_REQUIRED", status = "PROPOSED")
        assertTrue(!NoticeActionPresentation.canAutoExecute(action))
        assertTrue(NoticeActionPresentation.requiresConfirmation(action))
        assertTrue(!NoticeActionPresentation.isManualOnly(action))
    }

    @Test
    fun `NoticeActionPresentation classifies MANUAL_ONLY correctly`() {
        val action = NoticeWorkflowActionDto(riskLevel = "MANUAL_ONLY", status = "PROPOSED")
        assertTrue(NoticeActionPresentation.isManualOnly(action))
        assertTrue(!NoticeActionPresentation.canAutoExecute(action))
    }

    @Test
    fun `NoticeActionPresentation handles UNKNOWN risk conservatively`() {
        val action = NoticeWorkflowActionDto(riskLevel = "FUTURE_RISK", status = "PROPOSED")
        assertTrue(!NoticeActionPresentation.canAutoExecute(action))
        assertTrue(!NoticeActionPresentation.requiresConfirmation(action))
        assertTrue(!NoticeActionPresentation.isManualOnly(action))
    }
}
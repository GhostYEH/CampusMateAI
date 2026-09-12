package com.example.campusai.ui.screens.agent

import com.example.campusai.data.remote.agent.FinalReviewAdjustmentProposalDto
import com.example.campusai.data.remote.agent.FinalReviewCampaignDto
import com.example.campusai.data.remote.agent.FinalReviewDailyAgendaDto
import com.example.campusai.data.remote.agent.FinalReviewPlanVersionDto
import com.example.campusai.data.repository.FinalReviewRepository
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
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.mockito.Mockito
import org.mockito.kotlin.any
import org.mockito.kotlin.whenever

@OptIn(ExperimentalCoroutinesApi::class)
class FinalReviewViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    private lateinit var repository: FinalReviewRepository
    private lateinit var viewModel: FinalReviewViewModel

    @Before fun setUp() {
        Dispatchers.setMain(dispatcher)
        repository = Mockito.mock(FinalReviewRepository::class.java)
        viewModel = FinalReviewViewModel(repository)
    }
    @After fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `loadCampaigns updates state with campaigns`() = runTest(dispatcher) {
        val campaigns = listOf(FinalReviewCampaignDto(campaignId = "c1", status = "active"))
        whenever(repository.listCampaigns()).thenReturn(Result.success(campaigns))
        viewModel.loadCampaigns()
        advanceUntilIdle()
        assertEquals(campaigns, viewModel.state.value.campaigns)
        assertNull(viewModel.state.value.error)
    }

    @Test
    fun `loadCampaigns sets error on failure`() = runTest(dispatcher) {
        whenever(repository.listCampaigns()).thenReturn(Result.failure(RuntimeException("网络错误")))
        viewModel.loadCampaigns()
        advanceUntilIdle()
        assertEquals("网络错误", viewModel.state.value.error)
    }

    @Test
    fun `openCampaign loads campaign versions agenda and proposals`() = runTest(dispatcher) {
        val campaign = FinalReviewCampaignDto(campaignId = "c1", currentPlanVersion = 2)
        val versions = listOf(FinalReviewPlanVersionDto(version = 1), FinalReviewPlanVersionDto(version = 2))
        val agenda = FinalReviewDailyAgendaDto(date = "2026-09-13")
        val proposals = listOf(FinalReviewAdjustmentProposalDto(proposalId = "p1", status = "PENDING"))
        whenever(repository.getCampaign("c1")).thenReturn(Result.success(campaign))
        whenever(repository.listPlanVersions("c1")).thenReturn(Result.success(versions))
        whenever(repository.getTodayAgenda("c1")).thenReturn(Result.success(agenda))
        whenever(repository.listAdjustmentProposals("c1")).thenReturn(Result.success(proposals))
        viewModel.openCampaign("c1")
        advanceUntilIdle()
        assertEquals("c1", viewModel.state.value.activeCampaign?.campaignId)
        assertEquals(2, viewModel.state.value.planVersions.size)
        assertNotNull(viewModel.state.value.todayAgenda)
        assertEquals(1, viewModel.state.value.adjustmentProposals.size)
    }

    @Test
    fun `decideProposal refreshes campaign after decision`() = runTest(dispatcher) {
        val campaign = FinalReviewCampaignDto(campaignId = "c1")
        whenever(repository.decideAdjustment(any(), any(), any())).thenReturn(Result.success(Unit))
        whenever(repository.getCampaign("c1")).thenReturn(Result.success(campaign))
        whenever(repository.listPlanVersions("c1")).thenReturn(Result.success(emptyList()))
        whenever(repository.getTodayAgenda("c1")).thenReturn(Result.success(FinalReviewDailyAgendaDto()))
        whenever(repository.listAdjustmentProposals("c1")).thenReturn(Result.success(emptyList()))
        // 先设置 activeCampaign
        viewModel.openCampaign("c1")
        advanceUntilIdle()
        viewModel.decideProposal("p1", "APPROVED")
        advanceUntilIdle()
        Mockito.verify(repository).decideAdjustment("p1", "APPROVED", null)
    }

    @Test
    fun `clearError removes error`() = runTest(dispatcher) {
        whenever(repository.listCampaigns()).thenReturn(Result.failure(RuntimeException("err")))
        viewModel.loadCampaigns()
        advanceUntilIdle()
        assertTrue(viewModel.state.value.error != null)
        viewModel.clearError()
        assertNull(viewModel.state.value.error)
    }
}
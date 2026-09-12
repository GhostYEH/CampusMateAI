package com.example.campusai.ui.screens.agent

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.campusai.data.remote.agent.AgentEventDto
import com.example.campusai.data.remote.agent.AgentRunStatus
import com.example.campusai.data.remote.agent.FinalReviewAdjustmentProposalDto
import com.example.campusai.data.remote.agent.FinalReviewCampaignCreateRequest
import com.example.campusai.data.remote.agent.FinalReviewCampaignDto
import com.example.campusai.data.remote.agent.FinalReviewDailyAgendaDto
import com.example.campusai.data.remote.agent.FinalReviewEvidenceRequest
import com.example.campusai.data.remote.agent.FinalReviewPlanVersionDto
import com.example.campusai.data.repository.FinalReviewRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class FinalReviewUiState(
    val loading: Boolean = false,
    val campaigns: List<FinalReviewCampaignDto> = emptyList(),
    val activeCampaign: FinalReviewCampaignDto? = null,
    val planVersions: List<FinalReviewPlanVersionDto> = emptyList(),
    val todayAgenda: FinalReviewDailyAgendaDto? = null,
    val adjustmentProposals: List<FinalReviewAdjustmentProposalDto> = emptyList(),
    val events: List<AgentEventDto> = emptyList(),
    val error: String? = null,
    val generating: Boolean = false,
)

class FinalReviewViewModel(
    private val repository: FinalReviewRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(FinalReviewUiState())
    val state: StateFlow<FinalReviewUiState> = _state.asStateFlow()

    fun loadCampaigns() = viewModelScope.launch {
        _state.update { it.copy(loading = true, error = null) }
        repository.listCampaigns()
            .onSuccess { campaigns -> _state.update { it.copy(loading = false, campaigns = campaigns) } }
            .onFailure { e -> _state.update { it.copy(loading = false, error = e.message) } }
    }

    fun createCampaign(request: FinalReviewCampaignCreateRequest) = viewModelScope.launch {
        _state.update { it.copy(loading = true, error = null) }
        repository.createCampaign(request)
            .onSuccess { campaign -> _state.update { it.copy(loading = false, activeCampaign = campaign) } }
            .onFailure { e -> _state.update { it.copy(loading = false, error = e.message) } }
    }

    fun openCampaign(campaignId: String) = viewModelScope.launch {
        _state.update { it.copy(loading = true, error = null) }
        val campaign = repository.getCampaign(campaignId).getOrNull()
        val versions = repository.listPlanVersions(campaignId).getOrDefault(emptyList())
        val agenda = repository.getTodayAgenda(campaignId).getOrNull()
        val proposals = repository.listAdjustmentProposals(campaignId).getOrDefault(emptyList())
        _state.update {
            it.copy(
                loading = false,
                activeCampaign = campaign,
                planVersions = versions,
                todayAgenda = agenda,
                adjustmentProposals = proposals,
            )
        }
    }

    fun generatePlan(campaignId: String) = viewModelScope.launch {
        _state.update { it.copy(generating = true, error = null) }
        repository.generatePlan(campaignId)
            .onSuccess { _state.update { it.copy(generating = false) } }
            .onFailure { e -> _state.update { it.copy(generating = false, error = e.message) } }
    }

    fun activatePlan(campaignId: String) = viewModelScope.launch {
        repository.activatePlan(campaignId)
            .onFailure { e -> _state.update { it.copy(error = e.message) } }
        openCampaign(campaignId)
    }

    fun completeItem(itemId: String, evidence: FinalReviewEvidenceRequest) = viewModelScope.launch {
        repository.completeDailyItem(itemId, evidence)
            .onFailure { e -> _state.update { it.copy(error = e.message) } }
        _state.value.activeCampaign?.let { openCampaign(it.campaignId) }
    }

    fun analyzeAdjustments(campaignId: String) = viewModelScope.launch {
        repository.analyzeAdjustments(campaignId)
            .onFailure { e -> _state.update { it.copy(error = e.message) } }
        repository.listAdjustmentProposals(campaignId)
            .onSuccess { proposals -> _state.update { it.copy(adjustmentProposals = proposals) } }
    }

    fun decideProposal(proposalId: String, decision: String, reason: String? = null) = viewModelScope.launch {
        repository.decideAdjustment(proposalId, decision, reason)
            .onFailure { e -> _state.update { it.copy(error = e.message) } }
        _state.value.activeCampaign?.let { openCampaign(it.campaignId) }
    }

    fun observeEvents(campaignId: String) = viewModelScope.launch {
        repository.streamCampaignEvents(campaignId).collect { sseEvent ->
            when (sseEvent) {
                is com.example.campusai.data.remote.agent.AgentSseClient.SseEvent.Event -> {
                    _state.update { it.copy(events = it.events + sseEvent.event) }
                    if (sseEvent.event.runStatus() == AgentRunStatus.SUCCEEDED) {
                        openCampaign(campaignId)
                    }
                }
                is com.example.campusai.data.remote.agent.AgentSseClient.SseEvent.Error -> {
                    _state.update { it.copy(error = sseEvent.cause.message) }
                }
            }
        }
    }

    fun clearError() = _state.update { it.copy(error = null) }
}
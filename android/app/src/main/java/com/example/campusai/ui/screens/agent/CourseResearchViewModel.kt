package com.example.campusai.ui.screens.agent

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.campusai.data.remote.agent.AgentArtifactDto
import com.example.campusai.data.remote.agent.AgentEventDto
import com.example.campusai.data.remote.agent.AgentRunStatus
import com.example.campusai.data.remote.agent.CourseResearchCitationDto
import com.example.campusai.data.remote.agent.CourseResearchRoleProgressDto
import com.example.campusai.data.remote.agent.CourseResearchRunCreateRequest
import com.example.campusai.data.remote.agent.CourseResearchRunDto
import com.example.campusai.data.repository.CourseResearchRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class CourseResearchUiState(
    val loading: Boolean = false,
    val runs: List<CourseResearchRunDto> = emptyList(),
    val activeRun: CourseResearchRunDto? = null,
    val roleProgress: List<CourseResearchRoleProgressDto> = emptyList(),
    val citations: List<CourseResearchCitationDto> = emptyList(),
    val artifacts: List<AgentArtifactDto> = emptyList(),
    val events: List<AgentEventDto> = emptyList(),
    val error: String? = null,
)

class CourseResearchViewModel(
    private val repository: CourseResearchRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(CourseResearchUiState())
    val state: StateFlow<CourseResearchUiState> = _state.asStateFlow()

    fun loadRuns() = viewModelScope.launch {
        _state.update { it.copy(loading = true, error = null) }
        repository.listRuns()
            .onSuccess { runs -> _state.update { it.copy(loading = false, runs = runs) } }
            .onFailure { e -> _state.update { it.copy(loading = false, error = e.message) } }
    }

    fun submitResearch(request: CourseResearchRunCreateRequest) = viewModelScope.launch {
        _state.update { it.copy(loading = true, error = null) }
        repository.createRun(request)
            .onSuccess { run -> _state.update { it.copy(loading = false, activeRun = run) } }
            .onFailure { e -> _state.update { it.copy(loading = false, error = e.message) } }
    }

    fun openRun(runId: String) = viewModelScope.launch {
        _state.update { it.copy(loading = true, error = null) }
        val run = repository.getRun(runId).getOrNull()
        val roles = repository.listRoleProgress(runId).getOrDefault(emptyList())
        val cites = repository.listCitations(runId).getOrDefault(emptyList())
        val arts = repository.listArtifacts(runId).getOrDefault(emptyList())
        _state.update {
            it.copy(
                loading = false,
                activeRun = run,
                roleProgress = roles,
                citations = cites,
                artifacts = arts,
            )
        }
    }

    fun cancelRun(runId: String) = viewModelScope.launch {
        repository.cancelRun(runId)
            .onFailure { e -> _state.update { it.copy(error = e.message) } }
        openRun(runId)
    }

    fun observeEvents(runId: String) = viewModelScope.launch {
        repository.streamRunEvents(runId).collect { sseEvent ->
            when (sseEvent) {
                is com.example.campusai.data.remote.agent.AgentSseClient.SseEvent.Event -> {
                    _state.update { it.copy(events = it.events + sseEvent.event) }
                    val status = sseEvent.event.runStatus()
                    if (status == AgentRunStatus.SUCCEEDED || status == AgentRunStatus.PARTIAL) {
                        openRun(runId)
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
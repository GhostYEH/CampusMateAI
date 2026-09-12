package com.example.campusai.ui.screens.agent

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.campusai.data.remote.agent.AgentRiskLevel
import com.example.campusai.data.remote.agent.NoticeActionStatus
import com.example.campusai.data.remote.agent.NoticeWorkflowActionDto
import com.example.campusai.data.remote.agent.NoticeWorkflowDto
import com.example.campusai.data.remote.agent.NotificationSourceDto
import com.example.campusai.data.repository.NoticeWorkflowRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class NoticeWorkflowUiState(
    val loading: Boolean = false,
    val sources: List<NotificationSourceDto> = emptyList(),
    val activeWorkflow: NoticeWorkflowDto? = null,
    val pastedText: String = "",
    val error: String? = null,
)

class NoticeWorkflowViewModel(
    private val repository: NoticeWorkflowRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(NoticeWorkflowUiState())
    val state: StateFlow<NoticeWorkflowUiState> = _state.asStateFlow()

    fun loadSources() = viewModelScope.launch {
        _state.update { it.copy(loading = true, error = null) }
        repository.listSources()
            .onSuccess { sources -> _state.update { it.copy(loading = false, sources = sources) } }
            .onFailure { e -> _state.update { it.copy(loading = false, error = e.message) } }
    }

    fun updatePastedText(text: String) = _state.update { it.copy(pastedText = text) }

    fun createWorkflowFromText(content: String) = viewModelScope.launch {
        if (content.isBlank()) return@launch
        _state.update { it.copy(loading = true, error = null) }
        repository.createWorkflowFromText(content = content, sourceName = "manual_input")
            .onSuccess { workflow -> _state.update { it.copy(loading = false, activeWorkflow = workflow, pastedText = "") } }
            .onFailure { e -> _state.update { it.copy(loading = false, error = e.message) } }
    }

    fun openWorkflow(workflowId: String) = viewModelScope.launch {
        _state.update { it.copy(loading = true, error = null) }
        repository.getWorkflow(workflowId)
            .onSuccess { workflow -> _state.update { it.copy(loading = false, activeWorkflow = workflow) } }
            .onFailure { e -> _state.update { it.copy(loading = false, error = e.message) } }
    }

    fun reanalyze(workflowId: String) = viewModelScope.launch {
        repository.reanalyze(workflowId)
            .onSuccess { workflow -> _state.update { it.copy(activeWorkflow = workflow) } }
            .onFailure { e -> _state.update { it.copy(error = e.message) } }
    }

    fun approveAction(actionId: String, reason: String? = null) = viewModelScope.launch {
        repository.decideAction(actionId, "APPROVED", reason)
            .onFailure { e -> _state.update { it.copy(error = e.message) } }
        refreshActiveWorkflow()
    }

    fun rejectAction(actionId: String, reason: String? = null) = viewModelScope.launch {
        repository.decideAction(actionId, "REJECTED", reason)
            .onFailure { e -> _state.update { it.copy(error = e.message) } }
        refreshActiveWorkflow()
    }

    fun executeAction(actionId: String) = viewModelScope.launch {
        repository.executeAction(actionId)
            .onFailure { e -> _state.update { it.copy(error = e.message) } }
        refreshActiveWorkflow()
    }

    private fun refreshActiveWorkflow() = viewModelScope.launch {
        _state.value.activeWorkflow?.let { workflow ->
            repository.getWorkflow(workflow.workflowId)
                .onSuccess { updated -> _state.update { it.copy(activeWorkflow = updated) } }
        }
    }

    fun clearError() = _state.update { it.copy(error = null) }
}

object NoticeActionPresentation {
    fun canAutoExecute(action: NoticeWorkflowActionDto): Boolean =
        action.risk() == AgentRiskLevel.AUTO_SAFE && action.actionStatus() == NoticeActionStatus.APPROVED

    fun requiresConfirmation(action: NoticeWorkflowActionDto): Boolean =
        action.risk() == AgentRiskLevel.CONFIRM_REQUIRED && action.actionStatus() == NoticeActionStatus.PROPOSED

    fun isManualOnly(action: NoticeWorkflowActionDto): Boolean =
        action.risk() == AgentRiskLevel.MANUAL_ONLY
}
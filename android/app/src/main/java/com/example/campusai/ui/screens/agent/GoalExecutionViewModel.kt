package com.example.campusai.ui.screens.agent

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.campusai.data.remote.agent.AgentJobDto
import com.example.campusai.data.remote.agent.LearningPlanSummaryDto
import com.example.campusai.data.remote.agent.StudentGoalDto
import com.example.campusai.data.repository.AgentRuntimeRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class GoalExecutionUiState(
    val loading: Boolean = false,
    val goals: List<StudentGoalDto> = emptyList(),
    val jobs: List<AgentJobDto> = emptyList(),
    val summary: LearningPlanSummaryDto? = null,
    val error: String? = null,
)

class GoalExecutionViewModel(private val repository: AgentRuntimeRepository) : ViewModel() {
    private val _state = MutableStateFlow(GoalExecutionUiState())
    val state: StateFlow<GoalExecutionUiState> = _state.asStateFlow()

    fun load() = viewModelScope.launch {
        _state.update { it.copy(loading = true, error = null) }
        val goals = repository.listLearningGoals().getOrElse { emptyList() }
        val jobs = repository.listJobs().getOrElse { emptyList() }
        _state.update { it.copy(loading = false, goals = goals, jobs = jobs) }
        jobs.firstOrNull { it.kind().name == "learning_goal" }
            ?.inputRef?.get("plan_id")?.toString()?.takeIf { it.isNotBlank() }
            ?.let { loadSummary(it) }
    }

    fun createGoal(name: String) = viewModelScope.launch {
        _state.update { it.copy(loading = true, error = null) }
        repository.createLearningGoal(name)
            .onFailure { error -> _state.update { it.copy(loading = false, error = error.message) } }
        load()
    }

    fun generate(goalId: String, minutes: Int) = viewModelScope.launch {
        _state.update { it.copy(loading = true, error = null) }
        repository.createLearningGoalJob(goalId, minutes)
            .onSuccess { job ->
                val planId = job.inputRef["plan_id"]?.toString()
                _state.update { it.copy(loading = false) }
                if (!planId.isNullOrBlank()) loadSummary(planId)
                load()
            }
            .onFailure { error -> _state.update { it.copy(loading = false, error = error.message) } }
    }

    fun confirmPlan() = actOnSummary { repository.confirmPlan(it) }
    fun executePlan() = actOnSummary { repository.executePlan(it) }
    fun replan() = actOnSummary { repository.replan(it) }

    fun control(job: AgentJobDto, action: String) = viewModelScope.launch {
        val runId = job.latestRunId ?: return@launch
        _state.update { it.copy(loading = true, error = null) }
        val result = when (action) {
            "pause" -> repository.pauseRun(runId, "学生在目标中心暂停")
            "resume" -> repository.resumeRun(runId)
            else -> repository.retryRun(runId)
        }
        result.onFailure { error -> _state.update { it.copy(loading = false, error = error.message) } }
        load()
    }

    private fun loadSummary(planId: String) = viewModelScope.launch {
        repository.planSummary(planId)
            .onSuccess { summary -> _state.update { it.copy(summary = summary) } }
            .onFailure { error -> _state.update { it.copy(error = error.message) } }
    }

    private fun actOnSummary(action: suspend (String) -> Result<LearningPlanSummaryDto>) = viewModelScope.launch {
        val planId = _state.value.summary?.planId ?: return@launch
        _state.update { it.copy(loading = true, error = null) }
        action(planId)
            .onSuccess { summary -> _state.update { it.copy(loading = false, summary = summary) } }
            .onFailure { error -> _state.update { it.copy(loading = false, error = error.message) } }
        load()
    }
}

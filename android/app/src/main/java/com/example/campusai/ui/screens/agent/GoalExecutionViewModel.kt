package com.example.campusai.ui.screens.agent

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.campusai.data.remote.agent.AgentJobDto
import com.example.campusai.data.remote.agent.AgentRunStatus
import com.example.campusai.data.remote.agent.LearningPlanSummaryDto
import com.example.campusai.data.remote.agent.StudentGoalDto
import com.example.campusai.data.repository.AgentRuntimeRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

data class GoalExecutionUiState(
    val loading: Boolean = false,
    val goals: List<StudentGoalDto> = emptyList(),
    val jobs: List<AgentJobDto> = emptyList(),
    val summary: LearningPlanSummaryDto? = null,
    val error: String? = null,
    val activeRunId: String? = null,
)

class GoalExecutionViewModel(private val repository: AgentRuntimeRepository) : ViewModel() {
    private val _state = MutableStateFlow(GoalExecutionUiState())
    val state: StateFlow<GoalExecutionUiState> = _state.asStateFlow()
    private var runObservation: Job? = null
    private var observedRunId: String? = null

    fun load() = viewModelScope.launch {
        _state.update { it.copy(loading = true, error = null) }
        val goals = repository.listLearningGoals().getOrElse { emptyList() }
        val jobs = repository.listJobs().getOrElse { emptyList() }
        _state.update { it.copy(loading = false, goals = goals, jobs = jobs) }
        val latest = jobs.firstOrNull { it.kind().name == "learning_goal" }
        if (latest != null) {
            _state.update { it.copy(activeRunId = latest.latestRunId) }
            if (latest.runStatus() == AgentRunStatus.QUEUED || latest.runStatus() == AgentRunStatus.RUNNING) {
                observeRun(latest)
            } else {
                val completedJob = repository.getJob(latest.jobId).getOrNull() ?: latest
                completedJob.inputRef["plan_id"]?.toString()?.takeIf { it.isNotBlank() }
                    ?.let { loadSummary(it) }
            }
        }
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
                _state.update { it.copy(loading = false, activeRunId = job.latestRunId) }
                observeRun(job)
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

    private fun observeRun(job: AgentJobDto) {
        val runId = job.latestRunId ?: return
        if (observedRunId == runId && runObservation?.isActive == true) return
        runObservation?.cancel()
        observedRunId = runId
        runObservation = viewModelScope.launch {
            repository.streamRunEvents(runId).collect { sseEvent ->
                when (sseEvent) {
                    is com.example.campusai.data.remote.agent.AgentSseClient.SseEvent.Event -> {
                        val status = sseEvent.event.runStatus()
                        if (status == AgentRunStatus.SUCCEEDED) {
                            val completed = repository.getJob(job.jobId).getOrElse {
                                _state.update { it.copy(error = "任务已完成，但结果加载失败，请重试") }
                                return@collect
                            }
                            _state.update { current ->
                                current.copy(jobs = current.jobs.map { if (it.jobId == completed.jobId) completed else it })
                            }
                            completed.inputRef["plan_id"]?.toString()?.takeIf { it.isNotBlank() }
                                ?.let { loadSummary(it) }
                                ?: _state.update { it.copy(error = "任务已完成，但计划引用暂不可用，请重试") }
                        } else if (status == AgentRunStatus.FAILED || status == AgentRunStatus.CANCELLED) {
                            _state.update { it.copy(error = "任务未完成，可稍后重试") }
                        }
                    }
                    is com.example.campusai.data.remote.agent.AgentSseClient.SseEvent.Error -> {
                        _state.update { it.copy(error = "任务连接中断，可刷新后重试") }
                    }
                }
            }
        }
    }

    override fun onCleared() {
        runObservation?.cancel()
        super.onCleared()
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

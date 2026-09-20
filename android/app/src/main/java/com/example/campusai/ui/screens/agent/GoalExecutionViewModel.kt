package com.example.campusai.ui.screens.agent

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.campusai.data.remote.agent.AgentJobDto
import com.example.campusai.data.remote.agent.AgentRunStatus
import com.example.campusai.data.remote.agent.LearningPlanSummaryDto
import com.example.campusai.data.remote.agent.AdaptiveInterventionOutcomeDto
import com.example.campusai.data.remote.agent.DataSourceControlDto
import com.example.campusai.data.remote.agent.ForecastDto
import com.example.campusai.data.remote.agent.LearnerStateSnapshotDto
import com.example.campusai.data.remote.agent.ModelTransparencyDto
import com.example.campusai.data.remote.agent.StudentGoalDto
import com.example.campusai.data.repository.AgentRuntimeRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

/**
 * 学生世界模型的只读视图状态。
 *
 * 刻意与 [GoalExecutionUiState.error] 分开：世界模型取不到时**不能**把整个
 * 目标/计划区域一起替换成错误，只能在这一块里显示明确的只读降级说明。
 */
data class WorldModelUiState(
    val loading: Boolean = false,
    val snapshots: List<LearnerStateSnapshotDto> = emptyList(),
    val forecasts: List<ForecastDto> = emptyList(),
    val interventionOutcome: AdaptiveInterventionOutcomeDto? = null,
    val dataControls: List<DataSourceControlDto> = emptyList(),
    val transparency: ModelTransparencyDto? = null,
    /** 非空即为只读降级说明；此时页面仍展示其它区域。 */
    val degradedReason: String? = null,
)

data class GoalExecutionUiState(
    val loading: Boolean = false,
    val goals: List<StudentGoalDto> = emptyList(),
    val jobs: List<AgentJobDto> = emptyList(),
    val summary: LearningPlanSummaryDto? = null,
    val error: String? = null,
    val activeRunId: String? = null,
    val worldModel: WorldModelUiState = WorldModelUiState(),
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

    /**
     * 加载世界模型只读视图。
     *
     * 任何一个子请求失败都不抛给调用方：世界模型是只读增强项，缺一块就少显示一块，
     * 并在 `degradedReason` 里说明"已降级"，而不是把整页变成错误。
     */
    fun loadWorldModel() = viewModelScope.launch {
        _state.update { it.copy(worldModel = it.worldModel.copy(loading = true, degradedReason = null)) }

        val snapshots = repository.learnerStateSnapshots("CORE").getOrElse { emptyList() }
        val worldSnapshots = repository.learnerStateSnapshots("WORLD").getOrElse { emptyList() }
        val forecasts = repository.forecasts().getOrElse { emptyList() }
        val controls = repository.dataControls().getOrElse { emptyList() }
        val transparency = repository.modelTransparency().getOrNull()
        val interventions = repository.interventions().getOrElse { emptyList() }
        val current = interventions.firstOrNull { it.status != "SUPERSEDED" }
        val outcome = current?.let { repository.interventionOutcome(it.interventionId).getOrNull() }

        val anythingLoaded = snapshots.isNotEmpty() || worldSnapshots.isNotEmpty() ||
            forecasts.isNotEmpty() || controls.isNotEmpty() || transparency != null
        _state.update {
            it.copy(
                worldModel = WorldModelUiState(
                    loading = false,
                    snapshots = snapshots + worldSnapshots,
                    forecasts = forecasts,
                    interventionOutcome = outcome,
                    dataControls = controls,
                    transparency = transparency,
                    degradedReason = if (anythingLoaded) null else "世界模型暂时不可用，已降级为只读展示",
                ),
            )
        }
    }

    /** 暂停/恢复一个数据源；只影响该来源是否参与投影，不修改任何学习状态。 */
    fun setDataSourceStatus(sourceKey: String, status: String) = viewModelScope.launch {
        repository.setDataSourceStatus(sourceKey, status)
            .onSuccess { controls -> _state.update { it.copy(worldModel = it.worldModel.copy(dataControls = controls)) } }
            .onFailure { error -> _state.update { it.copy(worldModel = it.worldModel.copy(degradedReason = error.message)) } }
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

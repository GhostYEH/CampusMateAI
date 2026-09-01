package com.example.campusai.data.repository

import com.example.campusai.data.focus.goal.FocusGoalPlan
import com.example.campusai.data.focus.goal.toFocusGoalPlan
import com.example.campusai.data.model.FocusMode
import com.example.campusai.data.model.FocusRecord
import com.example.campusai.data.model.FocusSessionSummary
import com.example.campusai.data.model.FocusStats
import com.example.campusai.data.model.FocusBehaviorSummary
import com.example.campusai.data.model.FocusTimerState
import com.example.campusai.data.remote.ApiService
import com.example.campusai.data.remote.StudyGoalUpdateRequest
import com.example.campusai.data.remote.StudySessionCreateRequest
import com.example.campusai.data.remote.StudySessionDto
import com.example.campusai.data.remote.StudySessionFinishRequest
import com.example.campusai.data.remote.TaskBreakdownRequest
import com.example.campusai.data.remote.StudyBehaviorSummaryDto
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.time.Instant

class ApiFocusRepository(private val api: ApiService) : FocusRepository {
    private val _records = MutableStateFlow<List<FocusRecord>>(emptyList())
    override val records: StateFlow<List<FocusRecord>> = _records.asStateFlow()

    private val _timer = MutableStateFlow<FocusTimerState?>(null)
    override val timer: StateFlow<FocusTimerState?> = _timer.asStateFlow()

    private val _stats = MutableStateFlow(FocusStats(0, 0, 0, 60))
    override val stats: StateFlow<FocusStats> = _stats.asStateFlow()

    private val _loading = MutableStateFlow(true)
    override val loading: StateFlow<Boolean> = _loading.asStateFlow()

    private val _activeSession = MutableStateFlow<StudySessionSnapshot?>(null)
    val activeSession: StateFlow<StudySessionSnapshot?> = _activeSession.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    suspend fun refresh(): Result<Unit> = runCatching {
        _loading.value = true
        val completed = api.listStudySessions(status = "completed")
        val active = api.activeStudySession()
        val goal = api.getDailyStudyGoal()
        check(completed.isSuccessful) { requestError("加载专注记录", completed.code()) }
        check(active.isSuccessful) { requestError("恢复专注会话", active.code()) }
        check(goal.isSuccessful) { requestError("加载每日目标", goal.code()) }
        val snapshots = completed.body().orEmpty().map(::toSnapshot)
        val mapped = RemoteFocusRepository(snapshots, goal.body()!!.target_minutes)
        _records.value = mapped.records
        _stats.value = mapped.stats
        _activeSession.value = active.body()?.let(::toSnapshot)
        _error.value = null
    }.onFailure { _error.value = it.message ?: "网络请求失败" }.also {
        _loading.value = false
    }

    suspend fun start(mode: FocusMode, goal: String?, taskId: String?, plannedDurationSeconds: Int = mode.totalSeconds): Result<StudySessionSnapshot> =
        runCatching {
            val response = api.createStudySession(
                StudySessionCreateRequest(mode = mode.toApiMode(), planned_duration_seconds = plannedDurationSeconds, goal = goal, related_task_id = taskId),
            )
            check(response.isSuccessful) { "无法开始专注" }
            toSnapshot(checkNotNull(response.body()))
        }.onSuccess {
            _activeSession.value = it
            _error.value = null
        }.onFailure { _error.value = it.message ?: "网络请求失败" }

    suspend fun pause(): Result<StudySessionSnapshot> = mutateActive { api.pauseStudySession(it.id) }

    suspend fun resume(): Result<StudySessionSnapshot> = mutateActive { api.resumeStudySession(it.id) }

    suspend fun finish(summary: FocusSessionSummary? = null): Result<StudySessionSnapshot> = mutateActive {
        api.finishStudySession(
            it.id,
            StudySessionFinishRequest(behavior_summary = summary?.behaviorSummary?.toDto()),
        )
    }.onSuccess { refresh() }

    suspend fun updateGoal(minutes: Int): Result<Unit> = runCatching {
        val response = api.updateDailyStudyGoal(StudyGoalUpdateRequest(minutes))
        check(response.isSuccessful) { "无法更新每日目标" }
        _stats.value = _stats.value.copy(goalMinutes = checkNotNull(response.body()).target_minutes)
        _error.value = null
    }.onFailure { _error.value = it.message ?: "网络请求失败" }

    suspend fun breakdownGoal(goal: String): Result<FocusGoalPlan> = runCatching {
        val response = api.breakdownStudyGoal(TaskBreakdownRequest(goal = goal.trim()))
        check(response.isSuccessful) { "无法分析目标（${response.code()}）" }
        response.body()?.toFocusGoalPlan() ?: error("目标分析结果为空")
    }.onFailure { _error.value = it.message ?: "目标分析失败" }

    override suspend fun saveTimer(state: FocusTimerState?) = Unit
    override suspend fun setGoal(minutes: Int) { updateGoal(minutes) }
    override suspend fun addRecord(
        mode: FocusMode,
        actualMinutes: Int,
        finished: Boolean,
        observationSummary: FocusSessionSummary?,
    ) = Unit

    private suspend fun mutateActive(
        request: suspend (StudySessionSnapshot) -> retrofit2.Response<StudySessionDto>,
    ): Result<StudySessionSnapshot> = runCatching {
        val current = checkNotNull(_activeSession.value) { "当前没有进行中的专注会话" }
        val response = request(current)
        check(response.isSuccessful) { "无法更新专注会话" }
        toSnapshot(checkNotNull(response.body()))
    }.onSuccess {
        _activeSession.value = it
        _error.value = null
    }.onFailure { _error.value = it.message ?: "网络请求失败" }

    private fun toSnapshot(dto: StudySessionDto) = StudySessionSnapshot(
        id = dto.id,
        startedAt = dto.started_at,
        endedAt = dto.ended_at,
        plannedDurationSeconds = dto.planned_duration_seconds,
        durationSeconds = dto.duration_seconds,
        status = dto.status,
        mode = FocusMode.byName(dto.mode.uppercase()),
        pausedAt = dto.paused_at,
        pauseSeconds = dto.pause_seconds,
        behaviorSummary = dto.behavior_summary?.toDomain(),
    )

    private fun FocusMode.toApiMode() = when (this) {
        FocusMode.FOCUS -> "focus"
        FocusMode.SHORT_BREAK -> "short_break"
        FocusMode.LONG_BREAK -> "long_break"
    }

    private fun requestError(action: String, code: Int): String =
        if (code == 401) "登录已失效，请重新登录后同步专注记录" else "无法$action ($code)"

    private fun FocusBehaviorSummary.toDto() = StudyBehaviorSummaryDto(
        observed_seconds = observedSeconds,
        study_seconds = studySeconds,
        paused_seconds = pausedSeconds,
        longest_continuous_study_seconds = longestContinuousStudySeconds,
        meaningful_switch_count = meaningfulSwitchCount,
        phone_interaction_count = phoneInteractionCount,
        possible_distraction_count = possibleDistractionCount,
        absent_count = absentCount,
        reminder_count = reminderCount,
        model_version = modelVersion,
    )

    private fun StudyBehaviorSummaryDto.toDomain() = FocusBehaviorSummary(
        observedSeconds = observed_seconds,
        studySeconds = study_seconds,
        pausedSeconds = paused_seconds,
        longestContinuousStudySeconds = longest_continuous_study_seconds,
        meaningfulSwitchCount = meaningful_switch_count,
        phoneInteractionCount = phone_interaction_count,
        possibleDistractionCount = possible_distraction_count,
        absentCount = absent_count,
        reminderCount = reminder_count,
        modelVersion = model_version,
    )
}

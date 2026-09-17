package com.example.campusai.ui.screens.courses

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.CreationExtras
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.classroom.ClassroomCompositionText
import com.example.campusai.data.classroom.ClassroomPhase
import com.example.campusai.data.classroom.ClassroomProgressReducer
import com.example.campusai.data.classroom.ClassroomProgressState
import com.example.campusai.data.model.Course
import com.example.campusai.data.remote.ClassroomUrlPolicy
import com.example.campusai.data.remote.InteractiveClassroomCompositionDto
import com.example.campusai.data.remote.InteractiveClassroomGenerateRequest
import com.example.campusai.data.remote.InteractiveClassroomGenerateResponse
import com.example.campusai.data.remote.InteractiveClassroomItemDto
import com.example.campusai.data.remote.InteractiveClassroomPlanDto
import com.example.campusai.data.remote.InteractiveClassroomSessionDto
import com.example.campusai.data.remote.InteractiveClassroomStatusDto
import com.example.campusai.ui.components.GlassButton as Button
import com.example.campusai.ui.components.GlassOutlinedButton as OutlinedButton
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Success
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

interface InteractiveClassroomDataSource {
    suspend fun status(courseId: String): Result<InteractiveClassroomStatusDto>
    suspend fun plan(courseId: String, mode: String): Result<InteractiveClassroomPlanDto>
    suspend fun generate(courseId: String, request: InteractiveClassroomGenerateRequest): Result<InteractiveClassroomGenerateResponse>
    suspend fun job(courseId: String, sessionId: String): Result<InteractiveClassroomSessionDto>
    suspend fun retry(courseId: String, sessionId: String, request: InteractiveClassroomGenerateRequest): Result<InteractiveClassroomGenerateResponse>
    suspend fun composition(courseId: String, sessionId: String): Result<InteractiveClassroomCompositionDto>
    suspend fun history(courseId: String): Result<List<InteractiveClassroomItemDto>>
}

/** Production data source. Every method below is a real CampusMate API call. */
class AppInteractiveClassroomDataSource(
    private val repository: AppRepository,
) : InteractiveClassroomDataSource {
    override suspend fun status(courseId: String): Result<InteractiveClassroomStatusDto> =
        repository.interactiveClassroomStatus(courseId)?.let { Result.success(it) }
            ?: Result.failure(IllegalStateException("互动课堂服务状态暂不可用"))

    override suspend fun plan(courseId: String, mode: String): Result<InteractiveClassroomPlanDto> =
        repository.interactiveClassroomPlan(courseId, mode)?.let { Result.success(it) }
            ?: Result.failure(IllegalStateException("生成计划加载失败，请稍后重试"))

    override suspend fun generate(courseId: String, request: InteractiveClassroomGenerateRequest) =
        repository.generateInteractiveClassroom(courseId, request)

    override suspend fun job(courseId: String, sessionId: String) =
        repository.interactiveClassroomJob(courseId, sessionId)

    override suspend fun retry(courseId: String, sessionId: String, request: InteractiveClassroomGenerateRequest) =
        repository.retryInteractiveClassroom(courseId, sessionId, request)

    override suspend fun composition(courseId: String, sessionId: String) =
        repository.interactiveClassroomComposition(courseId, sessionId)

    override suspend fun history(courseId: String): Result<List<InteractiveClassroomItemDto>> =
        runCatching { repository.interactiveClassroomHistory(courseId) }
}

/**
 * 服务状态的**显式且穷尽**投影。
 *
 * 修复前的实现是 `when { incompatible; degraded; available; configured; else -> UNAVAILABLE }`，
 * 于是真实存在的 `configured=true, available=false, unavailable=true`
 * （配置了但连不上）会先命中 `configured`，界面错误地显示"已配置，正在准备"。
 *
 * 现在按后端字段语义定死优先级：
 *
 *   incompatible > unavailable > (degraded | available) > configured > not_configured
 *
 * - `unavailable` 必须优先于 `configured`：连不上就是连不上；
 * - `degraded` 只在 `available=true` 时有意义（后端 `degraded = is_degraded(caps)`
 *   与 `available=True` 同时置位）。只有 degraded 而没有 available 的组合后端不会产出，
 *   此时退回 CONFIGURED —— 既不宣称可用，也不谎称"未开启"；
 * - `configured=false` 才是"未开启"。
 */
enum class InteractiveClassroomServiceState(val label: String) {
    INCOMPATIBLE("版本不兼容"),
    UNAVAILABLE("暂不可用"),
    DEGRADED("降级运行"),
    AVAILABLE("可用"),
    CONFIGURED("已配置，正在准备"),
    NOT_CONFIGURED("未开启"),
}

internal fun InteractiveClassroomStatusDto.serviceState(): InteractiveClassroomServiceState = when {
    incompatible || compatibility == "incompatible" -> InteractiveClassroomServiceState.INCOMPATIBLE
    unavailable -> InteractiveClassroomServiceState.UNAVAILABLE
    available && degraded -> InteractiveClassroomServiceState.DEGRADED
    available -> InteractiveClassroomServiceState.AVAILABLE
    configured -> InteractiveClassroomServiceState.CONFIGURED
    else -> InteractiveClassroomServiceState.NOT_CONFIGURED
}

data class InteractiveClassroomUiState(
    val courseId: String,
    val status: InteractiveClassroomStatusDto? = null,
    val serviceState: InteractiveClassroomServiceState = InteractiveClassroomServiceState.UNAVAILABLE,
    val plan: InteractiveClassroomPlanDto? = null,
    val selectedMode: String = "adaptive",
    val learningObjective: String = "",
    val currentDifficulty: String = "",
    val desiredDurationMinutes: Int = 30,
    val difficultyLevel: String = "standard",
    val wantsMorePractice: Boolean = false,
    val selectedMaterialIds: Set<String> = emptySet(),
    val planLoading: Boolean = false,
    val confirmed: Boolean = false,
    val progress: ClassroomProgressState = ClassroomProgressState(),
    val composition: ClassroomCompositionText.Description? = null,
    val history: List<InteractiveClassroomItemDto> = emptyList(),
    val loading: Boolean = true,
    val observing: Boolean = false,
    val error: String? = null,
)

class InteractiveClassroomViewModel(
    private val courseId: String,
    private val dataSource: InteractiveClassroomDataSource,
    private val savedStateHandle: SavedStateHandle = SavedStateHandle(),
    private val clock: () -> Long = System::currentTimeMillis,
    private val wait: suspend (Long) -> Unit = { delay(it) },
    private val maxWaitMs: Long = 15 * 60 * 1000L,
    initialSessionId: String? = null,
) : ViewModel() {
    private val sessionKey = "interactive_classroom_session_id:$courseId"
    private val _uiState = MutableStateFlow(InteractiveClassroomUiState(courseId = courseId))
    val uiState: StateFlow<InteractiveClassroomUiState> = _uiState.asStateFlow()
    private var observationJob: Job? = null
    private var observationAllowed = true

    init {
        val restored = savedStateHandle.get<String>(sessionKey)
            ?: initialSessionId?.takeIf { it.isNotBlank() }
        if (restored != null) {
            savedStateHandle[sessionKey] = restored
            _uiState.update { it.copy(progress = ClassroomProgressState(phase = ClassroomPhase.QUEUED, sessionId = restored)) }
        }
        load()
    }

    fun load() {
        viewModelScope.launch {
            launch {
                dataSource.status(courseId)
                    .onSuccess { status -> _uiState.update { it.copy(status = status, serviceState = status.serviceState()) } }
                    .onFailure { error -> _uiState.update { it.copy(serviceState = InteractiveClassroomServiceState.UNAVAILABLE, error = readable(error, "互动课堂服务状态加载失败")) } }
            }
            launch {
                dataSource.history(courseId).onSuccess { items -> _uiState.update { it.copy(history = items) } }
            }
            loadPlan(_uiState.value.selectedMode)
            _uiState.update { it.copy(loading = false) }
        }
        resumeObservationIfNeeded()
    }

    fun resumeObservationIfNeeded() {
        observationAllowed = true
        val progress = _uiState.value.progress
        val sessionId = progress.sessionId ?: return
        if (progress.isLive) observeSession(sessionId, pollIntervalMs())
    }

    fun selectMode(mode: String) {
        val normalized = com.example.campusai.data.classroom.ClassroomIntentCatalog.normalize(mode).wire
        _uiState.update { it.copy(selectedMode = normalized, plan = null, confirmed = false, planLoading = true, error = null) }
        viewModelScope.launch { loadPlan(normalized) }
    }

    fun updateLearningObjective(value: String) = _uiState.update { it.copy(learningObjective = value.take(500)) }
    fun updateCurrentDifficulty(value: String) = _uiState.update { it.copy(currentDifficulty = value.take(500)) }
    fun updateDuration(value: Int) = _uiState.update { it.copy(desiredDurationMinutes = value) }
    fun updateDifficulty(value: String) = _uiState.update { it.copy(difficultyLevel = value) }
    fun updateMorePractice(value: Boolean) = _uiState.update { it.copy(wantsMorePractice = value) }
    fun toggleMaterial(id: String, selected: Boolean) = _uiState.update {
        it.copy(selectedMaterialIds = if (selected) it.selectedMaterialIds + id else it.selectedMaterialIds - id)
    }

    fun confirmPlan() {
        val state = _uiState.value
        if (state.plan?.canGenerate == true && state.progress.sessionId == null) {
            _uiState.update { it.copy(confirmed = true, error = null) }
        }
    }

    fun generate() {
        val state = _uiState.value
        val plan = state.plan ?: return
        if (!state.confirmed || state.progress.sessionId != null || !plan.canGenerate) return
        val request = state.toRequest()
        _uiState.update { it.copy(progress = ClassroomProgressReducer.requesting(it.progress), error = null) }
        viewModelScope.launch {
            dataSource.generate(courseId, request)
                .onSuccess { response -> startSession(response, request) }
                .onFailure { error -> _uiState.update { it.copy(progress = ClassroomProgressReducer.failed(it.progress, readable(error, "互动课堂生成请求失败")), error = readable(error, "互动课堂生成请求失败")) } }
        }
    }

    fun retry() {
        val state = _uiState.value
        val oldSessionId = state.progress.sessionId ?: return
        if (state.progress.phase != ClassroomPhase.FAILED || !state.progress.retryable) return
        val request = state.toRequest()
        _uiState.update { it.copy(progress = ClassroomProgressReducer.requesting(it.progress), error = null) }
        viewModelScope.launch {
            dataSource.retry(courseId, oldSessionId, request)
                .onSuccess { response -> startSession(response, request) }
                .onFailure { error -> _uiState.update { it.copy(progress = ClassroomProgressReducer.failed(it.progress, readable(error, "重试请求失败")), error = readable(error, "重试请求失败")) } }
        }
    }

    fun stopObservation() {
        observationJob?.cancel()
        observationJob = null
        observationAllowed = false
        _uiState.update { it.copy(observing = false) }
    }

    private suspend fun loadPlan(mode: String) {
        dataSource.plan(courseId, mode)
            .onSuccess { plan ->
                _uiState.update {
                    if (it.selectedMode == mode) it.copy(plan = plan, planLoading = false, error = null) else it
                }
            }
            .onFailure { error -> _uiState.update { it.copy(planLoading = false, error = readable(error, "生成计划加载失败，请稍后重试")) } }
    }

    private fun startSession(response: InteractiveClassroomGenerateResponse, request: InteractiveClassroomGenerateRequest) {
        val sessionId = response.session.sessionId
        savedStateHandle[sessionKey] = sessionId
        _uiState.update {
            it.copy(
                confirmed = true,
                progress = ClassroomProgressReducer.fromGenerate(response),
                error = null,
            )
        }
        if (observationAllowed) observeSession(sessionId, response.pollIntervalMs)
    }

    private fun observeSession(sessionId: String, pollIntervalMs: Int) {
        observationJob?.cancel()
        observationJob = viewModelScope.launch {
            _uiState.update { it.copy(observing = true) }
            val started = clock()
            val delayMs = pollIntervalMs.coerceIn(1500, 30000).toLong()
            while (isActive) {
                if (clock() - started > maxWaitMs) {
                    _uiState.update { it.copy(observing = false, error = "生成等待时间过长，请稍后回到本页查看") }
                    return@launch
                }
                val result = dataSource.job(courseId, sessionId)
                result.onSuccess { session ->
                    _uiState.update { state ->
                        state.copy(progress = ClassroomProgressReducer.fromSession(session, state.progress), error = null)
                    }
                }.onFailure { error ->
                    _uiState.update { it.copy(error = readable(error, "进度查询失败，正在重试")) }
                }
                val progress = _uiState.value.progress
                if (progress.phase == ClassroomPhase.SUCCEEDED) {
                    loadComposition(sessionId)
                    _uiState.update { it.copy(observing = false) }
                    return@launch
                }
                if (progress.phase == ClassroomPhase.FAILED) {
                    _uiState.update { it.copy(observing = false) }
                    return@launch
                }
                wait(delayMs)
            }
        }
    }

    private suspend fun loadComposition(sessionId: String) {
        dataSource.composition(courseId, sessionId)
            .onSuccess { dto -> _uiState.update { it.copy(composition = ClassroomCompositionText.describe(dto)) } }
            .onFailure { error -> _uiState.update { it.copy(error = readable(error, "课堂内容读取失败")) } }
    }

    private fun pollIntervalMs(): Int = _uiState.value.status?.pollIntervalMs ?: 5000

    private fun InteractiveClassroomUiState.toRequest() = InteractiveClassroomGenerateRequest(
        mode = selectedMode,
        learningObjective = learningObjective.trim().takeIf { it.isNotBlank() },
        currentDifficulty = currentDifficulty.trim().takeIf { it.isNotBlank() },
        desiredDurationMinutes = desiredDurationMinutes,
        difficultyLevel = difficultyLevel,
        wantsMorePractice = wantsMorePractice,
        selectedMaterialIds = selectedMaterialIds.toList(),
    )

    private fun readable(error: Throwable, fallback: String): String = error.message?.takeIf { it.isNotBlank() } ?: fallback
}

class InteractiveClassroomViewModelFactory(
    private val courseId: String,
    private val dataSource: InteractiveClassroomDataSource,
    private val initialSessionId: String? = null,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>, extras: CreationExtras): T =
        InteractiveClassroomViewModel(
            courseId = courseId,
            dataSource = dataSource,
            savedStateHandle = extras.createSavedStateHandle(),
            initialSessionId = initialSessionId,
        ) as T
}

@Composable
fun InteractiveClassroomSection(
    course: Course,
    repository: AppRepository,
    initialSessionId: String? = null,
) {
    val factory = remember(course.id, repository, initialSessionId) {
        InteractiveClassroomViewModelFactory(
            courseId = course.id,
            dataSource = AppInteractiveClassroomDataSource(repository),
            initialSessionId = initialSessionId,
        )
    }
    val viewModel: InteractiveClassroomViewModel = viewModel(
        key = "interactive-classroom-${course.id}",
        factory = factory,
    )
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current
    DisposableEffect(viewModel) {
        viewModel.resumeObservationIfNeeded()
        onDispose { viewModel.stopObservation() }
    }
    Column(
        Modifier.fillMaxWidth()
            .padding(top = 4.dp)
            .background(Surface, RoundedCornerShape(18.dp))
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("智能辅导 · 互动课堂", fontWeight = FontWeight.Bold, fontSize = 15.sp)
                Text("围绕这门课生成一次可交互学习内容", color = Muted, fontSize = 11.sp)
            }
            Text(state.serviceState.label, color = serviceColor(state.serviceState), fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
        }
        state.status?.reason?.takeIf { it.isNotBlank() }?.let { Text(it, color = Muted, fontSize = 11.sp) }
        if (state.status?.browserEmbedAvailable != true) {
            Text(
                "浏览器课堂当前不可打开${state.status?.browserEmbedReason?.let { "：$it" }.orEmpty()}",
                color = ColorError,
                fontSize = 11.sp,
            )
        }
        if (state.loading || state.planLoading) {
            Row(verticalAlignment = Alignment.CenterVertically) { CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp); Spacer(Modifier.width(7.dp)); Text("正在读取课程资料与生成计划…", color = Muted, fontSize = 11.sp) }
        }
        IntentChooser(state.selectedMode, state.serviceState, viewModel::selectMode)
        state.plan?.let { plan ->
            Text("推荐理由", fontWeight = FontWeight.SemiBold, fontSize = 12.sp)
            Text(plan.adaptiveReason ?: plan.reason ?: "根据课程资料为你安排一条学习路径。", color = Muted, fontSize = 11.sp, lineHeight = 16.sp)
            StudentBrief(state, viewModel)
            MaterialsChooser(plan, state.selectedMaterialIds, viewModel::toggleMaterial)
            if (!state.confirmed) {
                Button(
                    onClick = viewModel::confirmPlan,
                    enabled = plan.canGenerate && state.progress.sessionId == null,
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = Primary),
                ) { Text("查看生成前确认") }
            } else if (state.progress.sessionId == null) {
                ClassroomConfirmCard(plan, state, onGenerate = viewModel::generate)
            }
        }
        state.error?.let { Text(it, color = ColorError, fontSize = 11.sp) }
        ProgressCard(state.progress, state.status, context, onRetry = viewModel::retry)
        state.composition?.let { CompositionCard(it) }
        HistoryCard(state.history, state.status, context)
    }
}

@Composable
private fun IntentChooser(mode: String, serviceState: InteractiveClassroomServiceState, onSelect: (String) -> Unit) {
    Text("学习方式", fontWeight = FontWeight.SemiBold, fontSize = 12.sp)
    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(7.dp)) {
        com.example.campusai.data.classroom.ClassroomIntentCatalog.all.forEach { intent ->
            OutlinedButton(
                onClick = { onSelect(intent.wire) },
                contentPadding = PaddingValues(horizontal = 10.dp, vertical = 5.dp),
                border = BorderStroke(1.dp, if (mode == intent.wire) Primary else Line),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = if (mode == intent.wire) Primary else Muted),
            ) { Text(intent.label, fontSize = 11.sp, maxLines = 1) }
        }
    }
    if (serviceState == InteractiveClassroomServiceState.DEGRADED) Text("当前为降级服务，生成结果可能缺少部分能力。", color = ColorWarning, fontSize = 11.sp)
}

@Composable
private fun StudentBrief(state: InteractiveClassroomUiState, viewModel: InteractiveClassroomViewModel) {
    OutlinedTextField(state.learningObjective, viewModel::updateLearningObjective, Modifier.fillMaxWidth(), label = { Text("学习目标（可选）") }, placeholder = { Text("例如：掌握链表插入与删除") }, singleLine = false, minLines = 2)
    OutlinedTextField(state.currentDifficulty, viewModel::updateCurrentDifficulty, Modifier.fillMaxWidth(), label = { Text("当前困惑（可选）") }, placeholder = { Text("例如：不知道如何判断边界") }, singleLine = false, minLines = 2)
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(7.dp)) {
        Text("时长", color = Muted, fontSize = 11.sp)
        listOf(15, 30, 45, 60).forEach { minutes ->
            OutlinedButton(onClick = { viewModel.updateDuration(minutes) }, contentPadding = PaddingValues(horizontal = 9.dp, vertical = 4.dp), border = BorderStroke(1.dp, if (state.desiredDurationMinutes == minutes) Primary else Line)) { Text("${minutes}分", fontSize = 11.sp) }
        }
    }
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text("需要更多练习", modifier = Modifier.weight(1f), color = Muted, fontSize = 11.sp)
        Switch(checked = state.wantsMorePractice, onCheckedChange = viewModel::updateMorePractice)
    }
}

@Composable
private fun MaterialsChooser(plan: InteractiveClassroomPlanDto, selected: Set<String>, onToggle: (String, Boolean) -> Unit) {
    if (plan.materials.isEmpty()) return
    Text("使用课程资料", fontWeight = FontWeight.SemiBold, fontSize = 12.sp)
    plan.materials.forEach { material ->
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = material.id in selected, onCheckedChange = { onToggle(material.id, it) })
            Text(material.title, fontSize = 11.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
}

@Composable
private fun ClassroomConfirmCard(plan: InteractiveClassroomPlanDto, state: InteractiveClassroomUiState, onGenerate: () -> Unit) {
    Column(Modifier.fillMaxWidth().background(PrimarySoft, RoundedCornerShape(14.dp)).padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("生成前确认", fontWeight = FontWeight.Bold, fontSize = 13.sp)
        Text("课程：${plan.courseName ?: plan.courseId}", fontSize = 11.sp)
        Text("方式：${plan.modeLabel ?: state.selectedMode}", fontSize = 11.sp)
        Text("推荐：${plan.adaptiveReason ?: "按课程资料安排"}", color = Muted, fontSize = 11.sp)
        Text("资料：${if (state.selectedMaterialIds.isEmpty()) "不指定资料，由服务端按课程上下文选择" else "已选择 ${state.selectedMaterialIds.size} 项课程资料"}", color = Muted, fontSize = 11.sp)
        plan.contextWarnings.forEach { warning -> Text("读取提示：$warning", color = ColorWarning, fontSize = 11.sp) }
        Text(plan.intentNote ?: com.example.campusai.data.classroom.ClassroomIntentCatalog.INTENT_NOTE, color = Muted, fontSize = 11.sp, lineHeight = 16.sp)
        Button(onClick = onGenerate, modifier = Modifier.fillMaxWidth(), colors = ButtonDefaults.buttonColors(containerColor = Primary)) { Text("确认并生成") }
    }
}

@Composable
private fun ProgressCard(
    progress: ClassroomProgressState,
    status: InteractiveClassroomStatusDto?,
    context: Context,
    onRetry: () -> Unit,
) {
    if (progress.phase == ClassroomPhase.IDLE) return
    Column(Modifier.fillMaxWidth().background(PrimarySoft, RoundedCornerShape(14.dp)).padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("课堂生成进度", fontWeight = FontWeight.Bold, fontSize = 13.sp)
        Text("${ClassroomProgressReducer.stepLabel(progress.step)} · ${progress.progress.coerceIn(0, 100)}%", color = Primary, fontSize = 11.sp)
        LinearProgressIndicator(progress = { progress.progress.coerceIn(0, 100) / 100f }, Modifier.fillMaxWidth())
        if (progress.message.isNotBlank()) Text(progress.message, color = Muted, fontSize = 11.sp)
        progress.updatedAt?.takeIf { it.isNotBlank() }?.let { Text("更新于 $it", color = Muted, fontSize = 10.sp) }
        if (progress.phase == ClassroomPhase.FAILED && progress.retryable) Button(onClick = onRetry, contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp), colors = ButtonDefaults.buttonColors(containerColor = Primary)) { Text("重试", fontSize = 11.sp) }
        if (progress.generatedButClosed) Text("课堂已生成，但当前没有可用的公开地址。", color = ColorWarning, fontSize = 11.sp)
        // 学生指定的资料无法使用时必须明说，不能静默假装用上了
        progress.materialsWarning?.takeIf { it.isNotBlank() }?.let { Text(it, color = ColorWarning, fontSize = 11.sp) }
        progress.requestSourceNote?.takeIf { it.isNotBlank() }?.let { Text(it, color = Muted, fontSize = 10.sp) }
        val safe = if (status?.browserEmbedAvailable == true) {
            ClassroomUrlPolicy.sanitize(progress.openableUrl(), listOf(status.embedOrigin))
        } else null
        if (safe != null && progress.phase == ClassroomPhase.SUCCEEDED) {
            OutlinedButton(onClick = { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(safe))) }, contentPadding = PaddingValues(horizontal = 10.dp, vertical = 5.dp)) { Text("打开公开课堂", fontSize = 11.sp) }
        }
    }
}

@Composable
private fun CompositionCard(description: ClassroomCompositionText.Description) {
    Column(Modifier.fillMaxWidth().background(PrimarySoft, RoundedCornerShape(14.dp)).padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text("课堂内容", fontWeight = FontWeight.Bold, fontSize = 13.sp)
        Text(ClassroomCompositionText.summary(description), fontSize = 11.sp, lineHeight = 16.sp)
        ClassroomCompositionText.threeDNotice(description)?.let { Text(it, color = ColorWarning, fontSize = 11.sp) }
    }
}

@Composable
private fun HistoryCard(items: List<InteractiveClassroomItemDto>, status: InteractiveClassroomStatusDto?, context: Context) {
    if (items.isEmpty()) return
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("历史课堂", fontWeight = FontWeight.SemiBold, fontSize = 12.sp)
        items.forEach { item ->
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(item.mode ?: "互动课堂", fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
                    Text(item.createdAt ?: "历史记录", color = Muted, fontSize = 10.sp)
                }
                val safe = if (status?.browserEmbedAvailable == true) {
                    ClassroomUrlPolicy.sanitize(item.url, listOf(status.embedOrigin))
                } else null
                if (safe != null) {
                    OutlinedButton(onClick = { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(safe))) }, contentPadding = PaddingValues(horizontal = 9.dp, vertical = 4.dp)) { Text("打开", fontSize = 11.sp) }
                } else {
                    Text(item.urlUnavailableReason ?: status?.browserEmbedReason ?: "当前无法打开", color = Muted, fontSize = 10.sp)
                }
            }
        }
    }
}

private val ColorError = androidx.compose.ui.graphics.Color(0xFFC63D4F)
private val ColorWarning = androidx.compose.ui.graphics.Color(0xFFB26A1F)

@Composable
private fun serviceColor(state: InteractiveClassroomServiceState) = when (state) {
    InteractiveClassroomServiceState.AVAILABLE -> Success
    InteractiveClassroomServiceState.DEGRADED -> ColorWarning
    InteractiveClassroomServiceState.INCOMPATIBLE,
    InteractiveClassroomServiceState.UNAVAILABLE -> ColorError
    InteractiveClassroomServiceState.CONFIGURED -> Primary
    InteractiveClassroomServiceState.NOT_CONFIGURED -> Muted
}

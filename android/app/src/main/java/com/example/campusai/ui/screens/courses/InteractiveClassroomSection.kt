package com.example.campusai.ui.screens.courses

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
import androidx.compose.foundation.clickable
import androidx.compose.foundation.border
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.platform.LocalContext
import android.net.Uri
import android.provider.OpenableColumns
import java.io.ByteArrayOutputStream
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.classroom.ClassroomCompositionText
import com.example.campusai.BuildConfig
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
            val statusJob = launch {
                dataSource.status(courseId)
                    .onSuccess { status -> _uiState.update { it.copy(status = status, serviceState = status.serviceState()) } }
                    .onFailure { error -> _uiState.update { it.copy(serviceState = InteractiveClassroomServiceState.UNAVAILABLE, error = readable(error, "互动课堂服务状态加载失败")) } }
            }
            launch {
                dataSource.history(courseId).onSuccess { items -> _uiState.update { it.copy(history = items) } }
            }
            loadPlan(_uiState.value.selectedMode)
            statusJob.join()
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

    fun refreshPlan() {
        _uiState.update { it.copy(planLoading = true) }
        viewModelScope.launch { loadPlan(_uiState.value.selectedMode) }
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
        if (!state.confirmed || state.progress.phase != ClassroomPhase.IDLE || !plan.canGenerate) return
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

    fun returnToSettings() {
        if (_uiState.value.progress.phase == ClassroomPhase.FAILED && _uiState.value.progress.sessionId == null) {
            _uiState.update { it.copy(confirmed = false, progress = ClassroomProgressState(), error = null) }
            viewModelScope.launch {
                dataSource.history(courseId).onSuccess { items -> _uiState.update { it.copy(history = items) } }
            }
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

    private fun readable(error: Throwable, fallback: String): String =
        if (error is java.net.SocketTimeoutException) "连接等待超时，请先查看历史课堂，避免重复生成" else error.message?.takeIf { it.isNotBlank() } ?: fallback
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
    val scope = rememberCoroutineScope()
    var showMaterials by remember(course.id) { mutableStateOf(false) }
    var uploadBusy by remember(course.id) { mutableStateOf(false) }
    var uploadMessage by remember(course.id) { mutableStateOf<String?>(null) }
    var viewerUrl by remember(course.id) { mutableStateOf<String?>(null) }
    DisposableEffect(viewModel) {
        viewModel.resumeObservationIfNeeded()
        onDispose { viewModel.stopObservation() }
    }

    Column(
        Modifier.fillMaxWidth().padding(top = 4.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 2.dp, vertical = 6.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("备课讲义", color = ClassroomInk, fontWeight = FontWeight.Bold, fontSize = 21.sp)
                Text("选讲法 · 定目标 · 挑资料", color = ClassroomMuted, fontSize = 12.sp)
            }
            Text(if (state.loading) "检测中" else state.serviceState.label,
                color = ClassroomCopper,
                fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
        }
        val serviceReady = state.serviceState == InteractiveClassroomServiceState.AVAILABLE ||
            state.serviceState == InteractiveClassroomServiceState.DEGRADED
        val canCreateClassroom = serviceReady && state.status?.browserEmbedAvailable == true
        if (!state.loading && !canCreateClassroom) {
            Text(
                state.status?.reason ?: state.status?.browserEmbedReason ?: state.error ?: when (state.serviceState) {
                    InteractiveClassroomServiceState.NOT_CONFIGURED -> "互动课堂暂未开通。课程资料和自习室仍可使用。"
                    InteractiveClassroomServiceState.INCOMPATIBLE -> "课堂服务版本暂不兼容，请稍后再试。"
                    InteractiveClassroomServiceState.CONFIGURED -> "课堂服务正在准备，请稍后重试。"
                    InteractiveClassroomServiceState.AVAILABLE,
                    InteractiveClassroomServiceState.DEGRADED -> "课堂服务已就绪，但手机当前无法打开生成的课堂。暂不生成，以免产生费用。"
                    else -> "暂时无法连接课堂服务，请稍后重试。"
                },
                color = Muted,
                fontSize = 12.sp,
            )
            Text("重新检测课堂服务 ›", modifier = Modifier.clickable { viewModel.load() }.padding(vertical = 8.dp),
                color = ClassroomCopper, fontSize = 12.sp, fontWeight = FontWeight.Bold)
        }
        if (state.loading || (canCreateClassroom && state.planLoading)) {
            Row(verticalAlignment = Alignment.CenterVertically) { CircularProgressIndicator(Modifier.size(18.dp), color = ClassroomCopper, strokeWidth = 2.dp); Spacer(Modifier.width(7.dp)); Text("正在读取课程资料与生成计划…", color = Muted, fontSize = 11.sp) }
        }
        if (canCreateClassroom) state.plan?.let { plan ->
            if (state.progress.sessionId == null) {
                Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    IntentChooser(state.selectedMode, state.serviceState, viewModel::selectMode)
                    androidx.compose.material3.HorizontalDivider(color = ClassroomLine)
                    StudentBrief(state, viewModel)
                    androidx.compose.material3.HorizontalDivider(color = ClassroomLine)
                    Row(Modifier.fillMaxWidth().background(Color(0xFFEADABD))
                        .clickable { showMaterials = true }.padding(15.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("03  挑选课程资料", color = ClassroomInk, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                            Text("已选 ${state.selectedMaterialIds.size} / ${plan.materials.size} 项", color = ClassroomMuted, fontSize = 11.sp)
                        }
                        Text("›", color = ClassroomCopper, fontSize = 24.sp)
                    }
                    Text("个人上传的可解析资料会读取正文；学习通资料以已同步内容为准。", color = ClassroomMuted, fontSize = 11.sp)
                }
            }
            if (!state.confirmed && state.progress.sessionId == null) {
                androidx.compose.material3.Button(
                    onClick = viewModel::confirmPlan,
                    enabled = plan.canGenerate && state.progress.sessionId == null,
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = ClassroomCopper),
                ) { Text("查看生成前确认") }
            } else if (state.progress.phase == ClassroomPhase.IDLE) {
                ClassroomConfirmCard(plan, state, onGenerate = viewModel::generate)
            }
        }
        if (canCreateClassroom) state.error?.let { Text(it, color = ColorError, fontSize = 11.sp) }
        ProgressCard(state.progress, state.status, canRetry = canCreateClassroom, onRetry = viewModel::retry, onOpen = { viewerUrl = it })
        if (state.progress.phase == ClassroomPhase.FAILED && state.progress.sessionId == null) {
            Text("返回设置并刷新历史课堂 ›", modifier = Modifier.clickable { viewModel.returnToSettings() }.padding(vertical = 8.dp),
                color = ClassroomCopper, fontSize = 12.sp, fontWeight = FontWeight.Bold)
        }
        state.composition?.let { CompositionCard(it) }
        HistoryCard(state.history, state.status, onOpen = { viewerUrl = it })
    }
    if (showMaterials) state.plan?.let { plan ->
        ClassroomMaterialLibrary(
            courseName = course.name,
            materials = plan.materials,
            selected = state.selectedMaterialIds,
            onToggle = viewModel::toggleMaterial,
            uploadBusy = uploadBusy,
            uploadMessage = uploadMessage,
            onPickFile = { uri: Uri ->
                if (!uploadBusy) scope.launch {
                    uploadBusy = true
                    uploadMessage = null
                    try {
                        val nameAndBytes = withContext(Dispatchers.IO) {
                            val resolver = context.contentResolver
                            val fallbackName = when (resolver.getType(uri)) {
                                "application/pdf" -> "资料.pdf"
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document" -> "资料.docx"
                                "text/markdown" -> "资料.md"
                                else -> "资料.txt"
                            }
                            val name = resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                                if (cursor.moveToFirst()) cursor.getString(0) else null
                            } ?: fallbackName
                            val bytes = resolver.openInputStream(uri)?.use { stream ->
                                val output = ByteArrayOutputStream()
                                val chunk = ByteArray(8192)
                                while (true) {
                                    val read = stream.read(chunk)
                                    if (read <= 0) break
                                    output.write(chunk, 0, read)
                                    if (output.size() > 2 * 1024 * 1024) throw IllegalArgumentException("单份资料不能超过 2 MB")
                                }
                                output.toByteArray()
                            } ?: throw IllegalArgumentException("无法读取所选文件")
                            name to bytes
                        }
                        repository.uploadClassroomMaterial(course.id, nameAndBytes.first, nameAndBytes.second)
                            .onSuccess { uploaded ->
                                if (uploaded.extractionStatus == "extracted" && uploaded.textChars > 0) {
                                    viewModel.toggleMaterial(uploaded.id, true)
                                    viewModel.refreshPlan()
                                    uploadMessage = "已添加并选中：${uploaded.filename}"
                                } else {
                                    uploadMessage = "文件已上传，但暂无法提取正文，不能用于生成课堂。"
                                }
                            }.onFailure { uploadMessage = it.message ?: "资料上传失败" }
                    } catch (error: Exception) {
                        uploadMessage = error.message ?: "无法读取文件"
                    } finally { uploadBusy = false }
                }
            },
            onDone = { showMaterials = false },
        )
    }
    viewerUrl?.let { ClassroomViewer(it, { viewerUrl = null }, repository) }
}

@Composable
private fun IntentChooser(mode: String, serviceState: InteractiveClassroomServiceState, onSelect: (String) -> Unit) {
    Text("01  选择讲法", color = ClassroomInk, fontWeight = FontWeight.Bold, fontSize = 14.sp)
    com.example.campusai.data.classroom.ClassroomIntentCatalog.all.chunked(3).forEach { row ->
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            row.forEach { intent ->
                val selected = mode == intent.wire
                Text(intent.label, modifier = Modifier.weight(1f)
                    .background(if (selected) Color(0xFFEBCDA1) else Color.Transparent)
                    .border(1.dp, if (selected) ClassroomCopper else ClassroomLine)
                    .clickable { onSelect(intent.wire) }.padding(vertical = 10.dp),
                    color = ClassroomInk, fontSize = 11.sp,
                    fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
                    textAlign = androidx.compose.ui.text.style.TextAlign.Center, maxLines = 1)
            }
        }
    }
    Text(com.example.campusai.data.classroom.ClassroomIntentCatalog.normalize(mode).description,
        color = ClassroomMuted, fontSize = 11.sp)
    if (serviceState == InteractiveClassroomServiceState.DEGRADED) Text("当前为降级服务，生成结果可能缺少部分能力。", color = ColorWarning, fontSize = 11.sp)
}

@Composable
private fun StudentBrief(state: InteractiveClassroomUiState, viewModel: InteractiveClassroomViewModel) {
    Text("02  学习目标与时长", color = ClassroomInk, fontWeight = FontWeight.Bold, fontSize = 14.sp)
    OutlinedTextField(state.learningObjective, viewModel::updateLearningObjective, Modifier.fillMaxWidth(),
        label = { Text("这节课想弄懂什么？（可选）") }, placeholder = { Text("例如：掌握链表插入与删除") },
        singleLine = true, shape = RoundedCornerShape(5.dp),
        colors = OutlinedTextFieldDefaults.colors(
            focusedBorderColor = ClassroomCopper, unfocusedBorderColor = ClassroomLine,
            focusedTextColor = ClassroomInk, unfocusedTextColor = ClassroomInk,
            focusedLabelColor = ClassroomCopper, cursorColor = ClassroomCopper,
        ))
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(7.dp)) {
        listOf(15, 30, 45, 60).forEach { minutes ->
            val selected = state.desiredDurationMinutes == minutes
            Text("${minutes} 分", modifier = Modifier.weight(1f)
                .background(if (selected) Color(0xFFEBCDA1) else Color.Transparent)
                .border(1.dp, if (selected) ClassroomCopper else ClassroomLine)
                .clickable { viewModel.updateDuration(minutes) }.padding(vertical = 11.dp),
                color = ClassroomInk, fontSize = 11.sp,
                textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        }
    }
}

@Composable
private fun ClassroomConfirmCard(plan: InteractiveClassroomPlanDto, state: InteractiveClassroomUiState, onGenerate: () -> Unit) {
    Column(Modifier.fillMaxWidth().background(Color(0xFFEADABD)).padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("生成前确认", color = ClassroomInk, fontWeight = FontWeight.Bold, fontSize = 13.sp)
        Text("课程：${plan.courseName ?: plan.courseId}", fontSize = 11.sp)
        Text("方式：${if (state.selectedMode == "adaptive") "自动推荐 → " else ""}${plan.modeLabel ?: state.selectedMode}", fontSize = 11.sp)
        Text("推荐：${plan.adaptiveReason ?: "按课程资料安排"}", color = Muted, fontSize = 11.sp)
        Text("资料：${if (state.selectedMaterialIds.isEmpty()) "不指定资料，由服务端按课程上下文选择" else "已选择 ${state.selectedMaterialIds.size} 项课程资料"}", color = Muted, fontSize = 11.sp)
        plan.contextWarnings.forEach { warning -> Text("读取提示：$warning", color = ColorWarning, fontSize = 11.sp) }
        Text(plan.intentNote ?: com.example.campusai.data.classroom.ClassroomIntentCatalog.INTENT_NOTE, color = Muted, fontSize = 11.sp, lineHeight = 16.sp)
        androidx.compose.material3.Button(onClick = onGenerate, modifier = Modifier.fillMaxWidth(), colors = ButtonDefaults.buttonColors(containerColor = ClassroomCopper)) { Text("确认并生成") }
    }
}

@Composable
private fun ProgressCard(
    progress: ClassroomProgressState,
    status: InteractiveClassroomStatusDto?,
    canRetry: Boolean,
    onRetry: () -> Unit,
    onOpen: (String) -> Unit,
) {
    if (progress.phase == ClassroomPhase.IDLE) return
    Column(Modifier.fillMaxWidth().padding(vertical = 14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        androidx.compose.material3.HorizontalDivider(color = ClassroomLine)
        Text("课堂生成进度", color = ClassroomInk, fontWeight = FontWeight.Bold, fontSize = 13.sp)
        Text("${ClassroomProgressReducer.stepLabel(progress.step)} · ${progress.progress.coerceIn(0, 100)}%", color = ClassroomCopper, fontSize = 11.sp)
        LinearProgressIndicator(progress = { progress.progress.coerceIn(0, 100) / 100f }, Modifier.fillMaxWidth(), color = ClassroomCopper, trackColor = ClassroomLine)
        if (progress.message.isNotBlank()) Text(when {
            progress.phase == ClassroomPhase.SUCCEEDED -> "课堂已经准备好"
            progress.message.startsWith("Generated ") -> "正在生成课堂内容"
            else -> progress.message
        }, color = Muted, fontSize = 11.sp)
        progress.updatedAt?.takeIf { it.isNotBlank() }?.let { raw ->
            val display = runCatching { java.time.OffsetDateTime.parse(raw).atZoneSameInstant(java.time.ZoneId.systemDefault()).format(java.time.format.DateTimeFormatter.ofPattern("MM-dd HH:mm")) }.getOrDefault(raw.take(16).replace('T', ' '))
            Text("更新于 $display", color = Muted, fontSize = 10.sp)
        }
        if (canRetry && progress.phase == ClassroomPhase.FAILED && progress.retryable) androidx.compose.material3.Button(onClick = onRetry, contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp), colors = ButtonDefaults.buttonColors(containerColor = ClassroomCopper)) { Text("重试", fontSize = 11.sp) }
        if (progress.generatedButClosed) Text("课堂已生成，但当前没有可用的公开地址。", color = ColorWarning, fontSize = 11.sp)
        // 学生指定的资料无法使用时必须明说，不能静默假装用上了
        progress.materialsWarning?.takeIf { it.isNotBlank() }?.let { Text(it, color = ColorWarning, fontSize = 11.sp) }
        progress.requestSourceNote?.takeIf { it.isNotBlank() }?.let { Text(it, color = Muted, fontSize = 10.sp) }
        val safe = if (status?.browserEmbedAvailable == true) {
            ClassroomUrlPolicy.sanitize(progress.openableUrl(), listOf(status.embedOrigin), allowEmulatorDebug = BuildConfig.DEBUG)
        } else null
        if (progress.phase == ClassroomPhase.SUCCEEDED) {
            if (safe != null) {
                androidx.compose.material3.Button(onClick = { onOpen(safe) }, modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = ClassroomCopper)) { Text("进入课堂", fontWeight = FontWeight.Bold) }
            } else {
                Text(progress.urlUnavailableReason ?: status?.browserEmbedReason ?: "课堂地址未通过安全校验，暂时无法打开", color = ColorWarning, fontSize = 11.sp)
            }
        }
    }
}

@Composable
private fun CompositionCard(description: ClassroomCompositionText.Description) {
    Column(Modifier.fillMaxWidth().padding(vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
        androidx.compose.material3.HorizontalDivider(color = ClassroomLine)
        Text("课堂内容", color = ClassroomInk, fontWeight = FontWeight.Bold, fontSize = 13.sp)
        Text(ClassroomCompositionText.summary(description), fontSize = 11.sp, lineHeight = 16.sp)
        ClassroomCompositionText.threeDNotice(description)?.let { Text(it, color = ColorWarning, fontSize = 11.sp) }
    }
}

@Composable
private fun HistoryCard(items: List<InteractiveClassroomItemDto>, status: InteractiveClassroomStatusDto?, onOpen: (String) -> Unit) {
    if (items.isEmpty()) return
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        androidx.compose.material3.HorizontalDivider(color = ClassroomLine)
        Text("历史课堂", color = ClassroomInk, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
        items.forEach { item ->
            Row(Modifier.fillMaxWidth().padding(vertical = 7.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(com.example.campusai.data.classroom.ClassroomIntentCatalog.labelOf(item.mode),
                        color = ClassroomInk, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                    val createdAt = item.createdAt?.let { raw ->
                        runCatching {
                            java.time.OffsetDateTime.parse(raw).atZoneSameInstant(java.time.ZoneId.systemDefault())
                                .format(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm"))
                        }.getOrDefault(raw.take(16).replace('T', ' '))
                    } ?: "历史记录"
                    Text(createdAt, color = Muted, fontSize = 11.sp)
                }
                val safe = if (status?.browserEmbedAvailable == true) {
                    ClassroomUrlPolicy.sanitize(item.url, listOf(status.embedOrigin), allowEmulatorDebug = BuildConfig.DEBUG)
                } else null
                if (safe != null) {
                    Text("打开 ›", modifier = Modifier.clickable { onOpen(safe) }.padding(8.dp),
                        color = ClassroomCopper, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                } else {
                    Text(item.urlUnavailableReason ?: status?.browserEmbedReason ?: "当前无法打开", color = Muted, fontSize = 10.sp)
                }
            }
            androidx.compose.material3.HorizontalDivider(color = ClassroomLine.copy(alpha = .7f))
        }
    }
}

private val ColorError = androidx.compose.ui.graphics.Color(0xFFC63D4F)
private val ColorWarning = androidx.compose.ui.graphics.Color(0xFFB26A1F)
private val ClassroomInk = Color(0xFF263A50)
private val ClassroomCopper = Color(0xFFAD6845)
private val ClassroomLine = Color(0xFFD4BC91)
private val ClassroomMuted = Color(0xFF667487)

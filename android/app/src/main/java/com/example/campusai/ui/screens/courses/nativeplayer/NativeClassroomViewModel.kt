package com.example.campusai.ui.screens.courses.nativeplayer

import android.app.Application
import android.net.Uri
import android.os.Debug
import android.os.SystemClock
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.datasource.DataSource
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.common.util.UnstableApi
import com.example.campusai.BuildConfig
import com.example.campusai.data.classroom.nativeplayer.ClassroomActionSequencePlanner
import com.example.campusai.data.classroom.nativeplayer.ClassroomLimitExperiment
import com.example.campusai.data.classroom.nativeplayer.ClassroomLevel
import com.example.campusai.data.classroom.nativeplayer.ClassroomLocalRead
import com.example.campusai.data.classroom.nativeplayer.ClassroomLocalWriteGate
import com.example.campusai.data.classroom.nativeplayer.ClassroomMediaDataSourceFactory
import com.example.campusai.data.classroom.nativeplayer.ClassroomSequenceResult
import com.example.campusai.data.classroom.nativeplayer.ClassroomSequenceStep
import com.example.campusai.data.classroom.nativeplayer.ClassroomSequenceStepResult
import com.example.campusai.data.classroom.nativeplayer.ClassroomSessionFlusher
import com.example.campusai.data.classroom.nativeplayer.ClassroomStateWrite
import com.example.campusai.data.classroom.nativeplayer.ClassroomWriteResult
import com.example.campusai.data.classroom.nativeplayer.ClassroomWriteStatus
import com.example.campusai.data.classroom.nativeplayer.failed
import com.example.campusai.data.classroom.nativeplayer.readClassroomLocal
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomSource
import com.example.campusai.data.classroom.nativeplayer.runClassroomSequence
import com.example.campusai.data.classroom.nativeplayer.ClassroomMediaPolicy
import com.example.campusai.data.classroom.nativeplayer.ClassroomMediaSession
import com.example.campusai.data.classroom.nativeplayer.ClassroomRewardResult
import com.example.campusai.data.classroom.nativeplayer.ClassroomRewards
import com.example.campusai.data.classroom.nativeplayer.ClassroomRewardsCodec
import com.example.campusai.data.classroom.nativeplayer.ClassroomRewardsDecodeResult
import com.example.campusai.data.classroom.nativeplayer.ClassroomRewardsEngine
import com.example.campusai.data.classroom.nativeplayer.allowsWrite
import com.example.campusai.data.classroom.nativeplayer.rewards
import com.example.campusai.data.classroom.nativeplayer.ClassroomQuizCoordinator
import com.example.campusai.data.classroom.nativeplayer.NativeAction
import com.example.campusai.data.classroom.nativeplayer.NativeAnswer
import com.example.campusai.data.classroom.nativeplayer.NativeClassmate
import com.example.campusai.data.classroom.nativeplayer.NativeClassmateMessage
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomCache
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomRef
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomAssetPolicy
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomParser
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomText
import com.example.campusai.data.classroom.nativeplayer.NativePageState
import com.example.campusai.data.classroom.nativeplayer.NativePblProject
import com.example.campusai.data.classroom.nativeplayer.NativePlaybackPlan
import com.example.campusai.data.classroom.nativeplayer.NativePlaybackPolicy
import com.example.campusai.data.classroom.nativeplayer.NativeQuestion
import com.example.campusai.data.classroom.nativeplayer.NativeQuiz
import com.example.campusai.data.classroom.nativeplayer.NativeQuizResult
import com.example.campusai.data.classroom.nativeplayer.NativeQuizUiState
import com.example.campusai.data.classroom.nativeplayer.NativeSceneDisposition
import com.example.campusai.data.classroom.nativeplayer.NativeSceneMode
import com.example.campusai.data.classroom.nativeplayer.NativeScenePlan
import com.example.campusai.data.classroom.nativeplayer.NativeSlide
import com.example.campusai.data.classroom.nativeplayer.NativeStageDocument
import com.example.campusai.data.classroom.nativeplayer.NativeCanvasElement
import com.example.campusai.data.classroom.nativeplayer.asMap
import com.example.campusai.data.classroom.nativeplayer.asDouble
import com.example.campusai.data.classroom.nativeplayer.asText
import com.example.campusai.data.focus.voice.AndroidTextToSpeechSynthesizer
import com.example.campusai.data.remote.ApiClient
import com.example.campusai.data.remote.MagicClassClassmateAskRequest
import com.example.campusai.data.remote.MagicClassClassmateMemoryDto
import com.example.campusai.data.remote.MagicClassClassmateRespondRequest
import com.example.campusai.data.remote.MagicClassClassmateSceneDto
import com.example.campusai.data.remote.MagicClassQuizAttemptRequest
import com.example.campusai.data.remote.MagicClassScenePlaybackDto
import com.example.campusai.data.repository.AppRepository
import coil.request.ImageRequest
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import java.io.File
import java.time.Instant
import java.util.Locale
import java.util.concurrent.atomic.AtomicBoolean

data class NativeNarrationUiState(
    val sceneId: String = "",
    val loading: Boolean = false,
    val generating: Boolean = false,
    val available: Boolean = false,
    val hasScript: Boolean = false,
    val jobId: String? = null,
    val jobStatus: String? = null,
    val jobProgress: Int = 0,
    val artifactId: String? = null,
    val audioFile: File? = null,
    val playing: Boolean = false,
    val speaking: Boolean = false,
    val error: String? = null,
)

data class NativeClassmateUiState(
    val roster: List<NativeClassmate> = emptyList(),
    val messages: List<NativeClassmateMessage> = emptyList(),
    val loading: Boolean = false,
    val busy: Boolean = false,
    val error: String? = null,
    val selectedAgentId: String? = null,
)

data class NativeEndSummary(
    val activeSeconds: Long,
    val pagesVisited: Int,
    val totalPages: Int,
    val autoCorrect: Int,
    val autoTotal: Int,
    val sessionXp: Int,
    val achievements: List<String>,
    val completed: Boolean,
)

data class NativeSequenceUiState(
    val sceneId: String? = null,
    val total: Int = 0,
    val current: Int = 0,
    val actionId: String? = null,
    val active: Boolean = false,
    val paused: Boolean = false,
    val preparing: Boolean = false,
    val fullTranscript: Boolean = false,
)

data class NativeClassroomUiState(
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val offline: Boolean = false,
    val error: String? = null,
    val notice: String? = null,
    val plan: NativePlaybackPlan? = null,
    val document: NativeStageDocument? = null,
    val revision: Int = 0,
    val index: Int = 0,
    val page: NativePageState = NativePageState(),
    val disposition: NativeSceneDisposition = NativeSceneDisposition(NativeSceneMode.UNAVAILABLE, "missing_scene_content"),
    val rewards: ClassroomRewards = ClassroomRewardsEngine.empty(),
    val level: ClassroomLevel = ClassroomRewardsEngine.levelOf(0),
    val sessionXp: Int = 0,
    val unlocked: List<String> = emptyList(),
    val quiz: NativeQuizUiState? = null,
    val narration: NativeNarrationUiState = NativeNarrationUiState(),
    val classmates: NativeClassmateUiState = NativeClassmateUiState(),
    val whiteboardOpen: Boolean = false,
    val activeAction: NativeAction? = null,
    val spotlightElementId: String? = null,
    val laserElementId: String? = null,
    val videoUrl: String? = null,
    val speech: String? = null,
    val sequence: NativeSequenceUiState = NativeSequenceUiState(),
    val endSummary: NativeEndSummary? = null,
    val pageFlipMs: Long? = null,
    val firstPaintMs: Long? = null,
    val peakMemoryBytes: Long = 0,
    val showMetrics: Boolean = false,
    /** 缩放与讲义/PPT 选择放在会话状态里，旋转后仍保留。 */
    val zoom: Float = 1f,
    val readNotes: Boolean = false,
    val experimentValues: Map<String, Double> = emptyMap(),
) {
    val currentScenePlan: NativeScenePlan? get() = plan?.scenes?.getOrNull(index)
    val currentSceneId: String? get() = currentScenePlan?.id
    val currentScene get() = document?.scene(currentSceneId)
    val currentSlide: NativeSlide? get() = currentSceneId?.let { document?.slideByScene?.get(it) }
    val currentQuiz: NativeQuiz? get() = currentSceneId?.let { document?.quizByScene?.get(it) }
    val currentPbl: NativePblProject? get() = currentSceneId?.let { document?.pblByScene?.get(it) }
    private val currentInteractive
        get() = if (disposition.mode == NativeSceneMode.NATIVE && currentScenePlan?.type == "interactive") {
            document?.interactiveByScene?.get(currentSceneId)
        } else null
    val currentLimitExperiment get() = currentInteractive?.limitExperiment
    internal val currentSpatialExperiment get() = currentInteractive?.spatialExperiment
    internal val currentParameterExperiment get() = currentInteractive?.parameterExperiment
    internal val hasNativeExperiment
        get() = currentLimitExperiment != null || currentSpatialExperiment != null || currentParameterExperiment != null
    val canTeachSlide: Boolean
        get() = currentSlide?.let { slide ->
            sequence.total > 0 || narration.audioFile != null ||
                currentScene?.actions?.any(NativeAction::hasLectureSpeech) == true ||
                NativeClassroomText.lectureParagraphs(slide).isNotEmpty()
        } == true
}

private fun NativeAction.hasLectureSpeech(): Boolean = type == "speech" && supported &&
    (!audioUrl.isNullOrBlank() || !speech.isNullOrBlank() || description.isNotBlank())

/**
 * 原生课堂的单一状态机。
 *
 * 并发规则：
 * - 每次换课堂/换页/换账号都递增 generation，迟到的文档、测验、讲解响应直接丢弃；
 * - 翻页先停音频与朗读，再切页；
 * - 学习记录与奖励由稳定身份 + 首次访问/首次交卷结算，原生/兼容来回切换不重复加分。
 */
class NativeClassroomViewModel(
    application: Application,
    private val repository: AppRepository,
    private val ref: NativeClassroomRef,
    private val now: () -> Long = { SystemClock.elapsedRealtime() },
) : AndroidViewModel(application) {

    private val _uiState = MutableStateFlow(NativeClassroomUiState())
    val uiState: StateFlow<NativeClassroomUiState> = _uiState.asStateFlow()
    private val experimentControls = mutableMapOf<Pair<String, Int>, ClassroomLimitExperiment.Controls>()
    private val parameterValuesByScene = mutableMapOf<Pair<String, Int>, Map<String, Double>>()
    private val spatialControlsByScene = mutableMapOf<Pair<String, Int>, NativeSpatialControls>()

    internal fun spatialControls(sceneId: String, revision: Int, playAnimation: Boolean): NativeSpatialControls =
        spatialControlsByScene.getOrPut(sceneId to revision) { NativeSpatialControls(playAnimation) }

    internal fun updateExperimentValues(
        sceneId: String,
        revision: Int,
        changes: Map<String, Any?>?,
        action: NativeAction? = null,
    ): Boolean {
        val state = _uiState.value
        if (sessionBlocked || state.currentSceneId != sceneId || state.revision != revision) return false
        val experiment = state.currentParameterExperiment ?: return false
        val validated = experiment.validatedChanges(changes) ?: return false
        val values = state.experimentValues + validated
        parameterValuesByScene[sceneId to revision] = values
        _uiState.update {
            it.copy(
                experimentValues = values,
                activeAction = action ?: it.activeAction,
                notice = if (action == null) it.notice else null,
            )
        }
        return true
    }

    internal fun savedExperimentControls(sceneId: String, revision: Int): ClassroomLimitExperiment.Controls? =
        experimentControls[sceneId to revision]

    internal fun saveExperimentControls(sceneId: String, revision: Int, controls: ClassroomLimitExperiment.Controls) {
        if (!sessionBlocked) experimentControls[sceneId to revision] = controls
    }

    private val context = application.applicationContext
    private val mediaBasePath = ClassroomMediaPolicy.mediaBasePath(BuildConfig.API_BASE_URL, ref)

    /**
     * 一次播放会话独占的媒体资源。
     *
     * 退出页面、关闭弹窗或换号时整体释放；重新进入同一课堂会创建新实例。
     * 旋转不会结束会话，因此仍复用同一实例，当前页、缩放和草稿都由 ViewModel 保留。
     */
    @androidx.annotation.OptIn(UnstableApi::class)
    private inner class PlaybackSession(val accountScope: String) {
        private val released = AtomicBoolean(false)
        val cache = NativeClassroomCache(context, accountScope, ref)
        val mediaSession = ClassroomMediaSession(accountScope, ref)
        val tts = AndroidTextToSpeechSynthesizer(context)
        val dataSourceFactory: DataSource.Factory = DefaultDataSource.Factory(
            context,
            ClassroomMediaDataSourceFactory(
                client = ApiClient.classroomMediaHttpClient(ref, followRedirects = false),
                ref = ref,
                apiBaseUrl = BuildConfig.API_BASE_URL,
            ),
        )
        val player: ExoPlayer =
            ExoPlayer.Builder(context, DefaultMediaSourceFactory(dataSourceFactory)).build()

        init {
            player.setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(C.USAGE_MEDIA)
                    .setContentType(C.AUDIO_CONTENT_TYPE_SPEECH)
                    .build(),
                /* handleAudioFocus = */ true,
            )
            player.setHandleAudioBecomingNoisy(true)
            player.addListener(object : Player.Listener {
                override fun onPlaybackStateChanged(playbackState: Int) {
                    if (playbackState == Player.STATE_ENDED) {
                        updateNarration { it.copy(playing = false) }
                        val waiter = sequenceAudioWaiter ?: return
                        if (sequenceAudioToken != sequenceToken) return
                        if (sequenceAudioMediaId != player.currentMediaItem?.mediaId) return
                        val duration = player.duration
                        if (duration != C.TIME_UNSET && player.currentPosition < duration - 150) return
                        waiter.complete(null)
                    } else if (playbackState == Player.STATE_IDLE) {
                        updateNarration { it.copy(playing = false) }
                    }
                }

                override fun onPlayerError(error: androidx.media3.common.PlaybackException) {
                    val waiter = sequenceAudioWaiter
                    if (waiter != null &&
                        sequenceAudioToken == sequenceToken &&
                        sequenceAudioMediaId == player.currentMediaItem?.mediaId
                    ) {
                        waiter.complete(error.message ?: "音频播放失败")
                    }
                    updateNarration { it.copy(playing = false, error = "音频播放失败") }
                    _uiState.update {
                        it.copy(notice = "音频播放失败，可重试或改用系统朗读。")
                    }
                }
            })
        }

        fun release() {
            if (!released.compareAndSet(false, true)) return
            runCatching {
                player.stop()
                player.release()
            }
            runCatching { tts.shutdown() }
            cache.release()
            mediaSession.invalidate()
        }
    }

    private var playback: PlaybackSession? = null
    private var sessionBlocked = false

    /** 当前播放会话的图片缓存；会话未启动或已释放时为 null。 */
    val cache: NativeClassroomCache? get() = playback?.cache

    /** 视频弹窗与讲解音频共用的媒体数据源；会话未启动时为 null。 */
    val mediaDataSourceFactory: DataSource.Factory? get() = playback?.dataSourceFactory

    private val activePlayer: ExoPlayer? get() = playback?.player
    private val activeTts: AndroidTextToSpeechSynthesizer? get() = playback?.tts

    private var loadJob: Job? = null
    private var narrationJob: Job? = null
    private var classmateJob: Job? = null
    private var actionJob: Job? = null
    private var sequenceJob: Job? = null
    private var sequenceToken = 0
    private var sequenceSceneId: String? = null
    private var sequenceAudioWaiter: CompletableDeferred<String?>? = null
    private var sequenceAudioMediaId: String? = null
    private var sequenceAudioToken = 0
    private var sequenceUtterance: CompletableDeferred<LectureUtterance>? = null
    private var sequenceVideoWaiter: CompletableDeferred<String?>? = null
    private var sequenceWhiteboardWaiter: CompletableDeferred<Unit>? = null
    private var prefetchJob: Job? = null
    private val prefetchDisposables = mutableListOf<coil.request.Disposable>()
    private var positionJob: Job? = null
    private var rewardsJob: Job? = null
    private var metricsJob: Job? = null

    private var loadGeneration = 0
    private var narrationGeneration = 0
    private var activeSceneId: String? = null
    private var pageRequestedAt = 0L
    private var loadStartedAt = 0L
    private var firstPaintRecorded = false
    private var enteredAtIso: String = Instant.now().toString()
    private var activeSince = now()
    private var activeAccumulatedMs = 0L
    private var hostActive = true
    private var recorded = false
    private var entryRecorded = false
    private var initialAccountScope = repository.classroomAccountScope()
    private val localStateKey = repository.classroomLocalKey(ref, initialAccountScope)
    private val positionWriteKey = "$localStateKey:position"
    private val rewardsWriteKey = "$localStateKey:rewards"
    private val draftWriteKey = "$localStateKey:draft"
    private var rewardsWritable = true
    private var localReadNotice: String? = null
    private val sessionFlusher = ClassroomSessionFlusher(onResult = ::logWriteResult)
    private var quizCoordinator: ClassroomQuizCoordinator? = null
    private val quizWriteMutex = Mutex()

    init {
        loadStartedAt = now()
        observeAccountSwitch()
    }

    /**
     * 启动（或复用）一次播放会话。旋转后播放器重新进入组合时直接复用现有会话；
     * 关闭弹窗或退出页面会先 [endSession]，再次进入时创建全新的播放器与缓存。
     */
    fun startSession() {
        if (playback != null || sessionBlocked) return
        if (repository.classroomAccountScope() != initialAccountScope) {
            sessionBlocked = true
            _uiState.update {
                it.copy(loading = false, refreshing = false, error = "账号已切换，课堂已停止。")
            }
            return
        }
        playback = PlaybackSession(initialAccountScope)
        load()
    }

    /**
     * 结束一次播放会话。顺序固定为：
     * 1. 捕获当前学习位置、奖励与待保存草稿；
     * 2. 在独立 IO 作用域按原账号可靠落盘（不受 ViewModel 清理取消）；
     * 3. 取消本会话所有任务并释放播放器、TTS、图片缓存与媒体监听；
     * 4. 重置会话状态。重复调用是幂等的。
     */
    fun endSession() {
        val session = playback
        if (session == null) {
            resetSessionState()
            return
        }
        playback = null
        val sameAccount = repository.classroomAccountScope() == initialAccountScope
        val position = _uiState.value.currentSceneId
        val rewards = _uiState.value.rewards
        val draftFlush = if (sameAccount) quizCoordinator?.takeDraftFlush() else null
        if (sameAccount) recordStudyVisit(false)
        quizCoordinator?.close()
        quizCoordinator = null
        cancelSessionJobs()
        flushSessionState(sameAccount, position, rewards, draftFlush)
        session.release()
        resetSessionState()
    }

    private fun cancelSessionJobs() {
        loadJob?.cancel(); loadJob = null
        narrationJob?.cancel(); narrationJob = null
        classmateJob?.cancel(); classmateJob = null
        actionJob?.cancel(); actionJob = null
        prefetchJob?.cancel(); prefetchJob = null
        prefetchDisposables.forEach { runCatching { it.dispose() } }
        prefetchDisposables.clear()
        positionJob?.cancel(); positionJob = null
        rewardsJob?.cancel(); rewardsJob = null
        metricsJob?.cancel(); metricsJob = null
        resetSequenceRuntime(_uiState.value.currentSceneId)
    }

    /**
     * 使用独立作用域落盘：ViewModel.onCleared 取消 viewModelScope 后仍能完成。
     * 位置与奖励始终写回会话所属账号，即使账号已经切换。
     *
     * 三项写入互相隔离：位置失败不会跳过奖励与草稿；旧会话的迟到快照
     * 会因写入票据过期而让位于新会话的更新；草稿发网前再核对一次账号。
     */
    private fun flushSessionState(
        sameAccount: Boolean,
        position: String?,
        rewards: ClassroomRewards,
        draftFlush: (suspend () -> Unit)?,
    ) {
        val saveRewards = rewardsWritable && (rewards.visited.isNotEmpty() || rewards.xp > 0)
        val writes = buildList {
            if (position != null) {
                add(
                    ClassroomStateWrite(
                        key = positionWriteKey,
                        label = "position",
                        grant = ClassroomLocalWriteGate.grant(positionWriteKey),
                        save = {
                            repository.saveClassroomPosition(ref, position, initialAccountScope)
                        },
                    ),
                )
            }
            if (saveRewards) {
                add(
                    ClassroomStateWrite(
                        key = rewardsWriteKey,
                        label = "rewards",
                        grant = ClassroomLocalWriteGate.grant(rewardsWriteKey),
                        save = {
                            repository.saveClassroomRewardsRaw(
                                ref,
                                ClassroomRewardsCodec.encode(rewards),
                                initialAccountScope,
                            )
                        },
                    ),
                )
            }
            if (sameAccount && draftFlush != null) {
                add(
                    ClassroomStateWrite(
                        key = draftWriteKey,
                        label = "draft",
                        grant = ClassroomLocalWriteGate.grant(draftWriteKey),
                        save = {
                            // 发送前重新核对账号；换号后旧账号的草稿不能发出去。
                            if (repository.classroomAccountScope() == initialAccountScope) draftFlush()
                        },
                    ),
                )
            }
        }
        sessionFlusher.flush(writes)
    }

    private fun logWriteResult(result: ClassroomWriteResult) {
        if (result.status == ClassroomWriteStatus.SAVED) return
        Log.w(
            "NativeClassroom",
            "classroom_state_write label=${result.label} status=${result.status} attempts=${result.attempts}",
        )
    }

    /** 本地诊断/学习记录失败不应打断课堂；协程取消仍向上抛出。 */
    private suspend fun ignoreStorageFailure(block: suspend () -> Unit) {
        try {
            block()
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Exception) {
            // 课堂内容仍可继续使用，失败细节不写入日志。
        }
    }

    private fun resetSessionState() {
        parameterValuesByScene.clear()
        spatialControlsByScene.clear()
        loadGeneration++
        narrationGeneration++
        activeSceneId = null
        pageRequestedAt = 0L
        loadStartedAt = now()
        firstPaintRecorded = false
        recorded = false
        entryRecorded = false
        hostActive = true
        activeSince = now()
        activeAccumulatedMs = 0L
        enteredAtIso = Instant.now().toString()
        rewardsWritable = true
        localReadNotice = null
        _uiState.value = NativeClassroomUiState()
    }

    private fun beginMediaRequest(): Int? = playback?.mediaSession?.beginRequest()

    private fun isMediaRequestCurrent(generation: Int): Boolean =
        playback?.mediaSession?.isCurrent(generation, repository.classroomAccountScope(), ref) == true

    fun load(forceNetwork: Boolean = false) {
        val sessionCache = playback?.cache ?: return
        loadJob?.cancel()
        val generation = ++loadGeneration
        _uiState.update { it.copy(loading = it.plan == null, refreshing = it.plan != null, error = null) }
        loadStartedAt = now()
        firstPaintRecorded = false

        loadJob = viewModelScope.launch {
            val rewardsRead = withContext(Dispatchers.IO) {
                readClassroomLocal { repository.classroomRewardsRaw(ref) }
            }
            val decoded = when (rewardsRead) {
                is ClassroomLocalRead.Value -> ClassroomRewardsCodec.decodeResult(rewardsRead.value)
                ClassroomLocalRead.Missing -> ClassroomRewardsDecodeResult.Missing
                is ClassroomLocalRead.Failed -> null
            }
            val savedRewards = decoded?.rewards ?: ClassroomRewardsEngine.empty()
            val rewardsDamaged = decoded is ClassroomRewardsDecodeResult.Unreadable
            rewardsWritable = when {
                rewardsRead.failed -> false
                decoded != null -> decoded.allowsWrite
                else -> true
            }
            val positionRead = withContext(Dispatchers.IO) {
                readClassroomLocal { repository.classroomPosition(ref) }
            }
            val savedScene = (positionRead as? ClassroomLocalRead.Value)?.value
            val readNotice = when {
                rewardsDamaged && positionRead.failed ->
                    "本地奖励记录已损坏、学习位置读取失败；本次不会自动结算或覆盖记录。"
                rewardsDamaged ->
                    "本地奖励记录已损坏，已保留原记录；本次不会自动结算奖励。"
                rewardsRead.failed && positionRead.failed ->
                    "本地学习进度读取失败，本次不会覆盖已有记录。"
                rewardsRead.failed ->
                    "本地奖励记录读取失败，本次不会覆盖已有记录。"
                positionRead.failed ->
                    "本地学习位置读取失败，本次从课堂起始页开始。"
                else -> null
            }
            localReadNotice = readNotice
            withContext(Dispatchers.Main) {
                _uiState.update {
                    it.copy(
                        rewards = savedRewards,
                        level = ClassroomRewardsEngine.levelOf(savedRewards.xp),
                        unlocked = savedRewards.achievements.toList(),
                        notice = readNotice ?: it.notice,
                    )
                }
            }
            if (generation != loadGeneration) return@launch
            if (ref.source != NativeClassroomSource.MANAGED) {
                loadClassic(savedScene, generation, forceNetwork, sessionCache)
                return@launch
            }
            if (!forceNetwork) {
                val cached = withContext(Dispatchers.IO) {
                    val document = sessionCache.readStage()
                    val playback = sessionCache.readPlayback()
                    val cachedRevision = sessionCache.readRevision()
                    if (document != null && playback != null && playback.revision == cachedRevision) {
                        Triple(document, cachedRevision, playback)
                    } else {
                        null
                    }
                }
                if (generation != loadGeneration) return@launch
                if (cached != null) {
                    val parsed = withContext(Dispatchers.Default) {
                        NativeClassroomParser.parseDocument(
                            document = cached.first,
                            stageId = ref.stageId,
                            fallbackTitle = ref.title,
                            revision = cached.second,
                            dslVersion = cached.third.dslVersion.orEmpty(),
                        )
                    }
                    val cachedPlan = withContext(Dispatchers.Default) {
                        NativeClassroomParser.parsePlan(cached.third)
                    }
                    withContext(Dispatchers.Main) {
                        if (generation != loadGeneration) return@withContext
                        applyLoaded(
                            plan = cachedPlan,
                            document = parsed,
                            preferSceneId = savedScene ?: _uiState.value.currentSceneId,
                            fromCache = true,
                        )
                    }
                }
            }

            val (playbackResult, stageResult) = coroutineScope {
                val playback = async {
                    repository.magicClassStagePlayback(
                        ref.courseId,
                        ref.workspaceId,
                        ref.stageId,
                        savedScene ?: _uiState.value.currentSceneId,
                    )
                }
                val stage = async { repository.magicClassStage(ref.courseId, ref.workspaceId, ref.stageId) }
                playback.await() to stage.await()
            }
            if (generation != loadGeneration) return@launch
            val playback = playbackResult.getOrNull()
            val stage = stageResult.getOrNull()
            if (playback != null && stage != null) {
                val parsed = withContext(Dispatchers.Default) { NativeClassroomParser.parseStage(stage) }
                val plan = withContext(Dispatchers.Default) { NativeClassroomParser.parsePlan(playback) }
                withContext(Dispatchers.IO) {
                    sessionCache.writeStage(stage.revision, stage.document.orEmpty())
                    sessionCache.writePlayback(playback)
                }
                if (generation != loadGeneration) return@launch
                withContext(Dispatchers.Main) {
                    if (generation != loadGeneration) return@withContext
                    applyLoaded(
                        plan = plan,
                        document = parsed,
                        preferSceneId = savedScene ?: _uiState.value.currentSceneId,
                        fromCache = false,
                    )
                }
            } else {
                val failure = stageResult.exceptionOrNull() ?: playbackResult.exceptionOrNull()
                val cached = _uiState.value.plan != null && _uiState.value.document != null
                withContext(Dispatchers.Main) {
                    _uiState.update {
                        it.copy(
                            loading = false,
                            refreshing = false,
                            offline = cached,
                            error = if (cached) null else (failure?.message ?: "课堂内容读取失败"),
                            notice = if (cached) "网络不可用，正在使用本地缓存的课堂内容" else null,
                        )
                    }
                }
            }
        }
    }

    private suspend fun loadClassic(
        savedScene: String?,
        generation: Int,
        forceNetwork: Boolean,
        sessionCache: NativeClassroomCache,
    ) {
        if (!forceNetwork) {
            val cached = withContext(Dispatchers.IO) { sessionCache.readClassicPlayback() }
            if (generation != loadGeneration) return
            if (cached != null) {
                val document = withContext(Dispatchers.Default) { NativeClassroomParser.parsePlayback(cached) }
                val plan = withContext(Dispatchers.Default) { NativeClassroomParser.parsePlaybackPlan(cached) }
                withContext(Dispatchers.Main) {
                    if (generation != loadGeneration) return@withContext
                    applyLoaded(
                        plan = plan,
                        document = document,
                        preferSceneId = savedScene ?: _uiState.value.currentSceneId,
                        fromCache = true,
                    )
                }
            }
        }
        val playback = repository.classroomPlayback(
            ref = ref,
            sceneId = savedScene ?: _uiState.value.currentSceneId,
        ).getOrNull()
        if (generation != loadGeneration) return
        if (playback != null) {
            val document = withContext(Dispatchers.Default) { NativeClassroomParser.parsePlayback(playback) }
            val plan = withContext(Dispatchers.Default) { NativeClassroomParser.parsePlaybackPlan(playback) }
            withContext(Dispatchers.IO) { sessionCache.writeClassicPlayback(playback) }
            if (generation != loadGeneration) return
            withContext(Dispatchers.Main) {
                if (generation != loadGeneration) return@withContext
                applyLoaded(
                    plan = plan,
                    document = document,
                    preferSceneId = savedScene ?: _uiState.value.currentSceneId,
                    fromCache = false,
                )
            }
        } else {
            val cached = _uiState.value.plan != null && _uiState.value.document != null
            withContext(Dispatchers.Main) {
                _uiState.update {
                    it.copy(
                        loading = false,
                        refreshing = false,
                        offline = cached,
                        error = if (cached) null else "课堂播放数据读取失败",
                        notice = if (cached) "网络不可用，正在使用本地缓存的课堂内容" else null,
                    )
                }
            }
        }
    }

    private fun applyLoaded(
        plan: NativePlaybackPlan,
        document: NativeStageDocument,
        preferSceneId: String?,
        fromCache: Boolean,
    ) {
        val previousRevision = _uiState.value.revision
        val target = plan.scenes.indexOfFirst { it.id == preferSceneId }
            .takeIf { it >= 0 } ?: plan.startIndex.coerceIn(0, (plan.scenes.size - 1).coerceAtLeast(0))
        val sceneId = plan.scenes.getOrNull(target)?.id
        val readWarning = localReadNotice
        localReadNotice = null
        _uiState.update {
            it.copy(
                loading = false,
                refreshing = false,
                offline = fromCache,
                error = null,
                notice = readWarning ?: if (fromCache) "正在使用本地缓存，后台继续刷新" else null,
                plan = plan,
                document = document,
                revision = plan.revision,
                index = target,
                page = NativePageState.of(plan.scenes, target),
            )
        }
        evaluateScene(sceneId)
        if (sceneId != null && (sceneId != activeSceneId || plan.revision != previousRevision)) {
            activeSceneId = sceneId
            onSceneChanged(sceneId)
        }
        if (!entryRecorded) {
            entryRecorded = true
            viewModelScope.launch(Dispatchers.IO) {
                ignoreStorageFailure { repository.recordClassroomEntry(ref.identityUrl) }
            }
        }
    }

    fun retry() = load(forceNetwork = true)

    fun clearNotice() {
        _uiState.update { it.copy(notice = null) }
    }

    fun setZoom(value: Float) {
        _uiState.update { it.copy(zoom = value.coerceIn(0.7f, 1.6f)) }
    }

    fun setReadNotes(value: Boolean) {
        if (!value && (_uiState.value.spotlightElementId != null || _uiState.value.laserElementId != null ||
                _uiState.value.sequence.active)) return
        _uiState.update { it.copy(readNotes = value) }
    }

    fun goTo(index: Int) {
        val plan = _uiState.value.plan ?: return
        if (plan.scenes.isEmpty()) return
        val target = index.coerceIn(0, plan.scenes.lastIndex)
        if (target == _uiState.value.index) return
        resetSequenceRuntime(plan.scenes[target].id)
        // 翻页前把旧页草稿交给协调器串行落盘；不阻塞翻页，也不取消在途请求。
        val draftFlush = quizCoordinator?.takeDraftFlush()
        quizCoordinator?.close()
        quizCoordinator = null
        if (draftFlush != null && repository.classroomAccountScope() == initialAccountScope) {
            // UNDISPATCHED：先把旧页草稿排进共享写锁，后续新页保存一定排在它之后。
            viewModelScope.launch(Dispatchers.IO, start = kotlinx.coroutines.CoroutineStart.UNDISPATCHED) {
                withTimeoutOrNull(6_000L) {
                    ignoreStorageFailure { draftFlush() }
                }
            }
        }
        pageRequestedAt = now()
        stopAudio()
        _uiState.update {
            it.copy(index = target, page = NativePageState.of(plan.scenes, target), notice = null)
        }
        val sceneId = plan.scenes[target].id
        evaluateScene(sceneId)
        activeSceneId = sceneId
        onSceneChanged(sceneId)
    }

    fun next() = goTo(_uiState.value.index + 1)

    fun previous() = goTo(_uiState.value.index - 1)

    fun markFirstPainted() {
        if (firstPaintRecorded) return
        firstPaintRecorded = true
        val elapsed = (now() - loadStartedAt).coerceAtLeast(0)
        _uiState.update { it.copy(firstPaintMs = elapsed, peakMemoryBytes = memoryNow()) }
    }

    fun markPagePainted() {
        if (pageRequestedAt <= 0L) return
        val elapsed = (now() - pageRequestedAt).coerceAtLeast(0)
        pageRequestedAt = 0L
        _uiState.update { it.copy(pageFlipMs = elapsed, peakMemoryBytes = memoryNow()) }
    }

    fun toggleMetrics() {
        _uiState.update { it.copy(showMetrics = !it.showMetrics, peakMemoryBytes = memoryNow()) }
        if (_uiState.value.showMetrics) {
            metricsJob?.cancel()
            metricsJob = viewModelScope.launch {
                while (isActive) {
                    delay(1500)
                    _uiState.update { it.copy(peakMemoryBytes = maxOf(it.peakMemoryBytes, memoryNow())) }
                }
            }
        } else {
            metricsJob?.cancel()
        }
    }

    fun onHostResume() {
        if (!hostActive) {
            hostActive = true
            activeSince = now()
        }
    }

    fun onHostPause() {
        if (hostActive) {
            hostActive = false
            activeAccumulatedMs += (now() - activeSince).coerceAtLeast(0)
        }
        resetSequenceRuntime(_uiState.value.currentSceneId)
        prefetchJob?.cancel()
        narrationJob?.cancel()
        actionJob?.cancel()
        playback?.mediaSession?.invalidate()
        stopAudio()
    }

    fun onAccountChanged() {
        if (repository.classroomAccountScope() == initialAccountScope) return
        sessionBlocked = true
        // 换号：位置与奖励按原账号落盘；草稿/学习记录不能写到新账号。
        endSession()
        _uiState.update {
            it.copy(
                error = "账号已切换，课堂已停止。",
                loading = false,
                refreshing = false,
                videoUrl = null,
                speech = null,
            )
        }
    }

    private fun observeAccountSwitch() {
        viewModelScope.launch {
            repository.session.collect {
                onAccountChanged()
            }
        }
    }

    private fun activeSeconds(): Long {
        val current = activeAccumulatedMs + if (hostActive) (now() - activeSince).coerceAtLeast(0) else 0L
        return (current / 1000L).coerceAtLeast(0)
    }

    fun requestEnd(completed: Boolean) {
        onHostPause()
        val quiz = _uiState.value.quiz
        val results = quiz?.results.orEmpty()
        val autoResults = results.values.filter { it.correct != null }
        val summary = NativeEndSummary(
            activeSeconds = activeSeconds(),
            pagesVisited = _uiState.value.rewards.visited.size,
            totalPages = _uiState.value.plan?.scenes?.size ?: 0,
            autoCorrect = autoResults.count { it.correct == true },
            autoTotal = autoResults.size,
            sessionXp = _uiState.value.sessionXp,
            achievements = _uiState.value.unlocked,
            completed = completed,
        )
        _uiState.update { it.copy(endSummary = summary) }
    }

    fun dismissEnd() {
        _uiState.update { it.copy(endSummary = null) }
        onHostResume()
    }

    fun finish(completed: Boolean) {
        recordStudyVisit(completed)
        _uiState.update { it.copy(endSummary = null) }
        // 退出即结束播放会话；再次进入同一课堂会创建新的播放器、TTS 与缓存。
        endSession()
    }

    private fun recordStudyVisit(completed: Boolean) {
        if (recorded) return
        if (repository.classroomAccountScope() != initialAccountScope) return
        recorded = true
        if (!hostActive) {
            // onHostPause 已累计；保持幂等。
        } else {
            activeAccumulatedMs += (now() - activeSince).coerceAtLeast(0)
            hostActive = false
        }
        repository.recordClassroomStudyVisit(
            ref.identityUrl,
            enteredAtIso,
            activeSeconds(),
            completed,
        )
    }

    override fun onCleared() {
        recordStudyVisit(false)
        endSession()
        super.onCleared()
    }

    // ── 页面与动作 ───────────────────────────────────────────────────────────

    private fun evaluateScene(sceneId: String?) {
        val planScene = _uiState.value.plan?.scenes?.firstOrNull { it.id == sceneId }
            ?: return
        val documentScene = _uiState.value.document?.scene(sceneId)
        val slide = _uiState.value.document?.slideByScene?.get(sceneId)
        val quiz = _uiState.value.document?.quizByScene?.get(sceneId)
        val pbl = _uiState.value.document?.pblByScene?.get(sceneId)
        val interactive = _uiState.value.document?.interactiveByScene?.get(sceneId)
        val actions = documentScene?.actions.orEmpty()
        val canRunExperiment = interactive?.limitExperiment != null &&
            (planScene.widgetType == null || planScene.widgetType == "simulation") &&
            actions.none { action ->
                action.supported && action.type.startsWith("widget_") &&
                    (action.type != "widget_highlight" || ClassroomLimitExperiment.Highlight.fromSelector(action.widgetTarget) == null)
            }
        val parameterExperiment = interactive?.parameterExperiment
        val canRunParameterExperiment = (planScene.widgetType == null || planScene.widgetType == "simulation") &&
            parameterExperiment?.supportsActions(actions) == true
        val canRunSpatialScene = (planScene.widgetType == null || planScene.widgetType == "visualization3d") &&
            interactive?.spatialExperiment?.supportsActions(actions) == true
        val hasContent = when (planScene.type) {
            "slide" -> slide != null && slide.elements.isNotEmpty()
            "quiz" -> quiz != null && quiz.questions.isNotEmpty()
            "pbl" -> pbl != null && pbl.milestones.isNotEmpty()
            "interactive" -> !interactive?.html.isNullOrBlank() ||
                !interactive?.url.isNullOrBlank() ||
                planScene.sandbox.isNotBlank()
            else -> documentScene != null && documentScene.content.isNotEmpty()
        }
        val disposition = NativePlaybackPolicy.decide(
            renderKind = planScene.renderKind,
            sceneType = planScene.type,
            hasDocument = documentScene != null,
            hasRenderableContent = hasContent,
            fallbackAvailable = !ref.webFallbackUrl.isNullOrBlank(),
            renderReason = planScene.renderReason,
            hasNativeExperiment = canRunExperiment || canRunParameterExperiment,
            hasNativeSpatialScene = canRunSpatialScene,
        )
        _uiState.update { state ->
            val values = if (disposition.mode == NativeSceneMode.NATIVE && canRunParameterExperiment) {
                parameterValuesByScene[planScene.id to state.revision] ?: parameterExperiment.initialValues
            } else emptyMap()
            state.copy(disposition = disposition, experimentValues = values)
        }
    }

    private fun onSceneChanged(sceneId: String) {
        resetSequenceRuntime(sceneId)
        stopAudio()
        narrationJob?.cancel()
        prefetchJob?.cancel()
        actionJob?.cancel()
        playback?.mediaSession?.invalidate()
        quizCoordinator?.close()
        quizCoordinator = null
        val planScene = _uiState.value.plan?.scenes?.firstOrNull { it.id == sceneId }
        _uiState.update {
            it.copy(
                quiz = null,
                narration = NativeNarrationUiState(sceneId = sceneId),
                sequence = NativeSequenceUiState(sceneId = sceneId, total = planScene?.steps?.size ?: 0),
                spotlightElementId = null,
                laserElementId = null,
                speech = null,
                activeAction = null,
                videoUrl = null,
            )
        }
        settleVisit(sceneId)
        val positionAccountScope = repository.classroomAccountScope()
        positionJob?.cancel()
        if (positionAccountScope == initialAccountScope) {
            // 翻页落盘失败只影响下一次续播的起点，不打断本节课堂。
            val write = ClassroomStateWrite(
                key = positionWriteKey,
                label = "position",
                grant = ClassroomLocalWriteGate.grant(positionWriteKey),
                save = {
                    if (repository.classroomAccountScope() == positionAccountScope) {
                        repository.saveClassroomPosition(ref, sceneId, positionAccountScope)
                    }
                },
            )
            positionJob = viewModelScope.launch(Dispatchers.IO) {
                ClassroomSessionFlusher(budgetMs = 3_000L, itemBudgetMs = 1_500L)
                    .run(listOf(write))
            }
        }
        if (planScene?.type == "quiz") {
            loadQuiz(sceneId)
        }
        loadNarration(sceneId)
        prefetchAdjacent(sceneId)
    }

    private fun settleVisit(sceneId: String) {
        // 去重依据不可靠时暂停自动结算，避免按首次到访重复发奖或覆盖原文。
        if (!rewardsWritable) return
        val state = _uiState.value
        val total = state.plan?.scenes?.size ?: 0
        val result: ClassroomRewardResult = ClassroomRewardsEngine.visit(
            rewards = state.rewards,
            sceneId = sceneId,
            totalScenes = total,
            now = Instant.now().toString(),
        )
        if (result.awardedXp == 0 && result.unlocked.isEmpty()) return
        _uiState.update {
            it.copy(
                rewards = result.state,
                level = ClassroomRewardsEngine.levelOf(result.state.xp),
                sessionXp = it.sessionXp + result.awardedXp,
                unlocked = (it.unlocked + result.unlocked).distinct(),
            )
        }
        persistRewards(result.state)
    }

    private fun settleQuiz(sceneId: String, correct: Int, total: Int) {
        // 账本损坏时不结算测验奖励，保留原有测验去重记录。
        if (!rewardsWritable) return
        val state = _uiState.value
        val result = ClassroomRewardsEngine.grade(
            rewards = state.rewards,
            sceneId = sceneId,
            correct = correct,
            total = total,
            totalScenes = state.plan?.scenes?.size ?: 0,
            now = Instant.now().toString(),
        )
        if (result.awardedXp == 0 && result.unlocked.isEmpty()) return
        _uiState.update {
            it.copy(
                rewards = result.state,
                level = ClassroomRewardsEngine.levelOf(result.state.xp),
                sessionXp = it.sessionXp + result.awardedXp,
                unlocked = (it.unlocked + result.unlocked).distinct(),
            )
        }
        persistRewards(result.state)
    }

    private fun persistRewards(rewards: ClassroomRewards) {
        // 账本读不出来时只保留本次内存中的展示，不覆盖已有记录。
        if (!rewardsWritable) return
        val accountScope = repository.classroomAccountScope()
        if (accountScope != initialAccountScope) return
        rewardsJob?.cancel()
        val write = ClassroomStateWrite(
            key = rewardsWriteKey,
            label = "rewards",
            grant = ClassroomLocalWriteGate.grant(rewardsWriteKey),
            save = {
                repository.saveClassroomRewardsRaw(
                    ref,
                    ClassroomRewardsCodec.encode(rewards),
                    accountScope,
                )
            },
        )
        rewardsJob = viewModelScope.launch(Dispatchers.IO) {
            ClassroomSessionFlusher(budgetMs = 3_000L, itemBudgetMs = 1_500L)
                .run(listOf(write))
        }
    }

    fun triggerAction(action: NativeAction) {
        if (_uiState.value.sequence.active) {
            resetSequenceRuntime(_uiState.value.currentSceneId)
            stopAudio()
        }
        triggerActionInternal(action)
    }

    private fun triggerActionInternal(action: NativeAction) {
        if (!action.supported) {
            _uiState.update {
                it.copy(notice = action.reason ?: "该课堂动作需要兼容课堂运行时。")
            }
            return
        }
        when (action.type) {
            "spotlight", "widget_highlight" -> {
                val target = if (action.type == "widget_highlight" && _uiState.value.hasNativeExperiment) {
                    action.widgetTarget
                } else action.elementId
                _uiState.update {
                    it.copy(
                        activeAction = action,
                        spotlightElementId = target,
                        laserElementId = null,
                        notice = null,
                    )
                }
                actionJob?.cancel()
                actionJob = viewModelScope.launch {
                    delay(action.durationMs.takeIf { it > 0 } ?: 3200L)
                    _uiState.update { it.copy(spotlightElementId = null, laserElementId = null) }
                }
            }
            "laser" -> {
                _uiState.update {
                    it.copy(
                        activeAction = action,
                        laserElementId = action.elementId,
                        spotlightElementId = null,
                        notice = null,
                    )
                }
                actionJob?.cancel()
                actionJob = viewModelScope.launch {
                    delay(action.durationMs.takeIf { it > 0 } ?: 2200L)
                    _uiState.update { it.copy(spotlightElementId = null, laserElementId = null) }
                }
            }
            "speech" -> {
                _uiState.update {
                    it.copy(activeAction = action, speech = action.speech ?: action.description, notice = null)
                }
                action.audioUrl?.takeIf { it.isNotBlank() }?.let(::playSpeechAudio)
            }
            "play_video" -> {
                val resolved = resolveVideoSource(action)
                _uiState.update {
                    it.copy(
                        activeAction = action,
                        videoUrl = resolved,
                        notice = if (resolved == null) "视频资源未下发，暂时无法播放。" else null,
                    )
                }
            }
            "wb_open" -> openWhiteboard()
            "widget_setState", "widget_set_state" -> {
                val state = _uiState.value
                val updated = state.currentSceneId?.let { sceneId ->
                    updateExperimentValues(sceneId, state.revision, action.widgetState, action)
                } == true
                if (!updated) _uiState.update { it.copy(notice = "这个课堂动作需要在兼容课堂中完成。") }
            }
            "discussion" -> _uiState.update {
                it.copy(activeAction = action, classmates = it.classmates.copy(error = null), notice = null)
            }
            else -> _uiState.update {
                it.copy(
                    activeAction = action,
                    notice = action.description.ifBlank {
                        "这个课堂动作需要在兼容课堂中完成。"
                    },
                )
            }
        }
    }

    fun startLecture() {
        val state = _uiState.value
        val slide = state.currentSlide ?: return
        val scene = state.currentScenePlan ?: return
        if (state.disposition.mode != NativeSceneMode.NATIVE) return
        if (scene.steps.isNotEmpty()) {
            startSequence()
            return
        }
        val authoredSpeech = state.currentScene?.actions.orEmpty().filter(NativeAction::hasLectureSpeech)
        val cachedNarration = state.narration.audioFile.takeIf { state.narration.sceneId == scene.id }
        val useSceneNarration = authoredSpeech.isEmpty() && ref.source == NativeClassroomSource.MANAGED &&
            (cachedNarration != null || (!state.offline && (state.narration.loading || state.narration.available)))
        val speechActions = authoredSpeech.ifEmpty {
            val paragraphs = NativeClassroomText.lectureParagraphs(slide)
            val title = state.currentScene?.title ?: scene.title
            paragraphs.filterNot { it == title }.ifEmpty { listOf(title) }.mapIndexed { index, text ->
                NativeAction(id = "lecture-${scene.id}-$index", type = "speech", speech = text)
            }
        }
        if (speechActions.isEmpty()) return
        val steps = speechActions.mapIndexed { index, action ->
            ClassroomSequenceStep(index, action.id, action.type, "sync", action)
        }
        playSequence(scene.id, steps, useSceneNarration)
    }

    /** 按服务端 steps 顺序播放本页动作；单步动作仍走 [triggerAction]。 */
    fun startSequence() {
        val state = _uiState.value
        val scene = state.currentScenePlan ?: return
        if (state.disposition.mode != NativeSceneMode.NATIVE) {
            _uiState.update { it.copy(notice = "本页需要兼容课堂运行时，顺序播放暂不可用。") }
            return
        }
        if (scene.steps.isEmpty()) {
            _uiState.update { it.copy(notice = "本页没有下发动作顺序，可继续使用单个动作。") }
            return
        }
        val plan = ClassroomActionSequencePlanner.plan(
            sceneId = scene.id,
            steps = scene.steps,
            actions = state.currentScene?.actions.orEmpty(),
        )
        if (plan.steps.isEmpty()) {
            _uiState.update { it.copy(notice = "本页动作顺序为空，可继续使用单个动作。") }
            return
        }
        playSequence(scene.id, plan.steps)
    }

    private fun playSequence(sceneId: String, steps: List<ClassroomSequenceStep>, useSceneNarration: Boolean = false) {
        resetSequenceRuntime(sceneId)
        stopAudio()
        val token = sequenceToken
        _uiState.update {
            it.copy(
                sequence = NativeSequenceUiState(
                    sceneId = sceneId,
                    total = steps.size,
                    active = true,
                    preparing = useSceneNarration,
                ),
                notice = null,
            )
        }
        sequenceJob = viewModelScope.launch {
            val cachedSpeech = if (useSceneNarration) {
                narrationStatus(sceneId, timeoutMs = 1_500L)?.audioFile
            } else {
                null
            }
            if (!isSequenceCurrent(token, sceneId)) return@launch
            var result = runLectureSequence(sceneId, token, steps, cachedSpeech)
            if (useSceneNarration && cachedSpeech == null && result is ClassroomSequenceResult.Failed &&
                isSequenceCurrent(token, sceneId)
            ) {
                _uiState.update { it.copy(sequence = it.sequence.copy(preparing = true)) }
                val audio = awaitLectureNarration(sceneId)
                if (audio != null && isSequenceCurrent(token, sceneId)) {
                    result = runLectureSequence(sceneId, token, steps, audio)
                }
            }
            if (!isSequenceCurrent(token, sceneId)) return@launch
            when (result) {
                ClassroomSequenceResult.Completed -> _uiState.update { current ->
                    current.copy(
                        sequence = current.sequence.copy(
                            current = current.sequence.total,
                            actionId = null,
                            active = false,
                            paused = false,
                        ),
                    )
                }
                is ClassroomSequenceResult.Failed -> failSequence(result.reason)
                ClassroomSequenceResult.Cancelled -> Unit
            }
        }
    }

    private suspend fun runLectureSequence(
        sceneId: String,
        token: Int,
        steps: List<ClassroomSequenceStep>,
        speechAudio: File?,
    ): ClassroomSequenceResult {
        val playbackSteps = if (speechAudio == null) {
            steps
        } else {
            val transcript = steps.mapNotNull { it.action?.speech }.joinToString("\n\n")
            val speech = NativeAction(id = "lecture-audio-$sceneId", type = "speech", speech = transcript)
            listOf(ClassroomSequenceStep(0, speech.id, speech.type, "sync", speech))
        }
        _uiState.update {
            it.copy(sequence = it.sequence.copy(
                total = playbackSteps.size,
                preparing = false,
                fullTranscript = speechAudio != null,
            ))
        }
        return runClassroomSequence(
            steps = playbackSteps,
            isCurrent = { isSequenceCurrent(token, sceneId) },
            awaitPause = { awaitSequenceResume(token, sceneId) },
            onStep = { index, step ->
                _uiState.update { current ->
                    current.copy(sequence = current.sequence.copy(current = index + 1, actionId = step.actionId))
                }
            },
            execute = { step, awaitPause ->
                executeSequenceStep(step, token, sceneId, awaitPause, speechAudio)
            },
        )
    }

    fun pauseSequence() {
        val sequence = _uiState.value.sequence
        if (!sequence.active || sequence.paused) return
        _uiState.update { it.copy(sequence = it.sequence.copy(paused = true)) }
        if (sequenceAudioWaiter != null) activePlayer?.let { runCatching { it.pause() } }
        if (sequenceUtterance?.complete(LectureUtterance.Paused) == true) activeTts?.stop()
    }

    fun resumeSequence() {
        val sequence = _uiState.value.sequence
        if (!sequence.active || !sequence.paused) return
        _uiState.update { it.copy(sequence = it.sequence.copy(paused = false)) }
        if (sequenceAudioWaiter != null) activePlayer?.let { runCatching { it.play() } }
    }

    fun stopSequence() {
        if (!_uiState.value.sequence.active && sequenceJob == null) return
        resetSequenceRuntime(_uiState.value.currentSceneId)
        stopAudio()
    }

    private suspend fun executeSequenceStep(
        step: ClassroomSequenceStep,
        token: Int,
        sceneId: String,
        awaitPause: suspend () -> Unit,
        cachedSpeech: File?,
    ): ClassroomSequenceStepResult {
        if (!isSequenceCurrent(token, sceneId)) return ClassroomSequenceStepResult.Failed("课堂已切换。")
        step.problem?.let { return ClassroomSequenceStepResult.Failed(it) }
        val action = step.action ?: return ClassroomSequenceStepResult.Failed(
            "顺序动作 ${step.actionId} 没有对应的课堂动作。",
        )
        if (!action.supported) {
            return ClassroomSequenceStepResult.Failed(
                action.reason?.takeIf { it.isNotBlank() } ?: "动作 ${action.type} 当前不支持原生执行。",
            )
        }
        return when (action.type) {
            "speech" -> executeSequenceSpeech(step, action, token, sceneId, awaitPause, cachedSpeech)
            "play_video" -> executeSequenceVideo(step, action, token, sceneId)
            "wb_open" -> executeSequenceWhiteboard(step, action, token, sceneId)
            else -> {
                triggerActionInternal(action)
                if (step.blocking) {
                    awaitSequenceDelay(action.durationMs, token, sceneId, awaitPause)
                }
                ClassroomSequenceStepResult.Completed
            }
        }
    }

    private suspend fun executeSequenceSpeech(
        step: ClassroomSequenceStep,
        action: NativeAction,
        token: Int,
        sceneId: String,
        awaitPause: suspend () -> Unit,
        cachedSpeech: File?,
    ): ClassroomSequenceStepResult {
        if (!step.blocking) {
            triggerActionInternal(action)
            return ClassroomSequenceStepResult.Completed
        }
        val audioUrl = action.audioUrl?.takeIf { it.isNotBlank() }
        val text = action.speech ?: action.description
        if (audioUrl == null && cachedSpeech == null) {
            triggerActionInternal(action)
            val state = _uiState.value
            if ((state.currentSlide != null || state.hasNativeExperiment) && text.isNotBlank()) {
                return speakSequenceText(text, token, sceneId, awaitPause)
            }
            awaitSequenceDelay(speechHoldMs(action), token, sceneId, awaitPause)
            return ClassroomSequenceStepResult.Completed
        }
        val resolved = cachedSpeech?.let(Uri::fromFile)?.toString()
            ?: ClassroomMediaPolicy.resolve(audioUrl, BuildConfig.API_BASE_URL, mediaBasePath)?.url
            ?: return ClassroomSequenceStepResult.Failed(
                "讲解音频地址不可用，可先用系统朗读或从网页入口继续。",
            )
        stopAudio()
        val waiter = CompletableDeferred<String?>()
        val mediaId = "sequence-audio-$token-${step.index}-${System.nanoTime()}"
        sequenceAudioWaiter = waiter
        sequenceAudioToken = token
        sequenceAudioMediaId = mediaId
        _uiState.update {
            it.copy(
                activeAction = action,
                speech = text.takeIf { it.isNotBlank() },
                notice = null,
            )
        }
        val target = activePlayer
        if (target == null) {
            if (sequenceAudioWaiter === waiter) {
                sequenceAudioWaiter = null
                sequenceAudioMediaId = null
                sequenceAudioToken = 0
            }
            return ClassroomSequenceStepResult.Failed("课堂已结束。")
        }
        try {
            target.setMediaItem(MediaItem.Builder().setUri(resolved).setMediaId(mediaId).build())
            target.prepare()
            target.playWhenReady = true
        } catch (error: Exception) {
            if (sequenceAudioWaiter === waiter) {
                sequenceAudioWaiter = null
                sequenceAudioMediaId = null
                sequenceAudioToken = 0
            }
            return ClassroomSequenceStepResult.Failed(
                "讲解音频无法播放：${error.message ?: "播放器初始化失败"}。可重试或改用系统朗读。",
            )
        }
        val failure = try {
            waiter.await()
        } finally {
            if (sequenceAudioWaiter === waiter) {
                sequenceAudioWaiter = null
                sequenceAudioMediaId = null
                sequenceAudioToken = 0
            }
        }
        return failure?.let {
            ClassroomSequenceStepResult.Failed(
                "讲解音频播放失败：$it。可重试或改用系统朗读。",
            )
        } ?: ClassroomSequenceStepResult.Completed
    }

    private sealed interface LectureUtterance {
        data object Finished : LectureUtterance
        data object Paused : LectureUtterance
        data class Failed(val message: String) : LectureUtterance
    }

    private suspend fun speakSequenceText(
        text: String,
        token: Int,
        sceneId: String,
        awaitPause: suspend () -> Unit,
    ): ClassroomSequenceStepResult {
        for (part in text.chunked(320)) {
            while (true) {
                awaitPause()
                if (!isSequenceCurrent(token, sceneId)) return ClassroomSequenceStepResult.Completed
                val waiter = CompletableDeferred<LectureUtterance>()
                sequenceUtterance = waiter
                updateNarration { it.copy(speaking = true, error = null) }
                val result = try {
                    val speaker = activeTts
                    if (speaker == null) {
                        LectureUtterance.Failed("课堂已结束。")
                    } else {
                        speaker.speak(
                            NativeClassroomText.forSpeech(part),
                            onDone = { waiter.complete(LectureUtterance.Finished) },
                            onError = { waiter.complete(LectureUtterance.Failed(it)) },
                        )
                        withTimeoutOrNull(90_000L) { waiter.await() }
                    }
                } finally {
                    if (sequenceUtterance === waiter) {
                        sequenceUtterance = null
                        updateNarration { it.copy(speaking = false) }
                    }
                }
                when (result) {
                    LectureUtterance.Finished -> break
                    LectureUtterance.Paused -> continue
                    is LectureUtterance.Failed -> return ClassroomSequenceStepResult.Failed(result.message)
                    null -> return ClassroomSequenceStepResult.Failed("本段讲解朗读超时，请重试。")
                }
            }
        }
        return ClassroomSequenceStepResult.Completed
    }

    private suspend fun executeSequenceVideo(
        step: ClassroomSequenceStep,
        action: NativeAction,
        token: Int,
        sceneId: String,
    ): ClassroomSequenceStepResult {
        if (!isSequenceCurrent(token, sceneId)) return ClassroomSequenceStepResult.Failed("课堂已切换。")
        val resolved = resolveVideoSource(action)
            ?: return ClassroomSequenceStepResult.Failed(
                "视频资源未下发或不可用，可重试或从网页入口继续。",
            )
        _uiState.update {
            it.copy(activeAction = action, videoUrl = resolved, notice = null)
        }
        if (!step.blocking) return ClassroomSequenceStepResult.Completed
        val waiter = CompletableDeferred<String?>()
        sequenceVideoWaiter = waiter
        val failure = try {
            waiter.await()
        } finally {
            if (sequenceVideoWaiter === waiter) sequenceVideoWaiter = null
        }
        return failure?.let {
            ClassroomSequenceStepResult.Failed(
                "视频播放失败：$it。可重试或从网页入口继续。",
            )
        } ?: ClassroomSequenceStepResult.Completed
    }

    private suspend fun executeSequenceWhiteboard(
        step: ClassroomSequenceStep,
        action: NativeAction,
        token: Int,
        sceneId: String,
    ): ClassroomSequenceStepResult {
        if (!isSequenceCurrent(token, sceneId)) return ClassroomSequenceStepResult.Failed("课堂已切换。")
        if (_uiState.value.document?.whiteboard == null) {
            return ClassroomSequenceStepResult.Failed(
                "本页动作需要白板，但这份课件没有下发白板内容，可从网页入口继续。",
            )
        }
        _uiState.update { it.copy(activeAction = action, whiteboardOpen = true, notice = null) }
        if (!step.blocking) return ClassroomSequenceStepResult.Completed
        val waiter = CompletableDeferred<Unit>()
        sequenceWhiteboardWaiter = waiter
        try {
            waiter.await()
        } finally {
            if (sequenceWhiteboardWaiter === waiter) sequenceWhiteboardWaiter = null
        }
        return ClassroomSequenceStepResult.Completed
    }

    private suspend fun awaitSequenceDelay(
        durationMs: Long,
        token: Int,
        sceneId: String,
        awaitPause: suspend () -> Unit,
    ) {
        var remaining = durationMs.coerceAtLeast(0L)
        while (remaining > 0L) {
            if (!isSequenceCurrent(token, sceneId)) return
            awaitPause()
            if (!isSequenceCurrent(token, sceneId)) return
            val slice = minOf(remaining, 200L)
            delay(slice)
            remaining -= slice
        }
    }

    private suspend fun awaitSequenceResume(token: Int, sceneId: String) {
        while (isSequenceCurrent(token, sceneId) && _uiState.value.sequence.paused) {
            delay(80L)
        }
    }

    private fun isSequenceCurrent(token: Int, sceneId: String): Boolean =
        token == sequenceToken &&
            sequenceSceneId == sceneId &&
            _uiState.value.currentSceneId == sceneId &&
            repository.classroomAccountScope() == initialAccountScope

    private fun speechHoldMs(action: NativeAction): Long {
        if (action.durationMs > 0L) return action.durationMs
        val text = action.speech ?: action.description
        return (800L + text.length * 110L).coerceIn(1200L, 9000L)
    }

    private fun resolveVideoSource(action: NativeAction): String? {
        val direct = action.videoUrl
        val fromSlide = action.elementId?.let { id ->
            _uiState.value.currentSlide?.elements
                ?.filterIsInstance<NativeCanvasElement.Video>()
                ?.firstOrNull { it.id == id }
                ?.source
        }
        return ClassroomMediaPolicy.resolve(
            direct ?: fromSlide,
            BuildConfig.API_BASE_URL,
            mediaBasePath,
        )?.url
    }

    private fun failSequence(reason: String) {
        sequenceToken++
        sequenceSceneId = null
        sequenceJob = null
        sequenceAudioWaiter?.cancel()
        sequenceAudioWaiter = null
        sequenceAudioMediaId = null
        sequenceAudioToken = 0
        sequenceUtterance?.cancel()
        sequenceUtterance = null
        sequenceVideoWaiter?.cancel()
        sequenceVideoWaiter = null
        sequenceWhiteboardWaiter?.cancel()
        sequenceWhiteboardWaiter = null
        _uiState.update {
            it.copy(
                sequence = it.sequence.copy(active = false, paused = false, preparing = false, actionId = null),
                notice = reason,
            )
        }
        stopAudio()
    }

    private fun cancelSequenceForManualMedia() {
        if (!_uiState.value.sequence.active) return
        resetSequenceRuntime(_uiState.value.currentSceneId)
        stopAudio()
    }

    private fun resetSequenceRuntime(sceneId: String?) {
        sequenceToken++
        sequenceJob?.cancel()
        sequenceJob = null
        sequenceSceneId = sceneId
        sequenceAudioWaiter?.cancel()
        sequenceAudioWaiter = null
        sequenceAudioMediaId = null
        sequenceAudioToken = 0
        sequenceUtterance?.cancel()
        sequenceUtterance = null
        sequenceVideoWaiter?.cancel()
        sequenceVideoWaiter = null
        sequenceWhiteboardWaiter?.cancel()
        sequenceWhiteboardWaiter = null
        actionJob?.cancel()
        actionJob = null
        val sequenceTotal = _uiState.value.plan?.scenes?.firstOrNull { it.id == sceneId }?.steps?.size ?: 0
        _uiState.update {
            it.copy(
                sequence = NativeSequenceUiState(sceneId = sceneId, total = sequenceTotal),
                videoUrl = null,
                whiteboardOpen = false,
                activeAction = null,
                speech = null,
                spotlightElementId = null,
                laserElementId = null,
            )
        }
    }

    fun clearActionOverlay() {
        actionJob?.cancel()
        _uiState.update { it.copy(spotlightElementId = null, laserElementId = null, activeAction = null, speech = null) }
    }

    fun openWhiteboard() {
        cancelSequenceForManualMedia()
        val board = _uiState.value.document?.whiteboard
        if (board == null) {
            _uiState.update { it.copy(notice = "这份课件没有下发白板内容。") }
        } else {
            _uiState.update { it.copy(whiteboardOpen = true) }
        }
    }

    fun dismissWhiteboard(sceneId: String? = null) {
        if (sceneId != null && sceneId != _uiState.value.currentSceneId) return
        sequenceWhiteboardWaiter?.complete(Unit)
        sequenceWhiteboardWaiter = null
        _uiState.update { it.copy(whiteboardOpen = false) }
    }

    fun dismissVideo(url: String? = null) {
        val currentUrl = _uiState.value.videoUrl
        if (url != null && url != currentUrl) return
        sequenceVideoWaiter?.complete(null)
        sequenceVideoWaiter = null
        _uiState.update { it.copy(videoUrl = null) }
    }

    fun onVideoEnded(url: String) {
        dismissVideo(url)
    }

    fun onVideoFailed(url: String, message: String) {
        if (url != _uiState.value.videoUrl) return
        sequenceVideoWaiter?.complete(message.ifBlank { "视频加载失败" })
        sequenceVideoWaiter = null
        _uiState.update {
            it.copy(
                notice = "视频播放失败：${message.ifBlank { "视频加载失败" }}。可重试或从网页入口继续。",
            )
        }
    }

    // ── 讲解与朗读 ───────────────────────────────────────────────────────────

    fun toggleNarrationPanel() {
        val sceneId = _uiState.value.currentSceneId ?: return
        if (_uiState.value.narration.sceneId != sceneId) loadNarration(sceneId)
    }

    private suspend fun narrationStatus(sceneId: String, timeoutMs: Long): NativeNarrationUiState? =
        withTimeoutOrNull(timeoutMs) {
            uiState.map { it.narration }.first { it.sceneId == sceneId && (!it.loading || it.audioFile != null) }
        }

    private suspend fun awaitLectureNarration(sceneId: String): File? {
        val current = narrationStatus(sceneId, timeoutMs = 8_000L) ?: return null
        current.audioFile?.let { return it }
        if (!current.available || !current.hasScript) return null

        if (!current.awaitingAudio()) generateNarration()
        return withTimeoutOrNull(70_000L) {
            uiState.map { it.narration }.first { it.sceneId == sceneId && (it.audioFile != null || !it.awaitingAudio()) }
        }?.audioFile
    }

    private fun NativeNarrationUiState.awaitingAudio(): Boolean = loading || generating ||
        jobStatus == "queued" || jobStatus == "running" ||
        (jobStatus == "completed" && artifactId != null && audioFile == null && error == null)

    private fun loadNarration(sceneId: String) {
        if (ref.source != NativeClassroomSource.MANAGED) {
            _uiState.update { it.copy(narration = NativeNarrationUiState(sceneId = sceneId)) }
            return
        }
        narrationJob?.cancel()
        val generation = ++narrationGeneration
        _uiState.update {
            it.copy(narration = NativeNarrationUiState(sceneId = sceneId, loading = true))
        }
        narrationJob = viewModelScope.launch {
            val result = repository.magicClassNarration(ref.courseId, ref.workspaceId, ref.stageId, sceneId)
            if (generation != narrationGeneration || _uiState.value.currentSceneId != sceneId) return@launch
            result.onSuccess { dto ->
                val job = dto.job
                val state = NativeNarrationUiState(
                    sceneId = sceneId,
                    loading = false,
                    available = dto.available,
                    hasScript = dto.hasScript,
                    jobId = job?.id,
                    jobStatus = job?.status,
                    jobProgress = job?.progress ?: 0,
                    artifactId = job?.artifactId,
                    error = dto.message,
                )
                _uiState.update { it.copy(narration = state) }
                when {
                    job?.artifactId != null && (job.status == "completed" || dto.available) ->
                        downloadNarration(sceneId, job.artifactId)
                    job?.status in setOf("queued", "running") -> pollNarrationJob(sceneId, job?.id ?: return@launch)
                }
            }.onFailure {
                if (generation == narrationGeneration) {
                    _uiState.update { state ->
                        state.copy(narration = state.narration.copy(loading = false, error = it.message ?: "讲解状态读取失败"))
                    }
                }
            }
        }
    }

    fun generateNarration() {
        if (ref.source != NativeClassroomSource.MANAGED) {
            _uiState.update { it.copy(notice = "经典课堂没有讲解音频接口，可以先用系统朗读。") }
            return
        }
        val sceneId = _uiState.value.currentSceneId ?: return
        if (_uiState.value.narration.generating) return
        narrationGeneration++
        _uiState.update { it.copy(narration = it.narration.copy(generating = true, error = null)) }
        narrationJob = viewModelScope.launch {
            val result = repository.synthesizeMagicClassNarration(ref.courseId, ref.workspaceId, ref.stageId, sceneId)
            if (_uiState.value.currentSceneId != sceneId) return@launch
            result.onSuccess { dto ->
                val job = dto.job
                _uiState.update {
                    it.copy(
                        narration = it.narration.copy(
                            generating = false,
                            available = it.narration.available || dto.available,
                            hasScript = dto.hasScript,
                            jobId = job?.id,
                            jobStatus = job?.status,
                            jobProgress = job?.progress ?: 0,
                            artifactId = job?.artifactId,
                        ),
                    )
                }
                if (job != null) pollNarrationJob(sceneId, job.id)
            }.onFailure {
                _uiState.update { state ->
                    state.copy(narration = state.narration.copy(generating = false, error = it.message ?: "讲解生成失败"))
                }
            }
        }
    }

    private fun pollNarrationJob(sceneId: String, jobId: String) {
        narrationJob?.cancel()
        narrationJob = viewModelScope.launch {
            var elapsed = 0L
            while (isActive && elapsed < 90_000L) {
                delay(2_000)
                elapsed += 2_000
                if (_uiState.value.currentSceneId != sceneId) return@launch
                val job = repository.magicClassGenerationJob(ref.courseId, jobId).getOrNull() ?: continue
                _uiState.update {
                    it.copy(
                        narration = it.narration.copy(
                            jobStatus = job.status,
                            jobProgress = job.progress,
                            artifactId = job.artifactId,
                            generating = job.status in setOf("queued", "running"),
                        ),
                    )
                }
                when {
                    job.status == "completed" && job.artifactId != null -> {
                        downloadNarration(sceneId, job.artifactId)
                        return@launch
                    }
                    job.status == "failed" || job.status == "cancelled" -> {
                        _uiState.update { state ->
                            state.copy(narration = state.narration.copy(generating = false, error = "讲解生成未完成"))
                        }
                        return@launch
                    }
                }
            }
            if (_uiState.value.currentSceneId == sceneId && _uiState.value.narration.generating) {
                _uiState.update { state ->
                    state.copy(narration = state.narration.copy(generating = false, error = "讲解生成超时，可稍后重试"))
                }
            }
        }
    }

    private fun downloadNarration(sceneId: String, artifactId: String) {
        val sessionCache = playback?.cache ?: return
        narrationJob?.cancel()
        val revision = _uiState.value.revision
        val mediaGeneration = beginMediaRequest() ?: return
        _uiState.update { it.copy(narration = it.narration.copy(loading = true)) }
        narrationJob = viewModelScope.launch {
            val cached = withContext(Dispatchers.IO) { sessionCache.readAudio(artifactId, revision) }
            if (!isMediaRequestCurrent(mediaGeneration)) return@launch
            if (cached != null) {
                if (_uiState.value.currentSceneId == sceneId) {
                    _uiState.update {
                        it.copy(narration = it.narration.copy(loading = false, audioFile = cached, artifactId = artifactId))
                    }
                }
                return@launch
            }
            val bytes = withContext(Dispatchers.IO) {
                repository.downloadMagicClassArtifact(ref.courseId, artifactId)
            }
            if (!isMediaRequestCurrent(mediaGeneration)) return@launch
            if (_uiState.value.currentSceneId != sceneId) return@launch
            bytes.onSuccess { data ->
                val file = withContext(Dispatchers.IO) { sessionCache.writeAudio(artifactId, revision, data) }
                if (!isMediaRequestCurrent(mediaGeneration)) return@onSuccess
                _uiState.update {
                    it.copy(
                        narration = it.narration.copy(
                            loading = false,
                            audioFile = file,
                            artifactId = artifactId,
                            error = if (file == null) "讲解音频缓存失败" else null,
                        ),
                    )
                }
            }.onFailure {
                if (!isMediaRequestCurrent(mediaGeneration)) return@onFailure
                _uiState.update { state ->
                    state.copy(narration = state.narration.copy(loading = false, error = it.message ?: "讲解音频下载失败"))
                }
            }
        }
    }

    fun playElementAudio(source: String) {
        cancelSequenceForManualMedia()
        val resolved = ClassroomMediaPolicy.resolve(source, BuildConfig.API_BASE_URL, mediaBasePath)?.url
        if (resolved == null) {
            _uiState.update { it.copy(notice = "这一页的音频资源没有可访问地址。") }
            return
        }
        val target = activePlayer
        if (target == null) {
            _uiState.update { it.copy(notice = "课堂已结束，请重新进入。") }
            return
        }
        stopAudio()
        runCatching {
            target.setMediaItem(MediaItem.fromUri(resolved))
            target.prepare()
            target.playWhenReady = true
            updateNarration { it.copy(playing = true, error = null) }
        }.onFailure {
            _uiState.update { state -> state.copy(notice = "本页音频无法播放。") }
        }
    }

    private fun playSpeechAudio(source: String) {
        val resolved = ClassroomMediaPolicy.resolve(source, BuildConfig.API_BASE_URL, mediaBasePath)?.url
        if (resolved == null) {
            _uiState.update { it.copy(notice = "讲解音频地址不可用，可以先用系统朗读。") }
            return
        }
        val target = activePlayer
        if (target == null) {
            _uiState.update { it.copy(notice = "课堂已结束，请重新进入。") }
            return
        }
        stopAudio()
        runCatching {
            target.setMediaItem(MediaItem.fromUri(resolved))
            target.prepare()
            target.playWhenReady = true
            updateNarration { it.copy(playing = true, error = null) }
        }.onFailure {
            _uiState.update { it.copy(notice = "讲解音频无法播放，可以先用系统朗读。") }
        }
    }

    fun playVideo(source: String) {
        cancelSequenceForManualMedia()
        val resolved = ClassroomMediaPolicy.resolve(source, BuildConfig.API_BASE_URL, mediaBasePath)?.url
        _uiState.update {
            it.copy(
                videoUrl = resolved,
                notice = if (resolved == null) "视频资源未下发，暂时无法播放。" else null,
            )
        }
    }

    fun playNarration() {
        val narration = _uiState.value.narration
        val file = narration.audioFile
        if (file != null) {
            playAudio(file)
            return
        }
        if (narration.artifactId != null) {
            downloadNarration(narration.sceneId, narration.artifactId)
            return
        }
        if (narration.hasScript) {
            generateNarration()
        } else {
            _uiState.update { it.copy(notice = "本页还没有讲解内容，可以先用系统朗读。") }
        }
    }

    private fun playAudio(file: File) {
        cancelSequenceForManualMedia()
        stopAudio()
        val target = activePlayer
        if (target == null) {
            updateNarration { state -> state.copy(playing = false, error = "课堂已结束，请重新进入") }
            return
        }
        runCatching {
            target.setMediaItem(MediaItem.fromUri(Uri.fromFile(file)))
            target.prepare()
            target.playWhenReady = true
            updateNarration { it.copy(playing = true, error = null) }
        }.onFailure {
            updateNarration { state -> state.copy(playing = false, error = "讲解音频无法播放") }
        }
    }

    fun speakPage() {
        val text = pageSpeechText()
        if (text.isBlank()) {
            _uiState.update { it.copy(notice = "本页没有可朗读的文字。") }
            return
        }
        val speaker = activeTts
        if (speaker == null) {
            _uiState.update { it.copy(notice = "课堂已结束，请重新进入。") }
            return
        }
        cancelSequenceForManualMedia()
        stopAudio()
        updateNarration { it.copy(speaking = true, error = null) }
        speaker.speak(
            text,
            onDone = { updateNarration { it.copy(speaking = false) } },
            onError = { message ->
                updateNarration { it.copy(speaking = false, error = message) }
            },
        )
    }

    fun stopAudio() {
        playback?.let { session ->
            runCatching {
                session.player.stop()
                session.player.clearMediaItems()
            }
            session.tts.stop()
        }
        _uiState.update { state ->
            state.copy(narration = state.narration.copy(playing = false, speaking = false))
        }
    }

    private fun pageSpeechText(): String {
        val scene = _uiState.value.currentScene ?: return ""
        val slide = _uiState.value.currentSlide
        val parts = mutableListOf(scene.title)
        if (slide != null) {
            slide.elements.filterIsInstance<NativeCanvasElement.Text>()
                .sortedBy { it.top }
                .forEach { if (it.plainText.isNotBlank()) parts += it.plainText }
        }
        _uiState.value.currentQuiz?.let { quiz ->
            quiz.questions.forEach { q ->
                parts += "第 ${q.number} 题，${q.question}"
                q.options.forEach { option -> parts += "${option.label} ${option.value}" }
            }
        }
        _uiState.value.currentPbl?.let { pbl ->
            parts += pbl.title
            pbl.milestones.forEach { milestone ->
                parts += milestone.title
                milestone.tasks.forEach { parts += it.title }
            }
        }
        return parts.joinToString("。").take(4000)
    }

    private fun updateNarration(transform: (NativeNarrationUiState) -> NativeNarrationUiState) {
        _uiState.update { it.copy(narration = transform(it.narration)) }
    }

    // ── 测验 ─────────────────────────────────────────────────────────────────

    private fun loadQuiz(sceneId: String) {
        val quiz = _uiState.value.currentQuiz ?: return
        quizCoordinator?.close()
        val coordinator = ClassroomQuizCoordinator(
            sceneId = sceneId,
            quiz = quiz,
            writeMutex = quizWriteMutex,
            isAccountCurrent = { repository.classroomAccountScope() == initialAccountScope },
            loadAttempt = { id -> repository.classroomQuizAttempt(ref, id) },
            saveAttempt = { id, request -> repository.saveClassroomQuizAttempt(ref, id, request) },
            scope = viewModelScope,
            onState = { state ->
                if (_uiState.value.currentSceneId == sceneId) {
                    _uiState.update { current -> current.copy(quiz = state) }
                }
            },
            onSettled = { correct, total -> settleQuiz(sceneId, correct, total) },
        )
        quizCoordinator = coordinator
        coordinator.load()
    }

    fun setAnswer(questionId: String, answer: NativeAnswer) {
        quizCoordinator?.setAnswer(questionId, answer)
    }

    fun submitQuiz() {
        quizCoordinator?.submit()
    }

    fun setShortAnswerSelfCheck(questionId: String, correct: Boolean) {
        quizCoordinator?.setShortAnswerSelfCheck(questionId, correct)
    }

    fun finishQuizReview() {
        quizCoordinator?.finishReview()
    }

    fun retryQuiz() {
        quizCoordinator?.retry()
    }

    // ── AI 同学 ──────────────────────────────────────────────────────────────

    fun loadClassmates() {
        if (_uiState.value.classmates.roster.isNotEmpty() || _uiState.value.classmates.loading) return
        classmateJob?.cancel()
        _uiState.update { it.copy(classmates = it.classmates.copy(loading = true, error = null)) }
        classmateJob = viewModelScope.launch {
            repository.classmatesRoster()
                .onSuccess { roster ->
                    _uiState.update {
                        it.copy(
                            classmates = it.classmates.copy(
                                roster = roster.map { item -> NativeClassmate(item.id, item.name, item.role, item.persona) },
                                loading = false,
                                selectedAgentId = it.classmates.selectedAgentId ?: roster.firstOrNull()?.id,
                            ),
                        )
                    }
                }
                .onFailure {
                    _uiState.update { state ->
                        state.copy(classmates = state.classmates.copy(loading = false, error = it.message ?: "同学名单读取失败"))
                    }
                }
        }
    }

    fun selectClassmate(agentId: String) {
        _uiState.update { it.copy(classmates = it.classmates.copy(selectedAgentId = agentId)) }
    }

    fun classmatesSpeak() {
        requestClassmates(question = null)
    }

    fun askClassmate(question: String) {
        if (question.isBlank()) {
            _uiState.update { it.copy(classmates = it.classmates.copy(error = "先写下要问同学的问题")) }
            return
        }
        val agentId = _uiState.value.classmates.selectedAgentId
        if (agentId == null) {
            _uiState.update { it.copy(classmates = it.classmates.copy(error = "先选择一位同学")) }
            return
        }
        requestClassmates(question = question, agentId = agentId)
    }

    private fun requestClassmates(question: String?, agentId: String? = null) {
        if (_uiState.value.classmates.busy) return
        val scene = _uiState.value.currentScene ?: return
        val memory = classmateMemory()
        val scenePayload = compactScene(scene.id, scene.title, scene.type)
        if (scenePayload == null) {
            _uiState.update { it.copy(classmates = it.classmates.copy(error = "当前页没有可交给同学的内容")) }
            return
        }
        classmateJob?.cancel()
        _uiState.update { it.copy(classmates = it.classmates.copy(busy = true, error = null)) }
        classmateJob = viewModelScope.launch {
            if (question == null) {
                val response = repository.classmatesRespond(
                    MagicClassClassmateRespondRequest(
                        courseId = ref.courseId,
                        scene = scenePayload,
                        memory = memory,
                        language = "zh-CN",
                    ),
                )
                if (_uiState.value.currentSceneId != scene.id) return@launch
                response.onSuccess { dto ->
                    val messages = dto.messages.map { NativeClassmateMessage(it.agentId, it.text) }
                    _uiState.update {
                        it.copy(classmates = it.classmates.copy(busy = false, messages = appendMessages(it.classmates.messages, messages)))
                    }
                }.onFailure {
                    _uiState.update { state ->
                        state.copy(classmates = state.classmates.copy(busy = false, error = it.message ?: "同学发言失败"))
                    }
                }
            } else {
                val response = repository.classmatesAsk(
                    MagicClassClassmateAskRequest(
                        courseId = ref.courseId,
                        scene = scenePayload,
                        memory = memory,
                        language = "zh-CN",
                        agentId = agentId.orEmpty(),
                        question = question.take(600),
                    ),
                )
                if (_uiState.value.currentSceneId != scene.id) return@launch
                response.onSuccess { dto ->
                    val message = dto.message?.let { NativeClassmateMessage(it.agentId, it.text) }
                    _uiState.update {
                        it.copy(
                            classmates = it.classmates.copy(
                                busy = false,
                                messages = if (message == null) it.classmates.messages else appendMessages(it.classmates.messages, listOf(message)),
                            ),
                        )
                    }
                }.onFailure {
                    _uiState.update { state ->
                        state.copy(classmates = state.classmates.copy(busy = false, error = it.message ?: "点名同学失败"))
                    }
                }
            }
        }
    }

    private fun appendMessages(
        current: List<NativeClassmateMessage>,
        added: List<NativeClassmateMessage>,
    ): List<NativeClassmateMessage> = (current + added).takeLast(12)

    private fun classmateMemory(): MagicClassClassmateMemoryDto {
        val pages = _uiState.value.rewards.visited
            .mapNotNull { sceneId -> _uiState.value.plan?.scenes?.firstOrNull { it.id == sceneId }?.title }
            .takeLast(8)
        val known = _uiState.value.classmates.roster.map { it.id }.toSet()
        val lines = _uiState.value.classmates.messages
            .filter { it.agentId in known }
            .takeLast(12)
            .map { com.example.campusai.data.remote.MagicClassClassmateLineDto(it.agentId, it.text.take(400)) }
        return MagicClassClassmateMemoryDto(
            pages = pages,
            lines = lines,
            recentAgentIds = lines.map { it.agentId }.distinct().takeLast(7),
        )
    }

    /** 只发当前页可读文本，不发整份画布坐标；既满足 40KB 上限，也不泄露无必要结构。 */
    private fun compactScene(sceneId: String, title: String, type: String): MagicClassClassmateSceneDto? {
        val content: Map<String, Any?> = when (type) {
            "slide" -> {
                val slide = _uiState.value.document?.slideByScene?.get(sceneId) ?: return null
                val text = slide.elements.filterIsInstance<NativeCanvasElement.Text>()
                    .sortedBy { it.top }
                    .map { it.plainText }
                    .filter { it.isNotBlank() }
                    .joinToString("\n")
                    .take(12_000)
                mapOf(
                    "type" to "slide",
                    "title" to title,
                    "text" to text,
                    "elementCount" to slide.elements.size,
                )
            }
            "quiz" -> {
                val quiz = _uiState.value.document?.quizByScene?.get(sceneId) ?: return null
                mapOf(
                    "type" to "quiz",
                    "title" to title,
                    "questions" to quiz.questions.map { q ->
                        mapOf(
                            "id" to q.id,
                            "type" to q.type,
                            "question" to q.question.take(800),
                            "options" to q.options.map { it.label to it.value }.take(8),
                        )
                    }.take(12),
                )
            }
            "pbl" -> {
                val pbl = _uiState.value.document?.pblByScene?.get(sceneId) ?: return null
                mapOf(
                    "type" to "pbl",
                    "title" to pbl.title,
                    "description" to pbl.description.take(1000),
                    "milestones" to pbl.milestones.take(6).map { milestone ->
                        mapOf(
                            "title" to milestone.title,
                            "status" to milestone.status,
                            "tasks" to milestone.tasks.take(6).map { it.title },
                        )
                    },
                )
            }
            "interactive" -> {
                val interactive = _uiState.value.document?.interactiveByScene?.get(sceneId) ?: return null
                mapOf(
                    "type" to "interactive",
                    "title" to (interactive.title ?: title),
                    "widgetType" to interactive.widgetType,
                    "description" to interactive.description?.take(1000),
                )
            }
            else -> return null
        }
        return MagicClassClassmateSceneDto(
            id = sceneId,
            title = title.ifBlank { "课堂页" },
            type = type,
            content = content,
            actions = emptyList(),
        )
    }

    // ── 预取与指标 ───────────────────────────────────────────────────────────

    private fun prefetchAdjacent(sceneId: String) {
        val plan = _uiState.value.plan ?: return
        val imageLoader = playback?.cache?.imageLoader ?: return
        val index = plan.scenes.indexOfFirst { it.id == sceneId }
        if (index < 0) return
        val neighbours = listOfNotNull(plan.scenes.getOrNull(index + 1), plan.scenes.getOrNull(index - 1))
        val mediaGeneration = beginMediaRequest() ?: return
        prefetchDisposables.forEach { runCatching { it.dispose() } }
        prefetchDisposables.clear()
        prefetchJob = viewModelScope.launch {
            delay(220)
            if (!isMediaRequestCurrent(mediaGeneration)) return@launch
            for (neighbour in neighbours) {
                if (!isMediaRequestCurrent(mediaGeneration)) return@launch
                val slide = _uiState.value.document?.slideByScene?.get(neighbour.id) ?: continue
                for (image in slide.elements.filterIsInstance<NativeCanvasElement.Image>()) {
                    val url = ClassroomMediaPolicy.resolve(
                        image.source,
                        BuildConfig.API_BASE_URL,
                        mediaBasePath,
                    )?.url ?: continue
                    val cacheKey = "${ref.stableKey}:${_uiState.value.revision}:image-${image.id}:$url"
                    runCatching {
                        imageLoader.enqueue(
                            ImageRequest.Builder(context)
                                .data(url)
                                .size(1280, 720)
                                .memoryCacheKey(cacheKey)
                                .diskCacheKey(cacheKey)
                                .build(),
                        )
                    }.onSuccess { prefetchDisposables += it }
                }
            }
        }
    }

    private fun memoryNow(): Long = runCatching { Debug.getNativeHeapAllocatedSize() }.getOrDefault(0L)

    companion object {
        fun factory(
            application: Application,
            repository: AppRepository,
            ref: NativeClassroomRef,
        ): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return NativeClassroomViewModel(application, repository, ref) as T
            }
        }
    }
}

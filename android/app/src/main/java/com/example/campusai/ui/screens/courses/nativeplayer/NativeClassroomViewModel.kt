package com.example.campusai.ui.screens.courses.nativeplayer

import android.app.Application
import android.net.Uri
import android.os.Debug
import android.os.SystemClock
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.datasource.DataSource
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import com.example.campusai.BuildConfig
import com.example.campusai.data.classroom.nativeplayer.ClassroomActionSequencePlanner
import com.example.campusai.data.classroom.nativeplayer.ClassroomLevel
import com.example.campusai.data.classroom.nativeplayer.ClassroomMediaDataSourceFactory
import com.example.campusai.data.classroom.nativeplayer.ClassroomSequenceResult
import com.example.campusai.data.classroom.nativeplayer.ClassroomSequenceStep
import com.example.campusai.data.classroom.nativeplayer.ClassroomSequenceStepResult
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomSource
import com.example.campusai.data.classroom.nativeplayer.runClassroomSequence
import com.example.campusai.data.classroom.nativeplayer.ClassroomMediaPolicy
import com.example.campusai.data.classroom.nativeplayer.ClassroomMediaSession
import com.example.campusai.data.classroom.nativeplayer.ClassroomRewardResult
import com.example.campusai.data.classroom.nativeplayer.ClassroomRewards
import com.example.campusai.data.classroom.nativeplayer.ClassroomRewardsCodec
import com.example.campusai.data.classroom.nativeplayer.ClassroomRewardsEngine
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
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import java.io.File
import java.time.Instant
import java.util.Locale

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

data class NativeQuizUiState(
    val sceneId: String = "",
    val attemptId: String? = null,
    val phase: String = "draft",
    val answers: Map<String, NativeAnswer> = emptyMap(),
    val results: Map<String, NativeQuizResult> = emptyMap(),
    val selfChecks: Map<String, Boolean> = emptyMap(),
    val loading: Boolean = false,
    val saving: Boolean = false,
    val error: String? = null,
) {
    val showReport: Boolean
        get() = phase == "submitted" || phase == "reviewed" || results.isNotEmpty()
    val reviewed: Boolean get() = phase == "reviewed"
}

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
) {
    val currentScenePlan: NativeScenePlan? get() = plan?.scenes?.getOrNull(index)
    val currentSceneId: String? get() = currentScenePlan?.id
    val currentScene get() = document?.scene(currentSceneId)
    val currentSlide: NativeSlide? get() = currentSceneId?.let { document?.slideByScene?.get(it) }
    val currentQuiz: NativeQuiz? get() = currentSceneId?.let { document?.quizByScene?.get(it) }
    val currentPbl: NativePblProject? get() = currentSceneId?.let { document?.pblByScene?.get(it) }
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
    private val cache: NativeClassroomCache,
    private val now: () -> Long = { SystemClock.elapsedRealtime() },
) : AndroidViewModel(application) {

    private val _uiState = MutableStateFlow(NativeClassroomUiState())
    val uiState: StateFlow<NativeClassroomUiState> = _uiState.asStateFlow()

    private val context = application.applicationContext
    private val tts = AndroidTextToSpeechSynthesizer(context)
    private val mediaBasePath = ClassroomMediaPolicy.mediaBasePath(BuildConfig.API_BASE_URL, ref)
    private val mediaDataSourceFactory: DataSource.Factory = DefaultDataSource.Factory(
        context,
        ClassroomMediaDataSourceFactory(
            client = ApiClient.classroomMediaHttpClient(ref, followRedirects = false),
            ref = ref,
            apiBaseUrl = BuildConfig.API_BASE_URL,
        ),
    )
    private val player: ExoPlayer =
        ExoPlayer.Builder(context, DefaultMediaSourceFactory(mediaDataSourceFactory)).build().apply {
            addListener(object : Player.Listener {
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

    private var loadJob: Job? = null
    private var quizJob: Job? = null
    private var quizDraftJob: Job? = null
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
    private var positionJob: Job? = null
    private var rewardsJob: Job? = null
    private var metricsJob: Job? = null

    private var loadGeneration = 0
    private var quizGeneration = 0
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
    private val mediaSession = ClassroomMediaSession(initialAccountScope, ref)

    init {
        loadStartedAt = now()
        load()
        observeAccountSwitch()
    }

    fun load(forceNetwork: Boolean = false) {
        loadJob?.cancel()
        val generation = ++loadGeneration
        _uiState.update { it.copy(loading = it.plan == null, refreshing = it.plan != null, error = null) }
        loadStartedAt = now()
        firstPaintRecorded = false

        loadJob = viewModelScope.launch {
            val savedRewards = withContext(Dispatchers.IO) {
                ClassroomRewardsCodec.decode(repository.classroomRewardsRaw(ref))
            }
            withContext(Dispatchers.Main) {
                _uiState.update {
                    it.copy(
                        rewards = savedRewards,
                        level = ClassroomRewardsEngine.levelOf(savedRewards.xp),
                        unlocked = savedRewards.achievements.toList(),
                    )
                }
            }
            val savedScene = withContext(Dispatchers.IO) { repository.classroomPosition(ref) }
            if (generation != loadGeneration) return@launch
            if (ref.source != NativeClassroomSource.MANAGED) {
                loadClassic(savedScene, generation, forceNetwork)
                return@launch
            }
            if (!forceNetwork) {
                val cached = withContext(Dispatchers.IO) {
                    val document = cache.readStage()
                    val playback = cache.readPlayback()
                    val cachedRevision = cache.readRevision()
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
                    cache.writeStage(stage.revision, stage.document.orEmpty())
                    cache.writePlayback(playback)
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
    ) {
        if (!forceNetwork) {
            val cached = withContext(Dispatchers.IO) { cache.readClassicPlayback() }
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
            withContext(Dispatchers.IO) { cache.writeClassicPlayback(playback) }
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
        _uiState.update {
            it.copy(
                loading = false,
                refreshing = false,
                offline = fromCache,
                error = null,
                notice = if (fromCache) "正在使用本地缓存，后台继续刷新" else null,
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
            viewModelScope.launch(Dispatchers.IO) { repository.recordClassroomEntry(ref.identityUrl) }
        }
    }

    fun retry() = load(forceNetwork = true)

    fun clearNotice() {
        _uiState.update { it.copy(notice = null) }
    }

    fun goTo(index: Int) {
        val plan = _uiState.value.plan ?: return
        if (plan.scenes.isEmpty()) return
        val target = index.coerceIn(0, plan.scenes.lastIndex)
        if (target == _uiState.value.index) return
        resetSequenceRuntime(plan.scenes[target].id)
        val oldQuizState = _uiState.value.quiz
        val oldQuiz = _uiState.value.currentQuiz
        if (oldQuiz != null && oldQuizState != null && !oldQuizState.showReport) {
            // 草稿保存可能比翻页慢；不取消，但 saveDraft 会核对账号，避免迟到写回新账号。
            viewModelScope.launch { saveDraft(oldQuizState.sceneId, oldQuiz, oldQuizState) }
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
        mediaSession.invalidate()
        stopAudio()
    }

    fun onAccountChanged() {
        if (repository.classroomAccountScope() != initialAccountScope) {
            loadGeneration++
            quizGeneration++
            narrationGeneration++
            resetSequenceRuntime(_uiState.value.currentSceneId)
            mediaSession.invalidate()
            loadJob?.cancel()
            quizJob?.cancel()
            quizDraftJob?.cancel()
            narrationJob?.cancel()
            classmateJob?.cancel()
            actionJob?.cancel()
            prefetchJob?.cancel()
            positionJob?.cancel()
            rewardsJob?.cancel()
            stopAudio()
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
        // 退出页面只停止播放；ViewModel 可能被返回栈复用，播放器留给 onCleared 释放。
        resetSequenceRuntime(_uiState.value.currentSceneId)
        stopAudio()
        loadJob?.cancel()
        quizJob?.cancel()
        quizDraftJob?.cancel()
        narrationJob?.cancel()
        classmateJob?.cancel()
        prefetchJob?.cancel()
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

    private fun releaseMedia() {
        resetSequenceRuntime(_uiState.value.currentSceneId)
        mediaSession.invalidate()
        tts.shutdown()
        runCatching {
            player.stop()
            player.release()
        }
    }

    override fun onCleared() {
        recordStudyVisit(false)
        releaseMedia()
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
        )
        _uiState.update { it.copy(disposition = disposition) }
    }

    private fun onSceneChanged(sceneId: String) {
        resetSequenceRuntime(sceneId)
        stopAudio()
        narrationJob?.cancel()
        quizJob?.cancel()
        prefetchJob?.cancel()
        actionJob?.cancel()
        mediaSession.invalidate()
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
        positionJob = viewModelScope.launch(Dispatchers.IO) {
            if (positionAccountScope == repository.classroomAccountScope()) {
                repository.saveClassroomPosition(ref, sceneId)
            }
        }
        if (planScene?.type == "quiz") {
            loadQuiz(sceneId)
        }
        loadNarration(sceneId)
        prefetchAdjacent(sceneId)
    }

    private fun settleVisit(sceneId: String) {
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
        val accountScope = repository.classroomAccountScope()
        rewardsJob?.cancel()
        rewardsJob = viewModelScope.launch(Dispatchers.IO) {
            if (accountScope != repository.classroomAccountScope()) return@launch
            repository.saveClassroomRewardsRaw(ref, ClassroomRewardsCodec.encode(rewards))
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
                _uiState.update {
                    it.copy(
                        activeAction = action,
                        spotlightElementId = action.elementId,
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
        if (sequenceAudioWaiter != null) runCatching { player.pause() }
        if (sequenceUtterance?.complete(LectureUtterance.Paused) == true) tts.stop()
    }

    fun resumeSequence() {
        val sequence = _uiState.value.sequence
        if (!sequence.active || !sequence.paused) return
        _uiState.update { it.copy(sequence = it.sequence.copy(paused = false)) }
        if (sequenceAudioWaiter != null) runCatching { player.play() }
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
            if (_uiState.value.currentSlide != null && text.isNotBlank()) {
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
        try {
            player.setMediaItem(MediaItem.Builder().setUri(resolved).setMediaId(mediaId).build())
            player.prepare()
            player.playWhenReady = true
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
                    tts.speak(
                        NativeClassroomText.forSpeech(part),
                        onDone = { waiter.complete(LectureUtterance.Finished) },
                        onError = { waiter.complete(LectureUtterance.Failed(it)) },
                    )
                    withTimeoutOrNull(90_000L) { waiter.await() }
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
        narrationJob?.cancel()
        val revision = _uiState.value.revision
        val mediaGeneration = mediaSession.beginRequest()
        _uiState.update { it.copy(narration = it.narration.copy(loading = true)) }
        narrationJob = viewModelScope.launch {
            val cached = withContext(Dispatchers.IO) { cache.readAudio(artifactId, revision) }
            if (!mediaSession.isCurrent(mediaGeneration, repository.classroomAccountScope(), ref)) return@launch
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
            if (!mediaSession.isCurrent(mediaGeneration, repository.classroomAccountScope(), ref)) return@launch
            if (_uiState.value.currentSceneId != sceneId) return@launch
            bytes.onSuccess { data ->
                val file = withContext(Dispatchers.IO) { cache.writeAudio(artifactId, revision, data) }
                if (!mediaSession.isCurrent(mediaGeneration, repository.classroomAccountScope(), ref)) return@onSuccess
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
                if (!mediaSession.isCurrent(mediaGeneration, repository.classroomAccountScope(), ref)) return@onFailure
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
        stopAudio()
        runCatching {
            player.setMediaItem(MediaItem.fromUri(resolved))
            player.prepare()
            player.playWhenReady = true
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
        stopAudio()
        runCatching {
            player.setMediaItem(MediaItem.fromUri(resolved))
            player.prepare()
            player.playWhenReady = true
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
        runCatching {
            player.setMediaItem(MediaItem.fromUri(Uri.fromFile(file)))
            player.prepare()
            player.playWhenReady = true
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
        cancelSequenceForManualMedia()
        stopAudio()
        updateNarration { it.copy(speaking = true, error = null) }
        tts.speak(
            text,
            onDone = { updateNarration { it.copy(speaking = false) } },
            onError = { message ->
                updateNarration { it.copy(speaking = false, error = message) }
            },
        )
    }

    fun stopAudio() {
        runCatching {
            player.stop()
            player.clearMediaItems()
        }
        tts.stop()
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
        quizJob?.cancel()
        val generation = ++quizGeneration
        _uiState.update {
            it.copy(quiz = NativeQuizUiState(sceneId = sceneId, loading = true))
        }
        quizJob = viewModelScope.launch {
            val result = repository.classroomQuizAttempt(ref, sceneId)
            if (generation != quizGeneration || _uiState.value.currentSceneId != sceneId) return@launch
            result.onSuccess { dto ->
                val quiz = _uiState.value.currentQuiz ?: return@onSuccess
                val state = dto.state
                val phase = state?.phase ?: "draft"
                val answers = decodeAnswers(quiz, state?.answers.orEmpty())
                val results = decodeResults(state?.results.orEmpty())
                _uiState.update {
                    it.copy(
                        quiz = NativeQuizUiState(
                            sceneId = sceneId,
                            attemptId = dto.attemptId ?: state?.sessionId,
                            phase = phase,
                            answers = answers,
                            results = results,
                            loading = false,
                        ),
                    )
                }
                if (phase == "reviewed" && results.isNotEmpty()) {
                    settleQuiz(sceneId, results.values.count { it.correct == true }, results.size)
                }
            }.onFailure {
                _uiState.update { state ->
                    state.copy(quiz = state.quiz?.copy(loading = false, error = it.message ?: "测验读取失败"))
                }
            }
        }
    }

    fun setAnswer(questionId: String, answer: NativeAnswer) {
        val quizState = _uiState.value.quiz ?: return
        _uiState.update {
            it.copy(quiz = quizState.copy(answers = quizState.answers + (questionId to answer), error = null))
        }
        scheduleDraftSave(quizState.sceneId)
    }

    private fun scheduleDraftSave(sceneId: String) {
        val quiz = _uiState.value.currentQuiz ?: return
        val quizState = _uiState.value.quiz ?: return
        quizDraftJob?.cancel()
        quizDraftJob = viewModelScope.launch {
            delay(700)
            if (_uiState.value.currentSceneId == sceneId) saveDraft(sceneId, quiz, quizState)
        }
    }

    private suspend fun saveDraft(sceneId: String, quiz: NativeQuiz, quizState: NativeQuizUiState) {
        if (quizState.sceneId != sceneId || quizState.showReport) return
        val accountScope = repository.classroomAccountScope()
        val response = repository.saveClassroomQuizAttempt(
                ref,
                sceneId,
            MagicClassQuizAttemptRequest(
                attemptId = quizState.attemptId,
                phase = "draft",
                answers = encodeAnswers(quiz, quizState.answers),
            ),
        )
        if (accountScope != repository.classroomAccountScope()) return
        if (_uiState.value.currentSceneId != sceneId) return
        response.onSuccess { dto ->
            val returnState = dto.state
            if (returnState != null) {
                _uiState.update { state ->
                    val current = state.quiz ?: return@update state
                    if (current.sceneId != sceneId) return@update state
                    state.copy(
                        quiz = current.copy(
                            attemptId = dto.attemptId ?: current.attemptId,
                            answers = decodeAnswers(quiz, returnState.answers),
                            error = null,
                        ),
                    )
                }
            }
        }.onFailure {
            _uiState.update { state ->
                val current = state.quiz ?: return@update state
                if (current.sceneId != sceneId) return@update state
                state.copy(quiz = current.copy(error = it.message ?: "测验草稿保存失败"))
            }
        }
    }

    fun submitQuiz() {
        val ui = _uiState.value
        val quiz = ui.currentQuiz ?: return
        val quizState = ui.quiz ?: return
        val unanswered = quiz.questions.count { question -> !quizState.answers[question.id]?.hasValue.orFalse() }
        if (unanswered > 0) {
            _uiState.update {
                it.copy(quiz = quizState.copy(error = "还有 $unanswered 道题未作答"))
            }
            return
        }
        if (quizState.saving) return
        val results = gradeQuiz(quiz, quizState.answers)
        val hasShort = quiz.questions.any { it.isShortAnswer }
        _uiState.update {
            it.copy(quiz = quizState.copy(saving = true, error = null, results = results, phase = "submitted"))
        }
        quizDraftJob?.cancel()
        quizJob?.cancel()
        quizJob = viewModelScope.launch {
            val phase = if (hasShort) "submitted" else "reviewed"
            val response = repository.saveClassroomQuizAttempt(
                ref,
                quizState.sceneId,
                MagicClassQuizAttemptRequest(
                    attemptId = quizState.attemptId,
                    phase = phase,
                    answers = encodeAnswers(quiz, quizState.answers),
                    results = encodeResults(results.values),
                ),
            )
            if (_uiState.value.currentSceneId != quizState.sceneId) return@launch
            response.onSuccess { dto ->
                _uiState.update { state ->
                    val current = state.quiz ?: return@update state
                    state.copy(
                        quiz = current.copy(
                            saving = false,
                            phase = phase,
                            attemptId = dto.attemptId ?: current.attemptId,
                            results = results,
                        ),
                    )
                }
                if (!hasShort) {
                    settleQuiz(quizState.sceneId, results.values.count { it.correct == true }, results.size)
                }
            }.onFailure {
                _uiState.update { state ->
                    val current = state.quiz ?: return@update state
                    state.copy(
                        quiz = current.copy(
                            saving = false,
                            phase = "submitted",
                            error = it.message ?: "测验提交失败，答案仍保留在本机",
                        ),
                    )
                }
            }
        }
    }

    fun setShortAnswerSelfCheck(questionId: String, correct: Boolean) {
        val quizState = _uiState.value.quiz ?: return
        _uiState.update {
            it.copy(quiz = quizState.copy(selfChecks = quizState.selfChecks + (questionId to correct)))
        }
    }

    fun finishQuizReview() {
        val ui = _uiState.value
        val quiz = ui.currentQuiz ?: return
        val quizState = ui.quiz ?: return
        val shorts = quiz.questions.filter { it.isShortAnswer }
        if (shorts.any { quizState.selfChecks[it.id] == null }) {
            _uiState.update {
                it.copy(quiz = quizState.copy(error = "还有主观题没有完成核对"))
            }
            return
        }
        if (quizState.saving) return
        val updated = quizState.results.toMutableMap()
        shorts.forEach { question ->
            val correct = quizState.selfChecks[question.id] == true
            updated[question.id] = NativeQuizResult(
                questionId = question.id,
                correct = correct,
                earned = if (correct) question.points else 0.0,
                comment = "已按参考答案自行核对",
                selfChecked = true,
            )
        }
        _uiState.update {
            it.copy(
                quiz = quizState.copy(
                    results = updated,
                    phase = "reviewed",
                    saving = true,
                    error = null,
                ),
            )
        }
        quizJob?.cancel()
        quizJob = viewModelScope.launch {
            val response = repository.saveClassroomQuizAttempt(
                ref,
                quizState.sceneId,
                MagicClassQuizAttemptRequest(
                    attemptId = quizState.attemptId,
                    phase = "reviewed",
                    answers = encodeAnswers(quiz, quizState.answers),
                    results = encodeResults(updated.values),
                ),
            )
            if (_uiState.value.currentSceneId != quizState.sceneId) return@launch
            response.onSuccess {
                _uiState.update { state ->
                    val current = state.quiz ?: return@update state
                    state.copy(quiz = current.copy(saving = false, phase = "reviewed", results = updated))
                }
                settleQuiz(quizState.sceneId, updated.values.count { it.correct == true }, updated.size)
            }.onFailure {
                _uiState.update { state ->
                    val current = state.quiz ?: return@update state
                    state.copy(quiz = current.copy(saving = false, error = it.message ?: "测验报告保存失败"))
                }
            }
        }
    }

    fun retryQuiz() {
        val ui = _uiState.value
        val quiz = ui.currentQuiz ?: return
        val quizState = ui.quiz ?: return
        if (quizState.saving) return
        quizJob?.cancel()
        quizJob = viewModelScope.launch {
            val response = repository.saveClassroomQuizAttempt(
                ref,
                quizState.sceneId,
                MagicClassQuizAttemptRequest(
                    attemptId = quizState.attemptId,
                    phase = "draft",
                    answers = emptyMap(),
                    startNewAttempt = true,
                ),
            )
            if (_uiState.value.currentSceneId != quizState.sceneId) return@launch
            response.onSuccess { dto ->
                _uiState.update {
                    it.copy(
                        quiz = NativeQuizUiState(
                            sceneId = quizState.sceneId,
                            attemptId = dto.attemptId ?: quizState.attemptId,
                            phase = "draft",
                        ),
                    )
                }
            }.onFailure {
                _uiState.update { state ->
                    state.copy(quiz = state.quiz?.copy(error = it.message ?: "重新答题失败"))
                }
            }
        }
    }

    private fun gradeQuiz(quiz: NativeQuiz, answers: Map<String, NativeAnswer>): Map<String, NativeQuizResult> {
        return quiz.questions.associate { question ->
            val result = when {
                question.isShortAnswer -> NativeQuizResult(
                    questionId = question.id,
                    correct = null,
                    earned = 0.0,
                    comment = "主观题请对照参考答案自行核对",
                )
                !question.autoGradable -> NativeQuizResult(
                    questionId = question.id,
                    correct = null,
                    earned = 0.0,
                    comment = "本题没有下发标准答案，请对照解析",
                )
                else -> {
                    val selected = answers[question.id]?.selected.orEmpty()
                    val correct = if (question.isMultiple) {
                        selected == question.answerKey.toSet()
                    } else {
                        selected.size == 1 && selected.first() in question.answerKey
                    }
                    NativeQuizResult(
                        questionId = question.id,
                        correct = correct,
                        earned = if (correct) question.points else 0.0,
                        comment = if (correct) null else question.analysis.ifBlank { null },
                    )
                }
            }
            question.id to result
        }
    }

    private fun decodeAnswers(quiz: NativeQuiz, raw: Map<String, Any?>): Map<String, NativeAnswer> {
        return quiz.questions.associate { question ->
            val value = raw[question.id]
            val answer = when {
                question.isShortAnswer -> NativeAnswer(text = value.asText())
                value is List<*> -> NativeAnswer(selected = value.mapNotNull { it.asText().takeIf { text -> text.isNotBlank() } }.toSet())
                else -> NativeAnswer(selected = value.asText().takeIf { it.isNotBlank() }?.let { setOf(it) }.orEmpty())
            }
            question.id to answer
        }
    }

    private fun encodeAnswers(quiz: NativeQuiz, answers: Map<String, NativeAnswer>): Map<String, Any?> {
        return quiz.questions.mapNotNull { question ->
            val answer = answers[question.id] ?: return@mapNotNull null
            if (!answer.hasValue) return@mapNotNull null
            val value: Any = when {
                question.isShortAnswer -> answer.text
                question.isMultiple -> answer.selected.toList()
                else -> answer.selected.firstOrNull().orEmpty()
            }
            question.id to value
        }.toMap()
    }

    private fun decodeResults(raw: List<Map<String, Any?>>): Map<String, NativeQuizResult> {
        return raw.mapNotNull { item ->
            val id = item["questionId"].asText().ifBlank { item["question_id"].asText() }
            if (id.isBlank()) return@mapNotNull null
            val correct = when (item["correct"]) {
                is Boolean -> item["correct"] as Boolean
                is Number -> (item["correct"] as Number).toInt() != 0
                else -> when (item["status"].asText()) {
                    "correct" -> true
                    "incorrect" -> false
                    else -> null
                }
            }
            id to NativeQuizResult(
                questionId = id,
                correct = correct,
                earned = item["earned"].asDouble()?.takeIf { value -> value >= 0 } ?: 0.0,
                comment = item["aiComment"].asText().ifBlank { item["comment"].asText() }.ifBlank { null },
                selfChecked = item["selfChecked"] as? Boolean ?: false,
            )
        }.toMap()
    }

    private fun encodeResults(results: Collection<NativeQuizResult>): List<Map<String, Any?>> =
        results.map { result ->
            mapOf(
                "questionId" to result.questionId,
                "correct" to result.correct,
                "status" to when (result.correct) {
                    true -> "correct"
                    false -> "incorrect"
                    null -> "ungraded"
                },
                "earned" to result.earned,
                "aiComment" to result.comment,
                "selfChecked" to result.selfChecked,
            )
        }

    private fun Boolean?.orFalse(): Boolean = this == true

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
        val index = plan.scenes.indexOfFirst { it.id == sceneId }
        if (index < 0) return
        val neighbours = listOfNotNull(plan.scenes.getOrNull(index + 1), plan.scenes.getOrNull(index - 1))
        val mediaGeneration = mediaSession.beginRequest()
        prefetchJob = viewModelScope.launch {
            delay(220)
            if (!mediaSession.isCurrent(mediaGeneration, repository.classroomAccountScope(), ref)) return@launch
            for (neighbour in neighbours) {
                if (!mediaSession.isCurrent(mediaGeneration, repository.classroomAccountScope(), ref)) return@launch
                val slide = _uiState.value.document?.slideByScene?.get(neighbour.id) ?: continue
                for (image in slide.elements.filterIsInstance<NativeCanvasElement.Image>()) {
                    val url = ClassroomMediaPolicy.resolve(
                        image.source,
                        BuildConfig.API_BASE_URL,
                        mediaBasePath,
                    )?.url ?: continue
                    val cacheKey = "${ref.stableKey}:${_uiState.value.revision}:image-${image.id}:$url"
                    runCatching {
                        cache.imageLoader.enqueue(
                            ImageRequest.Builder(context)
                                .data(url)
                                .size(1280, 720)
                                .memoryCacheKey(cacheKey)
                                .diskCacheKey(cacheKey)
                                .build(),
                        )
                    }
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
            cache: NativeClassroomCache,
        ): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return NativeClassroomViewModel(application, repository, ref, cache) as T
            }
        }
    }
}

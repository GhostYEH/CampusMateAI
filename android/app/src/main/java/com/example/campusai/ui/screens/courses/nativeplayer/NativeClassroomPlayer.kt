package com.example.campusai.ui.screens.courses.nativeplayer

import android.app.Application
import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.FitScreen
import androidx.compose.material.icons.filled.Remove
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.ui.window.DialogWindowProvider
import androidx.core.view.WindowCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.PlaybackException
import androidx.media3.datasource.DataSource
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.ui.PlayerView
import com.example.campusai.BuildConfig
import com.example.campusai.data.classroom.nativeplayer.ClassroomMediaDataSourceFactory
import com.example.campusai.data.classroom.nativeplayer.ClassroomLimitExperiment
import com.example.campusai.data.classroom.nativeplayer.ClassroomMediaPolicy
import com.example.campusai.data.classroom.nativeplayer.NativeCanvasElement
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomCache
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomRef
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomText
import com.example.campusai.data.classroom.nativeplayer.NativePlaybackPolicy
import com.example.campusai.data.classroom.nativeplayer.NativeSceneMode
import com.example.campusai.data.remote.ApiClient
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.screens.courses.ClassroomWood
import com.example.campusai.ui.theme.Accent
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.CampusMotion
import com.example.campusai.ui.theme.DangerText
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.LocalReduceMotion
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlin.math.roundToInt

/**
 * 课程课堂、自主选题和受管工作台共用的原生播放器。
 */
@Composable
fun NativeClassroomPlayer(
    ref: NativeClassroomRef,
    repository: AppRepository,
    onClose: () -> Unit,
    onOpenFallback: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val application = context.applicationContext as Application
    val session by repository.session.collectAsStateWithLifecycle()
    val accountScope = remember(session) { repository.classroomAccountScope() }
    val cache = remember(ref.stableKey, accountScope) {
        NativeClassroomCache(context, accountScope, ref)
    }
    val vm: NativeClassroomViewModel = viewModel(
        key = "native-classroom-${ref.stableKey}-$accountScope",
        factory = NativeClassroomViewModel.factory(application, repository, ref, cache),
    )
    val state by vm.uiState.collectAsStateWithLifecycle()
    val mediaBase = remember(ref.stableKey) {
        ClassroomMediaPolicy.mediaBasePath(BuildConfig.API_BASE_URL, ref)
    }
    val videoDataSourceFactory = remember(ref.stableKey, accountScope) {
        DefaultDataSource.Factory(
            context,
            ClassroomMediaDataSourceFactory(
                client = ApiClient.classroomMediaHttpClient(ref, followRedirects = false),
                ref = ref,
                apiBaseUrl = BuildConfig.API_BASE_URL,
            ),
        )
    }
    val lifecycleOwner = LocalLifecycleOwner.current
    val view = LocalView.current
    var panel by rememberSaveable(ref.stableKey) { mutableStateOf<String?>(null) }
    var zoom by rememberSaveable(ref.stableKey) { mutableFloatStateOf(1f) }
    var readNotes by rememberSaveable(ref.stableKey, state.currentSceneId) { mutableStateOf(false) }
    var closing by remember(ref.stableKey) { mutableStateOf(false) }

    SideEffect {
        (view.parent as? DialogWindowProvider)?.window?.let { window ->
            WindowCompat.getInsetsController(window, view).apply {
                isAppearanceLightStatusBars = false
                isAppearanceLightNavigationBars = false
            }
        }
    }

    DisposableEffect(lifecycleOwner, vm) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> vm.onHostResume()
                Lifecycle.Event.ON_PAUSE, Lifecycle.Event.ON_STOP -> vm.onHostPause()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            vm.onHostPause()
        }
    }

    val total = state.plan?.scenes?.size ?: 0
    val completed = total > 0 && state.index >= total - 1
    val slide = state.currentSlide
    val slidePage = state.disposition.mode == NativeSceneMode.NATIVE &&
        state.currentScenePlan?.type == "slide" && slide != null
    val experimentPage = state.hasNativeExperiment
    val sceneTitle = state.currentScene?.title ?: state.currentScenePlan?.title.orEmpty()
    val lessonText = remember(slide, sceneTitle) {
        slide?.elements?.filterIsInstance<NativeCanvasElement.Text>()?.filter { element ->
            element.opacity > 0 && element.plainText.isNotBlank() && element.plainText != sceneTitle
        }.orEmpty()
    }
    val lectureVisible = state.spotlightElementId != null || state.laserElementId != null || state.sequence.active
    val showCanvas = lessonText.isEmpty() || !readNotes || lectureVisible
    val scene = state.currentScene
    val lectureScript = remember(slide, scene, sceneTitle) {
        if (slide == null) null else {
            scene?.actions.orEmpty().filter { it.type == "speech" && it.supported }
                .mapNotNull { it.speech?.takeIf(String::isNotBlank) ?: it.description.takeIf(String::isNotBlank) }
                .ifEmpty { NativeClassroomText.lectureParagraphs(slide).filterNot { it == sceneTitle } }
                .joinToString("\n\n").takeIf(String::isNotBlank)
        }
    }
    fun finishAndClose(complete: Boolean) {
        if (closing) return
        closing = true
        vm.finish(complete)
        onClose()
    }

    BackHandler {
        if (state.endSummary != null) vm.dismissEnd() else vm.requestEnd(completed)
    }

    LaunchedEffect(state.currentSceneId, state.revision, state.loading) {
        if (!state.loading && state.currentSceneId != null) {
            withFrameNanos { }
            vm.markFirstPainted()
            vm.markPagePainted()
        }
    }
    LaunchedEffect(state.sequence.active) {
        if (state.sequence.active) readNotes = false
    }

    val reduceMotion = LocalReduceMotion.current
    val pageTurn = remember(vm) { Animatable(0f) }
    val page = state.index.takeIf { state.currentSceneId != null }
    var previousPage by remember(vm) { mutableStateOf(page) }
    LaunchedEffect(page, reduceMotion) {
        val previous = previousPage
        previousPage = page
        if (reduceMotion || previous == null || page == null || page == previous) {
            pageTurn.snapTo(0f)
        } else {
            pageTurn.snapTo(if (page > previous) 1f else -1f)
            pageTurn.animateTo(0f, tween(350, easing = CampusMotion.settleEasing))
        }
    }
    val speaking = !state.sequence.paused && (state.narration.speaking || state.narration.playing ||
        (state.sequence.active && !state.sequence.preparing && state.activeAction?.type == "speech"))
    NativeClassroomTheme {
        BoxWithConstraints(modifier.fillMaxSize().background(Background)) {
            val landscape = maxWidth > maxHeight
            val splitLecture = landscape && maxWidth >= 580.dp
            NativeClassroomStage(pageTurn.asState(), speaking, landscape, Modifier.matchParentSize())
            val controlsInHeader = slidePage && splitLecture && maxWidth >= 720.dp
            Column(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Horizontal))) {
                NativeTopBar(
                    title = state.plan?.title ?: ref.title.ifBlank { "课堂" },
                    visited = state.plan?.scenes?.count { it.id in state.rewards.visited } ?: 0,
                    total = total,
                    offline = state.offline,
                    showMetrics = state.showMetrics,
                    compact = landscape,
                    onClose = { vm.requestEnd(completed) },
                    onToggleMetrics = vm::toggleMetrics,
                ) {
                    if (controlsInHeader) {
                        SlideToolbar(lessonText.isNotEmpty(), showCanvas, lectureVisible, zoom,
                            { readNotes = it }, { zoom = it })
                        Spacer(Modifier.width(8.dp))
                    }
                }

                val message = if (state.plan != null) state.error ?: state.notice else null
                if (message != null) {
                    val error = state.error != null
                    Row(
                        Modifier.fillMaxWidth().background(
                            if (error) Color(0xFF402B2B) else Surface,
                        ).padding(start = 14.dp, end = 6.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            message, color = if (error) DangerText else Accent,
                            fontSize = 12.sp, modifier = Modifier.weight(1f),
                        )
                        if (!ref.webFallbackUrl.isNullOrBlank()) {
                            TextButton(onClick = { onOpenFallback(ref.webFallbackUrl) }) {
                                Text("网页打开")
                            }
                        }
                        TextButton(onClick = if (error) vm::retry else vm::clearNotice) {
                            Text(if (error) "重试" else "知道了")
                        }
                    }
                }

                BoxWithConstraints(Modifier.weight(1f).fillMaxWidth()) {
                    key(state.currentSceneId, slidePage, state.disposition.mode, state.plan != null) {
                        val scenePlan = state.currentScenePlan
                        val renderScene: @Composable (Modifier, Boolean) -> Unit = { contentModifier, fitSlide ->
                            NativeSceneBody(
                                state = state,
                                ref = ref,
                                vm = vm,
                                cache = cache,
                                zoom = zoom,
                                mediaBase = mediaBase,
                                lessonText = lessonText,
                                showCanvas = showCanvas,
                                lectureVisible = lectureVisible,
                                onReadNotes = { readNotes = it },
                                onZoom = { zoom = it },
                                onOpenFallback = onOpenFallback,
                                fitSlide = fitSlide,
                                controlsInHeader = controlsInHeader,
                                modifier = if (!reduceMotion && (slidePage || experimentPage)) {
                                    contentModifier.classroomPageTurn(pageTurn.asState())
                                } else contentModifier,
                            )
                        }
                        val renderActions: @Composable (Boolean) -> Unit = { sidePanel ->
                            NativeClassroomActions(
                                teachingSlide = slidePage,
                                canTeach = slidePage && state.canTeachSlide,
                                sequence = state.sequence,
                                actions = state.currentScene?.actions.orEmpty(),
                                active = state.activeAction,
                                speech = state.speech,
                                speaking = speaking,
                                lectureScript = lectureScript,
                                onStart = if (slidePage) vm::startLecture else vm::startSequence,
                                onPause = vm::pauseSequence,
                                onResume = vm::resumeSequence,
                                onStop = vm::stopSequence,
                                onAction = vm::triggerAction,
                                onHideSpeech = vm::clearActionOverlay,
                                sidePanel = sidePanel,
                            )
                        }
                        val sceneScroll = key(landscape) { rememberScrollState() }
                        if ((slidePage || experimentPage) && splitLecture) {
                            val gap = 12.dp
                            val availableWidth = maxWidth - 24.dp - gap
                            val sideWidth = if (slidePage) {
                                val toolbarHeight = if (controlsInHeader) 0.dp else 52.dp
                                val fittedWidth = (maxHeight - 30.dp - toolbarHeight)
                                    .coerceAtLeast(0.dp) * slide.aspectRatio + 14.dp
                                (availableWidth - fittedWidth)
                                    .coerceIn(228.dp, (availableWidth * .46f).coerceIn(228.dp, 400.dp))
                            } else {
                                (availableWidth * .29f).coerceIn(200.dp, 300.dp)
                            }
                            Column(
                                Modifier.fillMaxSize().padding(horizontal = 12.dp, vertical = 8.dp),
                                verticalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                if (experimentPage) NativeSceneHeading(sceneTitle, "interactive", compact = true)
                                Row(
                                    Modifier.weight(1f).fillMaxWidth(),
                                    horizontalArrangement = Arrangement.spacedBy(gap),
                                ) {
                                    Box(Modifier.weight(1f).fillMaxHeight()) {
                                        renderScene(Modifier.fillMaxSize(), true)
                                    }
                                    Box(Modifier.width(sideWidth).fillMaxHeight()) {
                                        renderActions(true)
                                    }
                                }
                            }
                        } else {
                            Column(
                                Modifier.fillMaxSize()
                                    .then(if (slidePage) Modifier.verticalScroll(sceneScroll) else Modifier)
                                    .padding(horizontal = 14.dp, vertical = if (landscape) 8.dp else 12.dp),
                                verticalArrangement = Arrangement.spacedBy(11.dp),
                            ) {
                                val isNativeQuiz = scenePlan?.type == "quiz" && state.disposition.mode == NativeSceneMode.NATIVE
                                if (scenePlan != null && !slidePage && !isNativeQuiz) {
                                    NativeSceneHeading(sceneTitle, scenePlan.type, compact = landscape)
                                }
                                Box(Modifier.fillMaxWidth().then(if (slidePage) Modifier else Modifier.weight(1f))) {
                                    renderScene(if (slidePage) Modifier.fillMaxWidth() else Modifier.fillMaxSize(), false)
                                }
                                renderActions(false)
                            }
                        }
                    }
                }
                NativePagerBar(
                    page = state.page,
                    onPrev = vm::previous,
                    onNext = vm::next,
                    onGoTo = vm::goTo,
                    onDirectory = { panel = "directory" },
                    onNarration = {
                        vm.toggleNarrationPanel()
                        panel = "narration"
                    },
                    onClassmates = {
                        vm.loadClassmates()
                        panel = "classmates"
                    },
                    onWhiteboard = vm::openWhiteboard,
                    firstPaintMs = state.firstPaintMs,
                    pageFlipMs = state.pageFlipMs,
                    peakMemory = state.peakMemoryBytes,
                    xp = state.rewards.xp,
                    level = state.level.level,
                    showMetrics = state.showMetrics,
                    compact = splitLecture,
                )
            }
        }

        if (panel == "directory") {
            NativePanelDialog(title = "课堂地图", onDismiss = { panel = null }) {
                val plan = state.plan
                if (plan != null) {
                    NativeDirectoryPanel(
                        plan = plan,
                        document = state.document,
                        index = state.index,
                        visitedSceneIds = state.rewards.visited,
                        imageLoader = cache.imageLoader,
                        assetKeyPrefix = "${ref.stableKey}:${state.revision}",
                        mediaBase = mediaBase,
                        onSelect = {
                            vm.goTo(it)
                            panel = null
                        },
                    )
                }
            }
        }
        if (panel == "narration") {
            NativePanelDialog(title = "讲解与朗读", onDismiss = { panel = null }) {
                NativeNarrationPanel(
                    state = state.narration,
                    onGenerate = vm::generateNarration,
                    onPlay = vm::playNarration,
                    onSpeak = vm::speakPage,
                    onStop = { if (state.sequence.active) vm.stopSequence() else vm.stopAudio() },
                )
            }
        }
        if (panel == "classmates") {
            NativePanelDialog(title = "AI 同学", onDismiss = { panel = null }) {
                NativeClassmatesPanel(
                    state = state.classmates,
                    sceneTitle = state.currentScene?.title ?: "",
                    onLoad = vm::loadClassmates,
                    onSelect = vm::selectClassmate,
                    onSpeak = vm::classmatesSpeak,
                    onAsk = vm::askClassmate,
                )
            }
        }
        if (state.whiteboardOpen) {
            NativePanelDialog(title = "白板", onDismiss = { vm.dismissWhiteboard(state.currentSceneId) }) {
                val board = state.document?.whiteboard
                if (board == null) {
                    NativeUnavailablePanel(
                        reason = "这份课件没有下发白板内容。",
                        hasFallback = false,
                        onRetry = { vm.dismissWhiteboard(state.currentSceneId) },
                        onOpenFallback = {},
                    )
                } else {
                    BoxWithConstraints(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        val width = minOf(maxWidth, maxHeight * board.aspectRatio)
                        if (width > 0.dp) {
                            NativeSlideCanvas(
                                slide = board,
                                imageLoader = cache.imageLoader,
                                assetKeyPrefix = "${ref.stableKey}:${state.revision}:whiteboard",
                                mediaBase = mediaBase,
                                modifier = Modifier.width(width).height(width / board.aspectRatio),
                            )
                        }
                    }
                }
            }
        }
        val videoUrl = state.videoUrl
        if (videoUrl != null) {
            VideoDialog(
                url = videoUrl,
                dataSourceFactory = videoDataSourceFactory,
                onDismiss = { vm.dismissVideo(videoUrl) },
                onEnded = { vm.onVideoEnded(videoUrl) },
                onFailed = { vm.onVideoFailed(videoUrl, it) },
                paused = state.sequence.paused,
                onTogglePause = {
                    if (state.sequence.paused) vm.resumeSequence() else vm.pauseSequence()
                },
                onStop = vm::stopSequence,
                onOpenFallback = ref.webFallbackUrl
                    ?.takeIf { it.isNotBlank() }
                    ?.let { url -> { onOpenFallback(url) } },
            )
        }
        val endSummary = state.endSummary
        if (endSummary != null) {
            NativeEndSummaryDialog(
                summary = endSummary,
                onContinue = vm::dismissEnd,
                onFinish = { finishAndClose(endSummary.completed) },
            )
        }
    }
}

@Composable
private fun NativeSceneBody(
    state: NativeClassroomUiState,
    ref: NativeClassroomRef,
    vm: NativeClassroomViewModel,
    cache: NativeClassroomCache,
    zoom: Float,
    mediaBase: String?,
    lessonText: List<NativeCanvasElement.Text>,
    showCanvas: Boolean,
    lectureVisible: Boolean,
    onReadNotes: (Boolean) -> Unit,
    onZoom: (Float) -> Unit,
    onOpenFallback: (String) -> Unit,
    fitSlide: Boolean,
    controlsInHeader: Boolean,
    modifier: Modifier,
) {
    val hasFallback = !ref.webFallbackUrl.isNullOrBlank()
    val openFallback: () -> Unit = { ref.webFallbackUrl?.let(onOpenFallback) }
    when {
        state.loading && state.plan == null -> LoadingClassroom()
        state.plan == null -> NativeUnavailablePanel(
            reason = state.error ?: "课堂内容尚未加载完成。",
            hasFallback = hasFallback,
            onRetry = vm::retry,
            onOpenFallback = openFallback,
            modifier = modifier,
        )
        state.disposition.mode == NativeSceneMode.NATIVE -> NativeSceneContent(
            state = state,
            vm = vm,
            cache = cache,
            zoom = zoom,
            assetKeyPrefix = "${ref.stableKey}:${state.revision}",
            mediaBase = mediaBase,
            lessonText = lessonText,
            showCanvas = showCanvas,
            lectureVisible = lectureVisible,
            onReadNotes = onReadNotes,
            onZoom = onZoom,
            fitSlide = fitSlide,
            controlsInHeader = controlsInHeader,
            modifier = modifier,
        )
        state.disposition.mode == NativeSceneMode.SANDBOX_HTML ||
            state.disposition.mode == NativeSceneMode.SANDBOX_URL -> Column(modifier) {
            NativeFallbackBanner(
                reason = "这一页的互动内容在隔离的网页环境中播放。",
                hasFallback = hasFallback,
                onOpenFallback = openFallback,
                modifier = Modifier.padding(bottom = 8.dp),
            )
            NativeSandboxScene(
                mode = state.disposition.mode,
                payload = state.currentScenePlan?.sandboxPayload?.takeIf { it.isNotBlank() }
                    ?: state.currentSceneId?.let { id ->
                        state.document?.interactiveByScene?.get(id)?.let { it.html ?: it.url }
                    }.orEmpty(),
                trustedOrigin = ref.webFallbackUrl?.let {
                    com.example.campusai.data.remote.ClassroomUrlPolicy.originOf(it)
                },
                onBlocked = { vm.clearNotice() },
                modifier = Modifier.weight(1f).fillMaxWidth().clip(RoundedCornerShape(12.dp)),
            )
        }
        else -> NativeUnavailablePanel(
            reason = NativePlaybackPolicy.reasonText(state.disposition.reason),
            hasFallback = hasFallback,
            onRetry = vm::retry,
            onOpenFallback = openFallback,
            modifier = modifier,
        )
    }
}

@Composable
private fun NativeSceneContent(
    state: NativeClassroomUiState,
    vm: NativeClassroomViewModel,
    cache: NativeClassroomCache,
    zoom: Float,
    assetKeyPrefix: String,
    mediaBase: String?,
    lessonText: List<NativeCanvasElement.Text>,
    showCanvas: Boolean,
    lectureVisible: Boolean,
    onReadNotes: (Boolean) -> Unit,
    onZoom: (Float) -> Unit,
    fitSlide: Boolean,
    controlsInHeader: Boolean,
    modifier: Modifier = Modifier,
) {
    when (state.currentScenePlan?.type) {
        "slide" -> {
            val slide = state.currentSlide
            if (slide == null) {
                NativeUnavailablePanel(
                    reason = "这一页的讲义正文没有下发完整。",
                    hasFallback = false,
                    onRetry = vm::retry,
                    onOpenFallback = {},
                    modifier = modifier,
                )
            } else {
                val hasLessonText = lessonText.isNotEmpty()
                val frame = RoundedCornerShape(15.dp)
                BoxWithConstraints(
                    modifier.fillMaxWidth()
                        .shadow(10.dp, frame, clip = false)
                        .background(Brush.verticalGradient(listOf(Color(0xFF3B3E3D), Surface, Color(0xFF292827))), frame)
                        .border(1.dp, ClassroomWood.copy(alpha = .82f), frame)
                        .padding(7.dp),
                ) {
                    val stackToolbar = maxWidth < 300.dp
                    Column(
                        Modifier.then(if (fitSlide) Modifier.fillMaxSize() else Modifier.fillMaxWidth()),
                        verticalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        if (!controlsInHeader) {
                            SlideToolbar(hasLessonText, showCanvas, lectureVisible, zoom, onReadNotes, onZoom,
                                fillWidth = true, stack = stackToolbar)
                        }
                        if (showCanvas) {
                            val viewport = if (fitSlide) Modifier.weight(1f) else Modifier
                            BoxWithConstraints(viewport.fillMaxWidth(), contentAlignment = Alignment.Center) {
                                val width = if (fitSlide) minOf(maxWidth, maxHeight * slide.aspectRatio) else maxWidth
                                if (width > 0.dp) {
                                    Box(Modifier.width(width).height(width / slide.aspectRatio).clip(RoundedCornerShape(9.dp))) {
                                        NativeSlideCanvas(
                                            slide = slide,
                                            imageLoader = cache.imageLoader,
                                            spotlightElementId = state.spotlightElementId,
                                            laserElementId = state.laserElementId,
                                            onVideoClick = { vm.playVideo(it.source) },
                                            onAudioClick = vm::playElementAudio,
                                            assetKeyPrefix = assetKeyPrefix,
                                            mediaBase = mediaBase,
                                            modifier = Modifier.fillMaxSize().graphicsLayer(scaleX = zoom, scaleY = zoom),
                                        )
                                    }
                                }
                            }
                        } else {
                            val notes = if (fitSlide) Modifier.weight(1f).verticalScroll(rememberScrollState()) else Modifier
                            NativeLectureText(lessonText, notes)
                        }
                    }
                }
            }
        }
        "quiz" -> {
            val quiz = state.currentQuiz
            val quizState = state.quiz
            if (quiz == null || quizState == null) {
                NativeUnavailablePanel(
                    reason = "测验题目没有下发完整。",
                    hasFallback = false,
                    onRetry = vm::retry,
                    onOpenFallback = {},
                    modifier = modifier,
                )
            } else {
                NativeClassroomTheme(paper = true) {
                    NativeQuizPanel(
                        quiz = quiz,
                        sceneTitle = state.currentScene?.title ?: state.currentScenePlan?.title.orEmpty(),
                        state = quizState,
                        onAnswer = vm::setAnswer,
                        onSubmit = vm::submitQuiz,
                        onRetry = vm::retryQuiz,
                        onSelfCheck = vm::setShortAnswerSelfCheck,
                        onFinishReview = vm::finishQuizReview,
                        modifier = modifier,
                    )
                }
            }
        }
        "pbl" -> {
            val pbl = state.currentPbl
            if (pbl == null) {
                NativeUnavailablePanel(
                    reason = "项目式学习内容没有下发完整。",
                    hasFallback = false,
                    onRetry = vm::retry,
                    onOpenFallback = {},
                    modifier = modifier,
                )
            } else {
                NativeClassroomTheme(paper = true) {
                    NativePblPanel(
                        project = pbl,
                        hasFallback = false,
                        onOpenFallback = {},
                        modifier = modifier,
                    )
                }
            }
        }
        "interactive" -> {
            val sceneId = state.currentSceneId ?: return
            val revision = state.revision
            val limit = state.currentLimitExperiment
            val spatial = state.currentSpatialExperiment
            val parameter = state.currentParameterExperiment
            key(revision) {
                when {
                    limit != null -> NativeLimitExperimentPanel(
                        experiment = limit,
                        initial = vm.savedExperimentControls(sceneId, revision) ?: limit.initialControls(),
                        highlighted = ClassroomLimitExperiment.Highlight.fromSelector(state.spotlightElementId),
                        onControlsChanged = { vm.saveExperimentControls(sceneId, revision, it) },
                        modifier = modifier,
                    )
                    spatial != null -> NativeSpatialExperimentPanel(
                        experiment = spatial,
                        spatialControls = vm.spatialControls(
                            sceneId, revision, spatial.animated && !LocalReduceMotion.current,
                        ),
                        highlighted = state.spotlightElementId,
                        modifier = modifier,
                    )
                    parameter != null -> NativeParameterExperimentPanel(
                        experiment = parameter,
                        values = state.experimentValues,
                        highlighted = state.spotlightElementId,
                        onValuesChanged = { vm.updateExperimentValues(sceneId, revision, it) },
                        modifier = modifier,
                    )
                    else -> NativeUnavailablePanel(
                        reason = NativePlaybackPolicy.reasonText("interactive_native_renderer_missing"),
                        hasFallback = false,
                        onRetry = vm::retry,
                        onOpenFallback = {},
                        modifier = modifier,
                    )
                }
            }
        }
        else -> NativeUnavailablePanel(
            reason = "当前场景类型没有原生渲染器。",
            hasFallback = false,
            onRetry = vm::retry,
            onOpenFallback = {},
            modifier = modifier,
        )
    }
}

@Composable
private fun SlideToolbar(
    hasLessonText: Boolean,
    showCanvas: Boolean,
    lectureVisible: Boolean,
    zoom: Float,
    onReadNotes: (Boolean) -> Unit,
    onZoom: (Float) -> Unit,
    fillWidth: Boolean = false,
    stack: Boolean = false,
) {
    val modifier = if (fillWidth) Modifier.fillMaxWidth() else Modifier
    if (stack && hasLessonText && showCanvas) {
        Column(modifier) {
            SlideModePicker(showCanvas, lectureVisible, onReadNotes)
            SlideZoom(zoom, onZoom, Modifier.align(Alignment.End))
        }
    } else {
        Row(modifier, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            if (hasLessonText) SlideModePicker(showCanvas, lectureVisible, onReadNotes)
            if (fillWidth) Spacer(Modifier.weight(1f))
            if (showCanvas) SlideZoom(zoom, onZoom)
        }
    }
}

@Composable
private fun SlideModePicker(showCanvas: Boolean, lectureVisible: Boolean, onReadNotes: (Boolean) -> Unit) {
    val colors = FilterChipDefaults.filterChipColors(
        labelColor = Muted,
        selectedContainerColor = Primary,
        selectedLabelColor = Background,
    )
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        FilterChip(selected = showCanvas, onClick = { onReadNotes(false) },
            colors = colors, label = { Text("PPT") })
        FilterChip(selected = !showCanvas, onClick = { onReadNotes(true) }, enabled = !lectureVisible,
            colors = colors, label = { Text("讲义") })
    }
}

@Composable
private fun SlideZoom(zoom: Float, onZoom: (Float) -> Unit, modifier: Modifier = Modifier) {
    val decrease = { onZoom((zoom - 0.1f).coerceAtLeast(0.7f)) }
    val increase = { onZoom((zoom + 0.1f).coerceAtMost(1.6f)) }
    Row(modifier, horizontalArrangement = Arrangement.End, verticalAlignment = Alignment.CenterVertically) {
        IconButton(onClick = decrease, modifier = Modifier.width(44.dp)) {
            Icon(Icons.Default.Remove, "缩小课件", tint = Primary)
        }
        Text("${(zoom * 100).roundToInt()}%", color = TextPrimary, fontSize = 12.sp)
        IconButton(onClick = increase, modifier = Modifier.width(44.dp)) {
            Icon(Icons.Default.Add, "放大课件", tint = Primary)
        }
        IconButton(onClick = { onZoom(1f) }, modifier = Modifier.width(44.dp)) {
            Icon(Icons.Default.FitScreen, "整页", tint = Primary)
        }
    }
}

@Composable
private fun NativeLectureText(elements: List<NativeCanvasElement.Text>, modifier: Modifier = Modifier) {
    NativeClassroomTheme(paper = true) {
        Column(
            modifier.fillMaxWidth().background(Background, RoundedCornerShape(10.dp)).padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            elements.forEach { element ->
                val heading = element.textType == "title" || element.textType == "subtitle" ||
                    (element.bold && '\n' !in element.plainText && element.plainText.length <= 42)
                Text(
                    text = element.plainText,
                    color = if (heading) Primary else TextPrimary,
                    fontSize = if (heading) 18.sp else 16.sp,
                    lineHeight = if (heading) 25.sp else 24.sp,
                    fontWeight = if (element.bold || heading) FontWeight.Bold else FontWeight.Normal,
                    fontStyle = if (element.italic) FontStyle.Italic else FontStyle.Normal,
                    textDecoration = if (element.underline) TextDecoration.Underline else null,
                )
            }
        }
    }
}

@Composable
private fun LoadingClassroom() {
    Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        CircularProgressIndicator(color = Primary)
        Spacer(Modifier.height(10.dp))
        Text("正在读取课堂内容…", color = Muted, fontSize = 12.sp)
    }
}

@Composable
private fun VideoDialog(
    url: String,
    dataSourceFactory: DataSource.Factory,
    onDismiss: () -> Unit,
    onEnded: () -> Unit,
    onFailed: (String) -> Unit,
    paused: Boolean,
    onTogglePause: () -> Unit,
    onStop: () -> Unit,
    onOpenFallback: (() -> Unit)? = null,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var failed by remember(url) { mutableStateOf(false) }
    var attempt by remember(url) { mutableIntStateOf(0) }
    val exoPlayer = remember(url, attempt) {
        var endedReported = false
        var failureReported = false
        ExoPlayer.Builder(context, DefaultMediaSourceFactory(dataSourceFactory)).build().apply {
            setMediaItem(MediaItem.fromUri(url))
            prepare()
            playWhenReady = true
            addListener(object : Player.Listener {
                override fun onPlaybackStateChanged(playbackState: Int) {
                    if (playbackState == Player.STATE_ENDED && !endedReported) {
                        endedReported = true
                        onEnded()
                    }
                }

                override fun onPlayerError(error: PlaybackException) {
                    failed = true
                    if (!failureReported) {
                        failureReported = true
                        onFailed(error.message ?: "视频加载失败")
                    }
                }
            })
        }
    }
    DisposableEffect(exoPlayer) {
        onDispose { exoPlayer.release() }
    }
    LaunchedEffect(paused, exoPlayer, failed) {
        if (failed) return@LaunchedEffect
        if (paused) {
            exoPlayer.pause()
        } else if (exoPlayer.playbackState != Player.STATE_ENDED) {
            exoPlayer.play()
        }
    }
    DisposableEffect(lifecycleOwner, exoPlayer) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_PAUSE, Lifecycle.Event.ON_STOP -> exoPlayer.pause()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxWidth(0.94f).fillMaxHeight(0.72f), shape = RoundedCornerShape(16.dp), color = Color.Black) {
            Box(Modifier.fillMaxSize()) {
                if (failed) {
                    Column(
                        Modifier.fillMaxSize(),
                        verticalArrangement = Arrangement.Center,
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Text("视频加载失败，可重试或从网页入口继续。", color = Color.White, fontSize = 12.sp)
                        TextButton(onClick = {
                            failed = false
                            attempt++
                        }) {
                            Text("重试", color = Color.White)
                        }
                        onOpenFallback?.let { openFallback ->
                            TextButton(onClick = {
                                onDismiss()
                                openFallback()
                            }) {
                                Text("网页打开", color = Color.White)
                            }
                        }
                    }
                } else {
                    AndroidView(
                        modifier = Modifier.fillMaxSize(),
                        factory = {
                            PlayerView(it).apply {
                                player = exoPlayer
                                useController = true
                            }
                        },
                    )
                }
                Row(modifier = Modifier.align(Alignment.TopStart)) {
                    TextButton(onClick = onTogglePause) {
                        Text(if (paused) "继续" else "暂停", color = Color.White)
                    }
                    TextButton(onClick = onStop) {
                        Text("停止", color = Color.White)
                    }
                }
                TextButton(onClick = onDismiss, modifier = Modifier.align(Alignment.TopEnd)) {
                    Text("关闭", color = Color.White)
                }
            }
        }
    }
}

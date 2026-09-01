package com.example.campusai.ui.screens.focus

import com.example.campusai.ui.components.GlassButton as Button
import com.example.campusai.ui.components.GlassFloatingActionButton as FloatingActionButton
import com.example.campusai.ui.components.GlassIconButton as IconButton
import com.example.campusai.ui.components.GlassOutlinedButton as OutlinedButton
import com.example.campusai.ui.components.GlassTextButton as TextButton

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.view.PreviewView
import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.campusai.data.behavior.LearningContinuityState
import com.example.campusai.data.behavior.PresenceState
import com.example.campusai.data.focus.voice.AndroidSpeechRecognizerTranscriber
import com.example.campusai.data.focus.voice.AndroidTextToSpeechSynthesizer
import com.example.campusai.data.focus.voice.FocusVoiceController
import com.example.campusai.data.focus.voice.FocusVoiceMessageRole
import com.example.campusai.data.focus.voice.FocusVoicePhase
import com.example.campusai.data.focus.voice.RemoteFocusAiRepository
import com.example.campusai.data.focus.voice.RemoteRealtimeVoiceRepository
import com.example.campusai.data.focus.voice.SeeduplexRealtimeVoiceSession
import com.example.campusai.data.focus.scene.FocusScenePreferenceStore
import com.example.campusai.data.focus.goal.FocusGoalPlan
import com.example.campusai.data.focus.goal.FocusGoalPlanStore
import com.example.campusai.data.model.FocusSessionMode
import com.example.campusai.data.repository.ApiFocusRepository
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.remainingSeconds
import com.example.campusai.R
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.Instant

/** Immutable hand-off data used only while moving from a focus session to its summary. */
data class FocusSessionCompletion(
    val actualSeconds: Int,
    val taskName: String,
    val conversationCount: Int,
    val aiSummary: String,
    val observationSummary: String,
)

/**
 * The single execution page for an active focus session.
 * Voice and camera capabilities remain explicitly opt-in for the current visit.
 */
@Composable
fun FocusSessionScreen(
    appRepository: AppRepository,
    focusRepository: ApiFocusRepository,
    plannedDurationSeconds: Int,
    taskName: String,
    sessionMode: FocusSessionMode,
    onSessionCompleted: (FocusSessionCompletion) -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val manager = appRepository.expressionSessionManager
    val expressionResult by manager.result.collectAsStateWithLifecycle()
    val continuityState by manager.learningContinuityState.collectAsStateWithLifecycle()
    val presence by manager.presence.collectAsStateWithLifecycle()
    val gentleReminder by manager.gentleReminder.collectAsStateWithLifecycle()

    var microphonePermissionGranted by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED)
    }
    var cameraPermissionGranted by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
    }
    var appForeground by remember { mutableStateOf(true) }
    var voiceInstance by rememberSaveable { mutableIntStateOf(0) }
    var observationEnabled by rememberSaveable { mutableStateOf(false) }
    var conversationExpanded by rememberSaveable { mutableStateOf(false) }
    var observationDetailsExpanded by rememberSaveable { mutableStateOf(false) }
    var showEndConfirmation by rememberSaveable { mutableStateOf(false) }
    var finishingSession by rememberSaveable { mutableStateOf(false) }
    val scenePreferenceStore = remember(context) { FocusScenePreferenceStore(context) }
    val goalPlanStore = remember(context) { FocusGoalPlanStore(context) }
    var sceneSettings by remember(scenePreferenceStore) { mutableStateOf(scenePreferenceStore.load()) }
    var goalPlan by remember { mutableStateOf<FocusGoalPlan?>(null) }
    val activeFocusSession by focusRepository.activeSession.collectAsStateWithLifecycle()
    val focusScope = rememberCoroutineScope()
    val totalSeconds = plannedDurationSeconds.takeIf { it > 0 }
        ?: (activeFocusSession?.plannedDurationSeconds?.takeIf { it > 0 } ?: activeFocusSession?.mode?.totalSeconds ?: 0)
    var clockNow by remember { mutableStateOf(Instant.now()) }
    val focusRunning = activeFocusSession?.status == "active"
    val focusPaused = activeFocusSession?.status == "paused"
    LaunchedEffect(activeFocusSession?.id) {
        val stored = goalPlanStore.load()
        goalPlan = stored?.takeIf { it.sessionId == null || it.sessionId == activeFocusSession?.id }
    }
    val completionCoordinator = remember(activeFocusSession?.id, manager, focusRepository) {
        FocusCompletionCoordinator(
            finishObservation = manager::finishFocusSession,
            finishRemote = { summary -> focusRepository.finish(summary).isSuccess },
        )
    }
    // A focus visit is only left through its completion flow; it never returns to setup.
    BackHandler { showEndConfirmation = true }
    LaunchedEffect(focusRunning, activeFocusSession?.id) {
        while (focusRunning) {
            clockNow = Instant.now()
            delay(1_000)
        }
    }
    val secondsLeft = activeFocusSession?.remainingSeconds(clockNow) ?: totalSeconds
    LaunchedEffect(activeFocusSession?.id) {
        if (activeFocusSession != null) manager.beginFocusSession()
    }

    val voiceController = remember(context, voiceInstance) {
        FocusVoiceController(
            transcriber = AndroidSpeechRecognizerTranscriber(context),
            aiRepository = RemoteFocusAiRepository,
            synthesizer = AndroidTextToSpeechSynthesizer(context),
            scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate),
            realtimeRepository = RemoteRealtimeVoiceRepository,
            realtimeSession = SeeduplexRealtimeVoiceSession(context),
        )
    }
    var realtimeStatus by remember(voiceController) { mutableStateOf(FocusVoicePhase.IDLE) }
    var voiceError by remember(voiceController) { mutableStateOf<String?>(null) }
    var currentUserText by remember(voiceController) { mutableStateOf("") }
    var currentAiText by remember(voiceController) { mutableStateOf("") }
    var currentResponseCompleted by remember(voiceController) { mutableStateOf(false) }
    var historyMessages by remember { mutableStateOf<List<CompletedConversation>>(emptyList()) }
    val archiveCurrentConversation = {
        val userText = currentUserText.trim()
        val aiText = currentAiText.trim()
        if (currentResponseCompleted && userText.isNotEmpty() && aiText.isNotEmpty()) {
            historyMessages = historyMessages + CompletedConversation(userText = userText, aiText = aiText)
        }
        currentUserText = ""
        currentAiText = ""
        currentResponseCompleted = false
    }
    LaunchedEffect(voiceController) {
        var lastUserMessageId = 0L
        var lastAssistantMessageId = 0L
        var latestTranscriptHypothesis = ""
        var pendingAiSentence = ""
        var lastAnswerFragment = ""
        voiceController.state.collect { rawState ->
            realtimeStatus = rawState.phase
            voiceError = rawState.errorMessage

            // Keep interim ASR outside Compose. A newer hypothesis replaces the previous one
            // when it extends it, so it can never produce repeated text such as "什么是什么".
            rawState.liveTranscript?.takeIf { it.isNotBlank() }?.let { hypothesis ->
                latestTranscriptHypothesis = mergeTranscriptHypothesis(latestTranscriptHypothesis, hypothesis)
            }
            val latestUser = rawState.messages.lastOrNull { it.role == FocusVoiceMessageRole.USER }
            if (latestUser != null && latestUser.id > lastUserMessageId) {
                if (currentResponseCompleted) archiveCurrentConversation()
                lastUserMessageId = latestUser.id
                currentUserText = latestUser.text
                latestTranscriptHypothesis = latestUser.text
                currentAiText = ""
                currentResponseCompleted = false
            } else if (
                currentUserText.isEmpty() &&
                latestTranscriptHypothesis.isNotEmpty() &&
                (rawState.phase == FocusVoicePhase.THINKING || rawState.phase == FocusVoicePhase.SPEAKING)
            ) {
                // Fallback for providers that emit only a final transcript delta.
                currentUserText = latestTranscriptHypothesis
            }

            // Accumulate transport tokens off the Compose state path, then publish only at
            // Chinese sentence boundaries. This is sentence-level streaming, not token UI.
            rawState.liveAnswer?.takeIf { it.isNotBlank() && it != lastAnswerFragment }?.let { fragment ->
                lastAnswerFragment = fragment
                pendingAiSentence += fragment
                val boundary = pendingAiSentence.lastIndexOfAny(charArrayOf('。', '！', '？', '；'))
                if (boundary >= 0) {
                    currentAiText += pendingAiSentence.substring(0, boundary + 1)
                    pendingAiSentence = pendingAiSentence.substring(boundary + 1)
                }
            }
            val latestAssistant = rawState.messages.lastOrNull { it.role == FocusVoiceMessageRole.ASSISTANT }
            if (latestAssistant != null && latestAssistant.id > lastAssistantMessageId) {
                lastAssistantMessageId = latestAssistant.id
                val completedUser = rawState.messages.lastOrNull {
                    it.role == FocusVoiceMessageRole.USER && it.id < latestAssistant.id
                }
                val userText = currentUserText.ifBlank { completedUser?.text ?: latestTranscriptHypothesis }.trim()
                if (currentUserText.isEmpty()) currentUserText = userText
                // Preserve this completed turn in the live area. The final event only fills
                // the trailing text that did not end in a Chinese sentence delimiter.
                currentAiText = appendMissingFinalAnswer(
                    displayedText = currentAiText,
                    pendingText = pendingAiSentence,
                    completedText = latestAssistant.text,
                )
                currentResponseCompleted = userText.isNotEmpty()
                pendingAiSentence = ""
                lastAnswerFragment = ""
                latestTranscriptHypothesis = ""
            }
        }
    }
    val microphonePermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        microphonePermissionGranted = granted
        if (granted) voiceController.connectRealtime() else voiceController.reportPermissionDenied()
    }
    val cameraPermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        cameraPermissionGranted = granted
        observationEnabled = granted && sessionMode == FocusSessionMode.SMART_GUARD
    }

    LaunchedEffect(sessionMode, microphonePermissionGranted) {
        if (sessionMode != FocusSessionMode.QUIET) {
            if (microphonePermissionGranted) voiceController.connectRealtime()
            else microphonePermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
        }
    }
    LaunchedEffect(realtimeStatus, sessionMode, microphonePermissionGranted) {
        if (
            realtimeStatus == FocusVoicePhase.ERROR &&
            sessionMode != FocusSessionMode.QUIET &&
            microphonePermissionGranted
        ) {
            // Keep a long-running focus visit hands-free: transient network failures recover
            // without requiring the user to leave the session or tap a reconnect button.
            delay(1_500)
            voiceController.connectRealtime()
        }
    }
    LaunchedEffect(sessionMode, cameraPermissionGranted) {
        if (sessionMode == FocusSessionMode.SMART_GUARD) {
            if (cameraPermissionGranted) observationEnabled = true
            else cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    LaunchedEffect(observationEnabled, cameraPermissionGranted, appForeground, focusRunning) {
        manager.updateEligibility(
            enabled = observationEnabled,
            permissionGranted = cameraPermissionGranted,
            running = observationEnabled && focusRunning,
            visible = observationEnabled,
            foreground = appForeground,
            mode = com.example.campusai.data.model.FocusMode.FOCUS,
        )
    }
    DisposableEffect(lifecycleOwner, voiceController) {
        val observer = LifecycleEventObserver { _, event ->
            appForeground = event != Lifecycle.Event.ON_STOP
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            voiceController.release()
            manager.detachPreviewAsync()
        }
    }

    val completeSession: suspend () -> Unit = {
        val actualSeconds = (totalSeconds - secondsLeft).coerceAtLeast(0)
        val observation = completionCoordinator.complete(
            actualFocusMinutes = (actualSeconds / 60).coerceAtLeast(1),
        )
        if (observation != null) {
            goalPlanStore.clear()
            val conversations = historyMessages.size + if (currentUserText.isNotBlank()) 1 else 0
            onSessionCompleted(
                FocusSessionCompletion(
                    actualSeconds = actualSeconds,
                    taskName = taskName,
                    conversationCount = conversations,
                    aiSummary = "你完成了“$taskName”的这段专注。${if (conversations > 0) "我们一起交流了 $conversations 次，" else "你保持了安静投入，"}继续保持这个节奏。",
                    observationSummary = observation.toCompanionSummary(),
                ),
            )
        } else if (!completionCoordinator.isCompleted) {
            finishingSession = false
            showEndConfirmation = false
        }
    }
    LaunchedEffect(activeFocusSession?.id, secondsLeft, focusRunning) {
        if (focusRunning && secondsLeft == 0 && !finishingSession) {
            finishingSession = true
            completeSession()
        }
    }

    FocusAmbientPlaybackEffect(
        settings = sceneSettings,
        sessionRunning = focusRunning,
        appForeground = appForeground,
        phase = realtimeStatus,
    )
    BoxWithConstraints(modifier = Modifier.fillMaxSize()) {
        val compactLayout = maxHeight < 720.dp
        val statusBarInset = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
        FocusSceneStage(
            scene = sceneSettings.scene,
            modifier = Modifier.fillMaxSize(),
            robotContent = {
                FocusSpaceGuide(
                    phase = realtimeStatus,
                    onInterrupt = voiceController::interruptRealtime,
                    compact = compactLayout,
                    modifier = Modifier
                        .align(Alignment.TopCenter)
                        .padding(start = 16.dp, top = if (compactLayout) 158.dp else 174.dp, end = 16.dp),
                )
            },
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(start = 16.dp, top = statusBarInset + 12.dp, end = 16.dp, bottom = 32.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                Text(
                    "专注空间",
                    color = Color.White,
                    fontSize = 24.sp,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.headlineSmall,
                )
                FocusSceneToolbar(
                    settings = sceneSettings,
                    onSettingsChange = { updated ->
                        sceneSettings = updated
                        scenePreferenceStore.save(updated)
                    },
                )
                Spacer(Modifier.height(if (compactLayout) 170.dp else 198.dp))
                FocusSpaceTimer(secondsLeft = secondsLeft, totalSeconds = totalSeconds, taskName = taskName, paused = focusPaused)
                goalPlan?.let { plan ->
                    FocusGoalProgressPanel(plan = plan, onStepToggle = { stepNumber, completed ->
                        val updated = plan.copy(steps = plan.steps.map { step -> if (step.number == stepNumber) step.copy(completed = completed) else step })
                        goalPlan = updated
                        goalPlanStore.save(updated)
                    })
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    OutlinedButton(
                        onClick = { focusScope.launch { if (focusRunning) focusRepository.pause() else if (focusPaused) focusRepository.resume() } },
                        modifier = Modifier.weight(1f).height(52.dp),
                        enabled = focusRunning || focusPaused,
                        shape = RoundedCornerShape(18.dp),
                    ) { Icon(if (focusRunning) Icons.Default.Pause else Icons.Default.PlayArrow, null); Spacer(Modifier.width(6.dp)); Text(if (focusRunning) "暂停" else "继续") }
                    Button(
                        onClick = { showEndConfirmation = true },
                        modifier = Modifier.weight(1f).height(52.dp),
                        shape = RoundedCornerShape(18.dp),
                        enabled = !finishingSession,
                    ) { Icon(Icons.Default.Stop, null); Spacer(Modifier.width(6.dp)); Text(if (finishingSession) "正在生成总结" else "结束专注") }
                }
                FocusSensingSystem(
                    phase = realtimeStatus,
                    errorMessage = voiceError,
                    userText = currentUserText,
                    aiText = currentAiText,
                    enabled = observationEnabled,
                    state = continuityState,
                    sessionMode = sessionMode,
                    expanded = observationDetailsExpanded,
                    expressionLabel = expressionResult?.label?.name,
                    presence = presence.state,
                    reminder = presentFocusReminder(sessionMode, observationEnabled, gentleReminder),
                    onToggleDetails = { observationDetailsExpanded = !observationDetailsExpanded },
                    onAttachPreview = { preview -> manager.attachPreview(lifecycleOwner, preview) },
                )
            }
            FocusChatFloatingButton(
                messageCount = historyMessages.size + if (currentUserText.isNotBlank() || currentAiText.isNotBlank()) 1 else 0,
                onClick = { conversationExpanded = true },
                modifier = Modifier.align(Alignment.BottomEnd).padding(22.dp),
            )
            FocusConversationOverlay(
                visible = conversationExpanded,
                userText = currentUserText,
                aiText = currentAiText,
                phase = realtimeStatus,
                history = historyMessages,
                onDismiss = { conversationExpanded = false },
            )
        }
    }
    if (showEndConfirmation) {
        AlertDialog(
            onDismissRequest = { if (!finishingSession) showEndConfirmation = false },
            title = { Text("结束本次专注？") },
            text = { Text("AI 将根据本次学习时长、交流和学习状态生成总结。") },
            confirmButton = {
                TextButton(
                    enabled = !finishingSession,
                    onClick = {
                        finishingSession = true
                        focusScope.launch { completeSession() }
                    },
                ) { Text("结束并生成总结", color = Primary) }
            },
            dismissButton = { TextButton(enabled = !finishingSession, onClick = { showEndConfirmation = false }) { Text("继续专注") } },
        )
    }
}

@Composable
private fun FocusSpaceGuide(
    phase: FocusVoicePhase,
    onInterrupt: () -> Unit,
    compact: Boolean,
    modifier: Modifier = Modifier,
) {
    val motion = rememberInfiniteTransition(label = "focus-guide-motion")
    val floatingOffset by motion.animateFloat(
        initialValue = -4f,
        targetValue = 4f,
        animationSpec = infiniteRepeatable(tween(1500, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "focus-guide-float",
    )
    val message = when (phase) {
        FocusVoicePhase.IDLE -> "我会陪你开始这段专注"
        FocusVoicePhase.LISTENING -> "我在听"
        FocusVoicePhase.THINKING -> "让我想想"
        FocusVoicePhase.SPEAKING -> "正在回答你"
        FocusVoicePhase.CONNECTING, FocusVoicePhase.RECONNECTING -> "正在来到你的专注空间"
        FocusVoicePhase.ERROR -> "我暂时没能连接上"
    }
    Box(modifier.fillMaxWidth().height(if (compact) 184.dp else 210.dp)) {
        Image(
            painter = painterResource(R.drawable.ai_campus_robot),
            contentDescription = "CampusMate AI 导员",
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .offset(y = floatingOffset.dp)
                .size(if (compact) 142.dp else 168.dp),
            contentScale = ContentScale.Fit,
            alpha = .98f,
        )
        FocusGlassPanel(
            modifier = Modifier
                .align(Alignment.TopStart)
                .padding(top = 6.dp, end = if (compact) 104.dp else 118.dp),
            tint = Color.White.copy(alpha = .56f),
        ) {
            Column(Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
                Text("CampusMate AI", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                GuideTypewriterText(message)
            }
        }
        when (phase) {
            FocusVoicePhase.LISTENING -> VoiceWaveBadge(Modifier.align(Alignment.CenterEnd).padding(end = 15.dp))
            FocusVoicePhase.THINKING -> Text("…", modifier = Modifier.align(Alignment.CenterEnd).padding(end = 24.dp), color = Primary, fontWeight = FontWeight.Black, fontSize = 34.sp)
            FocusVoicePhase.SPEAKING -> Icon(Icons.Default.GraphicEq, null, tint = Color(0xFF54D8EB), modifier = Modifier.align(Alignment.CenterEnd).padding(end = 18.dp).size(30.dp))
            else -> Unit
        }
        AnimatedVisibility(
            visible = phase == FocusVoicePhase.THINKING || phase == FocusVoicePhase.SPEAKING,
            modifier = Modifier.align(Alignment.BottomEnd).padding(10.dp),
            enter = fadeIn() + slideInVertically(),
            exit = fadeOut() + slideOutVertically(),
        ) { TextButton(onClick = onInterrupt) { Text("打断回答", color = Primary) } }
    }
}

@Composable
private fun GuideTypewriterText(message: String) {
    var displayedLength by remember(message) { mutableIntStateOf(0) }
    LaunchedEffect(message) {
        displayedLength = 0
        while (displayedLength < message.length) {
            delay(55)
            displayedLength++
        }
    }
    Text(message.take(displayedLength), color = TextPrimary, fontSize = 16.sp, lineHeight = 22.sp)
}

@Composable
private fun VoiceWaveBadge(modifier: Modifier = Modifier) {
    val wave = rememberInfiniteTransition(label = "guide-listening-wave")
    Surface(modifier = modifier, shape = RoundedCornerShape(16.dp), color = Color(0xFF172755).copy(alpha = .85f)) {
        Row(Modifier.padding(horizontal = 9.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(3.dp), verticalAlignment = Alignment.CenterVertically) {
            listOf(0, 130, 260).forEach { delayMillis ->
                val height by wave.animateFloat(8f, 22f, infiniteRepeatable(tween(500, delayMillis = delayMillis), RepeatMode.Reverse), label = "guide-wave-$delayMillis")
                Box(Modifier.width(3.dp).height(height.dp).background(Color(0xFF70E5F8), RoundedCornerShape(2.dp)))
            }
        }
    }
}

@Composable
private fun FocusSpaceTimer(secondsLeft: Int, totalSeconds: Int, taskName: String, paused: Boolean, modifier: Modifier = Modifier) {
    val minutes = (secondsLeft.coerceAtLeast(0) / 60).toString().padStart(2, '0')
    val seconds = (secondsLeft.coerceAtLeast(0) % 60).toString().padStart(2, '0')
    val progress = (secondsLeft.toFloat() / totalSeconds.coerceAtLeast(1)).coerceIn(0f, 1f)
    FocusGlassPanel(modifier = modifier.fillMaxWidth(), tint = Color.White.copy(alpha = .56f)) {
        Column(Modifier.padding(vertical = 20.dp, horizontal = 20.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Box(contentAlignment = Alignment.Center, modifier = Modifier.size(180.dp)) {
                CircularProgressIndicator(
                    progress = progress,
                    modifier = Modifier.fillMaxSize(),
                    color = Primary,
                    trackColor = Color.White.copy(alpha = .82f),
                    strokeWidth = 8.dp,
                )
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("$minutes:$seconds", color = TextPrimary, fontSize = 45.sp, fontWeight = FontWeight.ExtraBold)
                    Text(if (paused) "已暂停" else "正在专注", color = Primary, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                }
            }
            Text("本次学习 · $taskName", color = TextPrimary, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(if (paused) "暂停中，准备好后可以继续" else "AI 陪伴中", color = Muted, fontSize = 12.sp)
        }
    }
}

/** Voice subtitles and learning awareness are one quiet companion system. */
@Composable
private fun FocusSensingSystem(
    phase: FocusVoicePhase,
    errorMessage: String?,
    userText: String,
    aiText: String,
    enabled: Boolean,
    state: LearningContinuityState,
    sessionMode: FocusSessionMode,
    expanded: Boolean,
    expressionLabel: String?,
    presence: PresenceState,
    reminder: String?,
    onToggleDetails: () -> Unit,
    onAttachPreview: (PreviewView) -> Unit,
) {
    val voiceLabel = when (phase) {
        FocusVoicePhase.LISTENING -> "正在聆听"
        FocusVoicePhase.THINKING -> "正在思考"
        FocusVoicePhase.SPEAKING -> "正在回答"
        FocusVoicePhase.CONNECTING, FocusVoicePhase.RECONNECTING -> "正在连接"
        FocusVoicePhase.ERROR -> "暂时未连接"
        FocusVoicePhase.IDLE -> "正在陪伴"
    }
    val observationMessage = reminder ?: when {
        !enabled || sessionMode != FocusSessionMode.SMART_GUARD -> "需要时可开启学习状态感知。"
        presence == PresenceState.ABSENT -> "我发现你离开了一会，需要暂停吗？"
        state == LearningContinuityState.STUDYING -> "你的专注状态很好，继续保持。"
        state == LearningContinuityState.PAUSED -> "看起来你正在短暂调整，准备好后我们继续。"
        else -> "我会安静关注你的学习状态，帮助你保持专注。"
    }
    FocusGlassPanel(modifier = Modifier.fillMaxWidth(), tint = Color.White.copy(alpha = .58f)) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(shape = CircleShape, color = PrimarySoft) { Icon(Icons.Default.GraphicEq, null, tint = Primary, modifier = Modifier.padding(8.dp).size(18.dp)) }
                Spacer(Modifier.width(9.dp))
                Column(Modifier.weight(1f)) {
                    Text("CampusMate AI", color = TextPrimary, fontWeight = FontWeight.Bold)
                    Text("● $voiceLabel", color = Primary, fontSize = 12.sp)
                }
                if (phase == FocusVoicePhase.SPEAKING || phase == FocusVoicePhase.THINKING) VoiceStatusAnimation(phase)
            }
            if (userText.isNotBlank() || aiText.isNotBlank() || phase == FocusVoicePhase.THINKING || phase == FocusVoicePhase.SPEAKING) {
                Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    userText.takeIf { it.isNotBlank() }?.let { Text("我：$it", color = TextPrimary, fontSize = 14.sp) }
                    if (aiText.isNotBlank() || phase == FocusVoicePhase.THINKING || phase == FocusVoicePhase.SPEAKING) {
                        Text("CampusMate：${aiText.ifBlank { if (phase == FocusVoicePhase.THINKING) "正在思考…" else "正在回答…" }}", color = Muted, fontSize = 14.sp)
                    }
                }
            } else {
                Text("需要帮助时可以直接说话。", color = Muted, fontSize = 12.sp)
            }
            errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error, fontSize = 12.sp) }
            HorizontalDivider(color = PrimarySoft)
            Row(
                modifier = Modifier.fillMaxWidth().clickable(onClick = onToggleDetails),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Icons.Default.Visibility, null, tint = Primary, modifier = Modifier.size(19.dp))
                Spacer(Modifier.width(8.dp))
                Column(Modifier.weight(1f)) {
                    Text("AI 学习观察", color = TextPrimary, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                    Text("● ${if (enabled && sessionMode == FocusSessionMode.SMART_GUARD) "正在关注你的学习状态" else "暂未开启智能观察"}", color = if (enabled) Primary else Muted, fontSize = 12.sp)
                }
                Icon(if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore, null, tint = Primary)
            }
            Text(
                "CampusMate：$observationMessage",
                color = if (reminder != null) Primary else Muted,
                fontSize = 12.sp,
                fontWeight = if (reminder != null) FontWeight.SemiBold else FontWeight.Normal,
            )
            AnimatedVisibility(visible = expanded, enter = fadeIn() + slideInVertically(), exit = fadeOut() + slideOutVertically()) {
                Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
                    Text("学习状态详情", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                    if (enabled && sessionMode == FocusSessionMode.SMART_GUARD) {
                        AndroidView(
                            factory = { cameraContext -> PreviewView(cameraContext).apply {
                                scaleType = PreviewView.ScaleType.FILL_CENTER
                                implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                                onAttachPreview(this)
                            } },
                            modifier = Modifier.fillMaxWidth().aspectRatio(3f / 4f).clip(RoundedCornerShape(16.dp)),
                        )
                    }
                    Text("人在座位：${if (presence == PresenceState.PRESENT) "是" else "正在识别"}", color = TextPrimary, fontSize = 12.sp)
                    Text("状态分析：${expressionLabel ?: observationLabel(state)}", color = TextPrimary, fontSize = 12.sp)
                }
            }
        }
    }
}

@Composable
private fun FocusCompanionStatus(phase: FocusVoicePhase, errorMessage: String?) {
    val phaseText = when (phase) {
        FocusVoicePhase.LISTENING -> "正在聆听"
        FocusVoicePhase.THINKING -> "正在思考"
        FocusVoicePhase.SPEAKING -> "正在回答"
        FocusVoicePhase.CONNECTING, FocusVoicePhase.RECONNECTING -> "正在连接"
        FocusVoicePhase.ERROR -> "暂时未连接"
        FocusVoicePhase.IDLE -> "正在陪伴"
    }
    Surface(shape = RoundedCornerShape(22.dp), color = Surface) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(shape = CircleShape, color = PrimarySoft) { Icon(Icons.Default.SmartToy, null, tint = Primary, modifier = Modifier.padding(8.dp)) }
                Spacer(Modifier.width(10.dp))
                Column {
                    Text("CampusMate AI", color = TextPrimary, fontWeight = FontWeight.Bold)
                    Text("● $phaseText", color = Primary, fontSize = 12.sp)
                }
            }
            HorizontalDivider(color = PrimarySoft)
            Text("语音交流 · 已开启", color = TextPrimary, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
            Text("需要帮助时可以直接说话", color = Muted, fontSize = 12.sp)
            errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error, fontSize = 12.sp) }
        }
    }
}

@Composable
private fun FocusObservationStatus(
    enabled: Boolean,
    state: LearningContinuityState,
    sessionMode: FocusSessionMode,
    expanded: Boolean,
    expressionLabel: String?,
    presence: PresenceState,
    onToggleDetails: () -> Unit,
    onAttachPreview: (PreviewView) -> Unit,
) {
    val description = when {
        sessionMode != FocusSessionMode.SMART_GUARD -> "暂未开启智能观察"
        !enabled -> "暂未开启智能观察"
        state == LearningContinuityState.STUDYING -> "当前专注状态良好"
        else -> "正在观察你的学习状态"
    }
    Surface(shape = RoundedCornerShape(22.dp), color = Surface) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth().clickable(onClick = onToggleDetails),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Surface(shape = CircleShape, color = PrimarySoft) { Icon(Icons.Default.Visibility, null, tint = Primary, modifier = Modifier.padding(8.dp)) }
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text("AI 学习观察", color = TextPrimary, fontWeight = FontWeight.Bold)
                    Text("● ${if (enabled && sessionMode == FocusSessionMode.SMART_GUARD) "正在观察" else "暂未开启"}", color = if (enabled) Primary else Muted, fontSize = 12.sp)
                }
                Icon(if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore, contentDescription = "学习状态详情", tint = Primary)
            }
            Text(if (enabled) "我会关注你的学习状态，帮助保持专注" else description, color = Muted, fontSize = 12.sp)
            AnimatedVisibility(visible = expanded, enter = fadeIn() + slideInVertically(), exit = fadeOut() + slideOutVertically()) {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("学习状态详情", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                    if (enabled && sessionMode == FocusSessionMode.SMART_GUARD) {
                        AndroidView(
                            factory = { cameraContext ->
                                PreviewView(cameraContext).apply {
                                    scaleType = PreviewView.ScaleType.FILL_CENTER
                                    implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                                    onAttachPreview(this)
                                }
                            },
                            modifier = Modifier.fillMaxWidth().height(170.dp).clip(RoundedCornerShape(16.dp)),
                        )
                    } else {
                        Surface(shape = RoundedCornerShape(16.dp), color = PrimarySoft) {
                            Text("智能观察仅在“智能监督”模式下开启。", Modifier.padding(14.dp), color = Muted, fontSize = 12.sp)
                        }
                    }
                    Text("人在画面中：${if (presence == PresenceState.PRESENT) "是" else "正在识别"}", color = TextPrimary, fontSize = 12.sp)
                    Text("状态分析：${expressionLabel ?: observationLabel(state)}", color = TextPrimary, fontSize = 12.sp)
                }
            }
        }
    }
}

@Composable
private fun FocusChatFloatingButton(messageCount: Int, onClick: () -> Unit, modifier: Modifier = Modifier) {
    Box(modifier = modifier) {
        FloatingActionButton(
            onClick = onClick,
            containerColor = Primary,
            contentColor = Color.White,
            shape = CircleShape,
        ) { Icon(Icons.Default.ChatBubbleOutline, contentDescription = "查看本次对话") }
        if (messageCount > 0) {
            Surface(
                modifier = Modifier.align(Alignment.TopEnd).offset(x = 5.dp, y = (-5).dp),
                shape = CircleShape,
                color = Color(0xFFFF8A65),
            ) { Text(messageCount.coerceAtMost(9).toString(), modifier = Modifier.padding(horizontal = 5.dp, vertical = 1.dp), color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Bold) }
        }
    }
}

@Composable
private fun FocusConversationOverlay(
    visible: Boolean,
    userText: String,
    aiText: String,
    phase: FocusVoicePhase,
    history: List<CompletedConversation>,
    onDismiss: () -> Unit,
) {
    AnimatedVisibility(
        visible = visible,
        modifier = Modifier.fillMaxSize(),
        enter = fadeIn(tween(180)) + scaleIn(initialScale = .8f, animationSpec = tween(280)),
        exit = fadeOut(tween(160)) + scaleOut(targetScale = .9f, animationSpec = tween(180)),
    ) {
        Box(Modifier.fillMaxSize()) {
            Box(Modifier.matchParentSize().background(Color(0xFF18234A).copy(alpha = .20f)).clickable(onClick = onDismiss))
            Surface(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(16.dp)
                    .fillMaxWidth()
                    .heightIn(max = 680.dp),
                shape = RoundedCornerShape(28.dp),
                color = Color.White.copy(alpha = .96f),
                shadowElevation = 12.dp,
            ) {
                Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("本次对话", color = TextPrimary, fontWeight = FontWeight.ExtraBold, fontSize = 18.sp, modifier = Modifier.weight(1f))
                        IconButton(onClick = onDismiss, modifier = Modifier.size(32.dp)) { Icon(Icons.Default.Close, contentDescription = "关闭对话", tint = Muted) }
                    }
                    Column(Modifier.weight(1f, fill = false).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(9.dp)) {
                        if (userText.isNotBlank() || aiText.isNotBlank()) CurrentConversationCard(userText, aiText, phase)
                        history.asReversed().forEach { turn ->
                            Surface(shape = RoundedCornerShape(16.dp), color = PrimarySoft.copy(alpha = .70f)) {
                                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Text("我：${turn.userText}", color = TextPrimary, fontSize = 13.sp)
                                    Text("CampusMate：${turn.aiText}", color = Muted, fontSize = 13.sp)
                                }
                            }
                        }
                        if (history.isEmpty() && userText.isBlank() && aiText.isBlank()) Text("开始说话后，你和 AI 的对话会显示在这里。", color = Muted, fontSize = 13.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun FocusExecutionCard(
    secondsLeft: Int,
    taskName: String,
    focusRunning: Boolean,
    focusPaused: Boolean,
    showAiStatus: Boolean,
    aiCompanionEnabled: Boolean,
    onPauseResume: () -> Unit,
    onFinish: () -> Unit,
) {
    val minutes = (secondsLeft.coerceAtLeast(0) / 60).toString().padStart(2, '0')
    val seconds = (secondsLeft.coerceAtLeast(0) % 60).toString().padStart(2, '0')
    Surface(shape = RoundedCornerShape(22.dp), color = PrimarySoft) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(18.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text("$minutes:$seconds", color = TextPrimary, fontSize = 42.sp, style = MaterialTheme.typography.headlineMedium)
            Text(taskName, color = TextPrimary, style = MaterialTheme.typography.titleMedium)
            if (showAiStatus) {
                Text(if (aiCompanionEnabled) "AI 陪伴中" else "正在连接 AI 陪伴…", color = Primary, fontSize = 13.sp)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                if (focusRunning || focusPaused) {
                    OutlinedButton(onClick = onPauseResume) {
                        Icon(if (focusRunning) Icons.Default.Pause else Icons.Default.PlayArrow, null)
                        Spacer(Modifier.width(5.dp))
                        Text(if (focusRunning) "暂停" else "继续")
                    }
                    TextButton(onClick = onFinish) { Text("结束专注") }
                } else {
                    Text("准备开始", color = Muted, fontSize = 13.sp)
                }
            }
        }
    }
}

@Composable
private fun AssistantVoiceCard(
    phase: FocusVoicePhase,
    errorMessage: String?,
    onStart: () -> Unit,
    onInterrupt: () -> Unit,
    onClose: () -> Unit,
) {
    val label = when (phase) {
        FocusVoicePhase.IDLE -> "准备开始"
        FocusVoicePhase.CONNECTING -> "正在连接"
        FocusVoicePhase.LISTENING -> "正在聆听…"
        FocusVoicePhase.THINKING -> "正在思考…"
        FocusVoicePhase.SPEAKING -> "AI 正在回答…"
        FocusVoicePhase.RECONNECTING -> "正在重新连接"
        FocusVoicePhase.ERROR -> "连接失败"
    }
    Surface(shape = RoundedCornerShape(22.dp), color = Surface) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(shape = CircleShape, color = PrimarySoft) { Icon(Icons.Default.SmartToy, null, Modifier.padding(9.dp), tint = Primary) }
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text("CampusMate AI", color = TextPrimary, style = MaterialTheme.typography.titleMedium)
                    Text(label, color = Muted, fontSize = 12.sp)
                }
                when (phase) {
                    FocusVoicePhase.IDLE, FocusVoicePhase.ERROR -> Button(onClick = onStart) { Text("开始陪伴") }
                    else -> OutlinedButton(onClick = onClose) { Text("关闭陪伴", color = Primary) }
                }
            }
            VoiceStatusAnimation(phase)
            Text("开启后静默等待你自然开口。", color = Muted, fontSize = 12.sp)
            errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error, fontSize = 12.sp) }
            if (phase == FocusVoicePhase.THINKING || phase == FocusVoicePhase.SPEAKING) {
                TextButton(onClick = onInterrupt, modifier = Modifier.align(Alignment.End)) { Text("打断回答", color = Primary) }
            }
        }
    }
}

@Composable
private fun VoiceStatusAnimation(phase: FocusVoicePhase) {
    val transition = rememberInfiniteTransition(label = "voice-status")
    when (phase) {
        FocusVoicePhase.LISTENING -> {
            val pulse by transition.animateFloat(
                initialValue = 0f,
                targetValue = 1f,
                animationSpec = infiniteRepeatable(tween(900, easing = FastOutSlowInEasing), RepeatMode.Reverse),
                label = "listening-pulse",
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(
                    modifier = Modifier.size((40f + pulse * 8f).dp),
                    shape = CircleShape,
                    color = Primary.copy(alpha = 0.14f + pulse * 0.12f),
                ) {
                    Icon(Icons.Default.Mic, null, Modifier.padding(9.dp), tint = Primary)
                }
                Spacer(Modifier.width(10.dp))
                Text("正在聆听你的声音", color = Primary, fontSize = 13.sp)
            }
        }
        FocusVoicePhase.THINKING -> {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("正在整理回答", color = Primary, fontSize = 13.sp)
                Spacer(Modifier.width(8.dp))
                listOf(0, 160, 320).forEach { delay ->
                    val dot by transition.animateFloat(
                        initialValue = 0.35f,
                        targetValue = 1f,
                        animationSpec = infiniteRepeatable(tween(620, delayMillis = delay), RepeatMode.Reverse),
                        label = "thinking-dot-$delay",
                    )
                    Box(
                        Modifier.padding(horizontal = 2.dp).size(6.dp)
                            .clip(CircleShape).background(Primary.copy(alpha = dot)),
                    )
                }
            }
        }
        FocusVoicePhase.SPEAKING -> {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.GraphicEq, null, tint = Primary)
                Spacer(Modifier.width(8.dp))
                Row(
                    modifier = Modifier.height(28.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(3.dp),
                ) {
                    listOf(0, 110, 220, 330).forEach { delay ->
                        val wave by transition.animateFloat(
                            initialValue = 0.2f,
                            targetValue = 1f,
                            animationSpec = infiniteRepeatable(tween(520, delayMillis = delay), RepeatMode.Reverse),
                            label = "speaking-wave-$delay",
                        )
                        Box(
                            Modifier.width(4.dp).height((6f + wave * 18f).dp)
                                .clip(RoundedCornerShape(4.dp)).background(Primary),
                        )
                    }
                }
                Spacer(Modifier.width(10.dp))
                Text("AI 正在回答", color = Primary, fontSize = 13.sp)
            }
        }
        else -> Unit
    }
}

@Composable
private fun CurrentConversationCard(
    userText: String,
    aiText: String,
    realtimeStatus: FocusVoicePhase,
) {
    Surface(shape = RoundedCornerShape(18.dp), color = PrimarySoft) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("当前对话", color = TextPrimary, style = MaterialTheme.typography.titleSmall)
            if (userText.isNotEmpty()) {
                Text("我：", color = Muted, fontSize = 12.sp)
                Text(userText, color = TextPrimary, fontSize = 15.sp)
            }
            if (aiText.isNotEmpty() || realtimeStatus == FocusVoicePhase.THINKING || realtimeStatus == FocusVoicePhase.SPEAKING) {
                Text("CampusMate：", color = Muted, fontSize = 12.sp)
                Text(
                    aiText.ifEmpty { if (realtimeStatus == FocusVoicePhase.THINKING) "正在思考..." else "正在回答..." },
                    color = TextPrimary,
                    fontSize = 15.sp,
                )
            }
        }
    }
}

/** Keeps the live ASR/TTS subtitles visible as a single conversation, not a separate tool. */
@Composable
private fun FocusConversationTimeline(
    userText: String,
    aiText: String,
    phase: FocusVoicePhase,
    history: List<CompletedConversation>,
    expanded: Boolean,
    onToggle: () -> Unit,
) {
    Surface(shape = RoundedCornerShape(22.dp), color = PrimarySoft.copy(alpha = .72f)) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(Modifier.fillMaxWidth().clickable(onClick = onToggle), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.ChatBubbleOutline, contentDescription = null, tint = Primary, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(8.dp))
                Text("本次对话", color = TextPrimary, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                Text(if (expanded) "收起" else "查看记录", color = Primary, fontSize = 12.sp)
                Icon(if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore, contentDescription = null, tint = Primary)
            }
            if (userText.isNotBlank() || aiText.isNotBlank() || phase == FocusVoicePhase.THINKING || phase == FocusVoicePhase.SPEAKING) {
                CurrentConversationCard(userText, aiText, phase)
            } else {
                Text("你说的话和我的回复会显示在这里。", color = Muted, fontSize = 12.sp)
            }
            AnimatedVisibility(visible = expanded, enter = fadeIn() + slideInVertically(), exit = fadeOut() + slideOutVertically()) {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    history.asReversed().forEach { turn ->
                        Surface(shape = RoundedCornerShape(16.dp), color = Color.White.copy(alpha = .76f)) {
                            Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                Text("我 · ${turn.userText}", color = TextPrimary, fontSize = 13.sp)
                                Text("CampusMate · ${turn.aiText}", color = Muted, fontSize = 13.sp)
                            }
                        }
                    }
                    if (history.isEmpty()) Text("还没有已完成的对话记录。", color = Muted, fontSize = 12.sp)
                }
            }
        }
    }
}

@Composable
private fun AssistantChip(icon: androidx.compose.ui.graphics.vector.ImageVector, text: String) {
    Surface(shape = RoundedCornerShape(12.dp), color = PrimarySoft) {
        Row(Modifier.padding(horizontal = 8.dp, vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, null, modifier = Modifier.size(14.dp), tint = Primary)
            Spacer(Modifier.width(4.dp))
            Text(text, color = TextPrimary, fontSize = 11.sp)
        }
    }
}

private fun observationLabel(state: LearningContinuityState): String = when (state) {
    LearningContinuityState.OBSERVING -> "正在观察"
    LearningContinuityState.STUDYING -> "学习进行中"
    LearningContinuityState.THINKING_OR_ADJUSTING -> "短暂思考或调整中"
    LearningContinuityState.PAUSED -> "暂时停顿"
}

private fun expressionLabel(name: String): String = name.lowercase().replace('_', ' ')

private data class CompletedConversation(
    val userText: String,
    val aiText: String,
)

/**
 * ASR engines may send either a complete hypothesis or a suffix. Prefer replacement for a
 * complete/new hypothesis; only retain the longer text when one is clearly a prefix of the other.
 */
private fun mergeTranscriptHypothesis(previous: String, incoming: String): String = when {
    previous.isBlank() -> incoming
    incoming.startsWith(previous) -> incoming
    previous.startsWith(incoming) -> previous
    else -> incoming
}

/** Adds only the unseen tail from the final event; sentence-level text already shown stays put. */
private fun appendMissingFinalAnswer(
    displayedText: String,
    pendingText: String,
    completedText: String,
): String {
    var result = displayedText
    if (pendingText.isNotBlank() && !result.endsWith(pendingText)) result += pendingText
    val completed = completedText.trim()
    return when {
        completed.isBlank() || result.endsWith(completed) -> result
        completed.startsWith(result) -> result + completed.removePrefix(result)
        result.isBlank() -> completed
        else -> result
    }
}

private fun com.example.campusai.data.model.FocusSessionSummary.toCompanionSummary(): String = when {
    behaviorSummary?.phoneInteractionCount?.let { it > 0 } == true ->
        "学习过程中检测到 ${behaviorSummary.phoneInteractionCount} 次持续手机交互；如用于查资料可忽略，否则下次可以把手机放远一些。"
    behaviorSummary?.possibleDistractionCount?.let { it > 0 } == true ->
        "中途有一些短暂调整，但你重新回到了学习节奏。"
    noFaceEventCount > 0 -> "学习过程中有短暂离开座位的情况，回来后你仍继续完成了这段专注。"
    breakSuggestionCount > 0 -> "你持续学习了一段时间，记得在下一次开始前让眼睛和身体稍作休息。"
    possibleDistractionDurationSeconds > 60 -> "中途有一些调整，但你重新回到了学习节奏。"
    else -> "你的学习状态整体稳定，专注节奏很好。"
}

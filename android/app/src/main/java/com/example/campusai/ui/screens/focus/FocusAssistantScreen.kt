package com.example.campusai.ui.screens.focus

import com.example.campusai.ui.components.GlassButton as Button
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
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
import com.example.campusai.data.focus.scene.FocusScenePreferenceStore
import com.example.campusai.data.focus.scene.FocusSceneSettings
import com.example.campusai.data.focus.voice.AndroidSpeechRecognizerTranscriber
import com.example.campusai.data.focus.voice.AndroidTextToSpeechSynthesizer
import com.example.campusai.data.focus.voice.FocusVoiceController
import com.example.campusai.data.focus.voice.FocusVoiceMessageRole
import com.example.campusai.data.focus.voice.FocusVoicePhase
import com.example.campusai.data.focus.voice.RemoteFocusAiRepository
import com.example.campusai.data.focus.voice.RemoteRealtimeVoiceRepository
import com.example.campusai.data.focus.voice.SeeduplexRealtimeVoiceSession
import com.example.campusai.data.model.FocusSessionMode
import com.example.campusai.data.repository.ApiFocusRepository
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.FocusPlanRepository
import com.example.campusai.data.repository.remainingSeconds
import com.example.campusai.ui.glass.CampusGlassRole
import com.example.campusai.ui.glass.campusGlass
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
    val planTaskId: String? = null,
    val nextStepTitle: String? = null,
    val planComplete: Boolean = false,
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
    planTaskId: String? = null,
    planRepository: FocusPlanRepository,
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
    var finishingSession by remember { mutableStateOf(false) }
    var timerExpired by rememberSaveable { mutableStateOf(false) }
    var completionPrompted by rememberSaveable { mutableStateOf(false) }
    var selfReport by rememberSaveable { mutableStateOf("") }
    var completionError by rememberSaveable { mutableStateOf<String?>(null) }
    val scenePreferenceStore = remember(context) { FocusScenePreferenceStore(context) }
    var sceneSettings by remember(scenePreferenceStore) { mutableStateOf(scenePreferenceStore.load()) }
    val updateSceneSettings: (FocusSceneSettings) -> Unit = { nextSettings ->
        sceneSettings = nextSettings
        scenePreferenceStore.save(nextSettings)
    }
    val activeFocusSession by focusRepository.activeSession.collectAsStateWithLifecycle()
    val focusScope = rememberCoroutineScope()
    val totalSeconds = plannedDurationSeconds.takeIf { it > 0 }
        ?: (activeFocusSession?.plannedDurationSeconds?.takeIf { it > 0 } ?: activeFocusSession?.mode?.totalSeconds ?: 0)
    var clockNow by remember { mutableStateOf(Instant.now()) }
    val focusRunning = activeFocusSession?.status == "active"
    val focusPaused = activeFocusSession?.status == "paused"
    val completionCoordinator = remember(activeFocusSession?.id, manager, focusRepository) {
        FocusCompletionCoordinator(
            finishObservation = manager::finishFocusSession,
            finishRemote = { summary, report -> focusRepository.finish(summary, report).isSuccess },
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
    LaunchedEffect(activeFocusSession?.id) {
        if (activeFocusSession != null) manager.beginFocusSession()
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
        manager.attachLifecycle(lifecycleOwner)
        val observer = LifecycleEventObserver { _, event ->
            appForeground = event != Lifecycle.Event.ON_STOP
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            voiceController.release()
            manager.detachPreviewAsync()
            manager.detachLifecycle()
        }
    }
    val completeSession: suspend (Boolean) -> Unit = completeSession@{ completePlanStep ->
        val actualSeconds = (totalSeconds - secondsLeft).coerceAtLeast(0)
        val taskId = planTaskId
        val sessionId = activeFocusSession?.id
        completionError = null
        val intentSaved = runCatching {
            if (completePlanStep && taskId != null && sessionId != null) {
                checkNotNull(planRepository.prepareStepCompletion(taskId, sessionId)) {
                    "当前没有可完成的规划步骤"
                }
            } else if (taskId != null && sessionId != null) {
                planRepository.discardPreparedCompletion(taskId, sessionId)
            }
        }.isSuccess
        if (!intentSaved) {
            completionError = "暂时无法保存完成状态，请重试"
            finishingSession = false
            return@completeSession
        }
        val completion = runCatching {
            completionCoordinator.complete(
                actualFocusMinutes = (actualSeconds / 60).coerceAtLeast(1),
                selfReport = selfReport,
                completePlanStep = completePlanStep,
            )
        }.getOrElse {
            completionError = it.message ?: "暂时无法结束专注，请重试"
            finishingSession = false
            return@completeSession
        }
        if (completion != null) {
            val updatedPlan = taskId?.let {
                if (completion.completePlanStep && sessionId != null) {
                    runCatching { planRepository.commitPreparedCompletion(it, sessionId) }
                        .getOrNull()
                        ?: planRepository.getPlan(it)
                }
                else planRepository.getPlan(it)
            }
            if (updatedPlan?.taskCompletionPending == true) {
                planRepository.syncPendingTaskCompletions { pendingTaskId ->
                    appRepository.completeTaskStrict(pendingTaskId).isSuccess
                }
            }
            val conversations = historyMessages.size + if (currentUserText.isNotBlank()) 1 else 0
            onSessionCompleted(
                FocusSessionCompletion(
                    actualSeconds = actualSeconds,
                    taskName = taskName,
                    conversationCount = conversations,
                    aiSummary = "你完成了“$taskName”的这段专注。${if (conversations > 0) "我们一起交流了 $conversations 次，" else "你保持了安静投入，"}继续保持这个节奏。",
                    observationSummary = completion.summary.toCompanionSummary(),
                    planTaskId = planTaskId,
                    nextStepTitle = updatedPlan?.currentStep?.title,
                    planComplete = updatedPlan?.isComplete == true,
                ),
            )
        } else if (!completionCoordinator.isCompleted) {
            finishingSession = false
            showEndConfirmation = true
        }
    }
    LaunchedEffect(activeFocusSession?.id, secondsLeft, focusRunning) {
        if (focusRunning && secondsLeft == 0 && !completionPrompted) {
            completionPrompted = true
            timerExpired = true
            showEndConfirmation = true
        }
    }

    FocusAmbientPlaybackEffect(
        settings = sceneSettings,
        sessionRunning = focusRunning,
        appForeground = appForeground,
        phase = realtimeStatus,
    )

    FocusSceneStage(
        scene = sceneSettings.scene,
        modifier = Modifier.fillMaxSize(),
        robotContent = {},
    ) {
        FocusExecutionContent(
            sceneSettings = sceneSettings,
            onSceneSettingsChange = updateSceneSettings,
            realtimeStatus = realtimeStatus,
            voiceError = voiceError,
            currentUserText = currentUserText,
            currentAiText = currentAiText,
            observationEnabled = observationEnabled,
            continuityState = continuityState,
            sessionMode = sessionMode,
            observationDetailsExpanded = observationDetailsExpanded,
            expressionLabel = expressionResult?.label?.name,
            presence = presence.state,
            gentleReminder = gentleReminder,
            onToggleDetails = { observationDetailsExpanded = !observationDetailsExpanded },
            onAttachPreview = { preview -> manager.attachPreview(lifecycleOwner, preview) },
            onInterrupt = voiceController::interruptRealtime,
            secondsLeft = secondsLeft,
            totalSeconds = totalSeconds,
            taskName = taskName,
            focusPaused = focusPaused,
            focusRunning = focusRunning,
            onPauseResume = { focusScope.launch { if (focusRunning) focusRepository.pause() else if (focusPaused) focusRepository.resume() } },
            finishingSession = finishingSession,
            onFinish = { showEndConfirmation = true },
            historyMessages = historyMessages,
            conversationExpanded = conversationExpanded,
            onOpenConversation = { conversationExpanded = true },
            onCloseConversation = { conversationExpanded = false },
        )
    }
    if (showEndConfirmation) {
        AlertDialog(
            onDismissRequest = {
                if (!finishingSession && !timerExpired) showEndConfirmation = false
            },
            title = { Text(if (timerExpired) "本次计时已完成" else "结束本次专注？") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("AI 将根据本次学习时长、交流和学习状态生成总结。")
                    OutlinedTextField(
                        value = selfReport,
                        onValueChange = { selfReport = it.take(2_000) },
                        label = { Text("本次学习感受（选填）") },
                        placeholder = { Text("例如：练习题比预想的难") },
                        minLines = 2,
                        maxLines = 4,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    completionError?.let { error ->
                        Text(error, color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
                    }
                }
            },
            confirmButton = {
                TextButton(
                    enabled = !finishingSession,
                    onClick = {
                        finishingSession = true
                        focusScope.launch {
                            completeSession(planTaskId != null)
                        }
                    },
                ) {
                    Text(
                        if (planTaskId != null) "完成步骤并结束" else "结束并生成总结",
                        color = Primary,
                    )
                }
            },
            dismissButton = {
                Row {
                    if (!timerExpired) {
                        TextButton(
                            enabled = !finishingSession,
                            onClick = { showEndConfirmation = false },
                        ) { Text("继续专注") }
                    }
                    if (planTaskId != null) {
                        TextButton(
                            enabled = !finishingSession,
                            onClick = {
                                finishingSession = true
                                focusScope.launch { completeSession(false) }
                            },
                        ) { Text("仅结束专注") }
                    }
                }
            },
        )
    }
}

@Composable
private fun FocusExecutionContent(
    sceneSettings: FocusSceneSettings,
    onSceneSettingsChange: (FocusSceneSettings) -> Unit,
    realtimeStatus: FocusVoicePhase,
    voiceError: String?,
    currentUserText: String,
    currentAiText: String,
    observationEnabled: Boolean,
    continuityState: LearningContinuityState,
    sessionMode: FocusSessionMode,
    observationDetailsExpanded: Boolean,
    expressionLabel: String?,
    presence: PresenceState,
    gentleReminder: String?,
    onToggleDetails: () -> Unit,
    onAttachPreview: (PreviewView) -> Unit,
    onInterrupt: () -> Unit,
    secondsLeft: Int,
    totalSeconds: Int,
    taskName: String,
    focusPaused: Boolean,
    focusRunning: Boolean,
    onPauseResume: () -> Unit,
    finishingSession: Boolean,
    onFinish: () -> Unit,
    historyMessages: List<CompletedConversation>,
    conversationExpanded: Boolean,
    onOpenConversation: () -> Unit,
    onCloseConversation: () -> Unit,
) {
    BoxWithConstraints(
        Modifier
            .fillMaxSize()
            .windowInsetsPadding(WindowInsets.safeDrawing)
            .padding(horizontal = 16.dp, vertical = 10.dp),
    ) {
        val stageLayout = focusStageLayout(maxWidth.value.toInt(), maxHeight.value.toInt())
        val timerSize = if (stageLayout == FocusStageLayout.LANDSCAPE) {
            188.dp
        } else {
            (maxWidth - 132.dp).coerceIn(164.dp, 214.dp)
        }

        Row(
            modifier = Modifier.fillMaxWidth().align(Alignment.TopCenter),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text("专注空间", color = Color.White, fontSize = 19.sp, fontWeight = FontWeight.Bold)
                Text(taskName, color = Color.White.copy(alpha = .72f), fontSize = 11.sp, maxLines = 1)
            }
            FocusSceneToolbar(
                settings = sceneSettings,
                onSettingsChange = onSceneSettingsChange,
            )
        }

        Row(
            modifier = Modifier
                .align(Alignment.Center)
                .widthIn(max = 520.dp)
                .fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            FocusPrimaryIconButton(
                onClick = onPauseResume,
                enabled = focusRunning || focusPaused,
                contentDescription = if (focusRunning) "暂停专注" else "继续专注",
            ) {
                Icon(if (focusRunning) Icons.Default.Pause else Icons.Default.PlayArrow, contentDescription = null)
            }
            FocusSpaceTimer(
                secondsLeft = secondsLeft,
                totalSeconds = totalSeconds,
                taskName = taskName,
                paused = focusPaused,
                modifier = Modifier.size(timerSize),
            )
            FocusPrimaryIconButton(
                onClick = onFinish,
                enabled = !finishingSession,
                contentDescription = if (finishingSession) "正在生成总结" else "结束专注",
            ) {
                Icon(Icons.Default.Stop, contentDescription = null)
            }
        }

        AnimatedVisibility(
            visible = observationDetailsExpanded,
            modifier = Modifier
                .align(if (stageLayout == FocusStageLayout.LANDSCAPE) Alignment.BottomStart else Alignment.BottomCenter)
                .padding(bottom = 66.dp)
                .widthIn(max = if (stageLayout == FocusStageLayout.LANDSCAPE) 360.dp else 520.dp)
                .heightIn(max = (maxHeight - 150.dp).coerceAtLeast(160.dp))
                .verticalScroll(rememberScrollState()),
            enter = fadeIn() + slideInVertically { it / 3 },
            exit = fadeOut() + slideOutVertically { it / 3 },
        ) {
            FocusSensingSystem(
                phase = realtimeStatus,
                errorMessage = voiceError,
                userText = currentUserText,
                aiText = currentAiText,
                enabled = observationEnabled,
                state = continuityState,
                sessionMode = sessionMode,
                expanded = observationDetailsExpanded,
                expressionLabel = expressionLabel,
                presence = presence,
                reminder = presentFocusReminder(sessionMode, observationEnabled, gentleReminder),
                onToggleDetails = onToggleDetails,
                onAttachPreview = onAttachPreview,
            )
        }

        FocusCompanionDock(
            phase = realtimeStatus,
            observationEnabled = observationEnabled,
            messageCount = historyMessages.size + if (currentUserText.isNotBlank() || currentAiText.isNotBlank()) 1 else 0,
            onToggleDetails = onToggleDetails,
            onInterrupt = onInterrupt,
            onOpenConversation = onOpenConversation,
            modifier = Modifier.align(Alignment.BottomCenter),
        )
        FocusConversationOverlay(
            visible = conversationExpanded,
            userText = currentUserText,
            aiText = currentAiText,
            phase = realtimeStatus,
            history = historyMessages,
            onDismiss = onCloseConversation,
        )
    }
}

@Composable
private fun FocusPrimaryIconButton(
    onClick: () -> Unit,
    enabled: Boolean,
    contentDescription: String,
    content: @Composable () -> Unit,
) {
    IconButton(
        onClick = onClick,
        enabled = enabled,
        modifier = Modifier.size(58.dp).semantics { this.contentDescription = contentDescription },
    ) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            CompositionLocalProvider(LocalContentColor provides Color.White) { content() }
        }
    }
}

@Composable
private fun FocusSpaceTimer(secondsLeft: Int, totalSeconds: Int, taskName: String, paused: Boolean, modifier: Modifier = Modifier) {
    val minutes = (secondsLeft.coerceAtLeast(0) / 60).toString().padStart(2, '0')
    val seconds = (secondsLeft.coerceAtLeast(0) % 60).toString().padStart(2, '0')
    val progress = (secondsLeft.toFloat() / totalSeconds.coerceAtLeast(1)).coerceIn(0f, 1f)
    Box(
        contentAlignment = Alignment.Center,
        modifier = modifier.campusGlass(
            shape = CircleShape,
            role = CampusGlassRole.PANEL,
            tint = Color.White.copy(alpha = .14f),
        ),
    ) {
        CircularProgressIndicator(
            progress = { progress },
            modifier = Modifier.fillMaxSize().padding(5.dp),
            color = Color.White.copy(alpha = .94f),
            trackColor = Color.White.copy(alpha = .18f),
            strokeWidth = 5.dp,
        )
        Column(
            modifier = Modifier.padding(horizontal = 18.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(3.dp),
        ) {
            Text("$minutes:$seconds", color = Color.White, fontSize = 43.sp, fontWeight = FontWeight.ExtraBold)
            Text(if (paused) "已暂停" else "正在专注", color = Color.White.copy(alpha = .82f), fontSize = 12.sp, fontWeight = FontWeight.Bold)
            Text(taskName, color = Color.White.copy(alpha = .66f), fontSize = 10.sp, maxLines = 1)
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
    Surface(
        modifier = Modifier.campusGlass(
            shape = RoundedCornerShape(26.dp),
            role = CampusGlassRole.PANEL,
            tint = Color.White.copy(alpha = .34f),
        ),
        shape = RoundedCornerShape(26.dp),
        color = Color.Transparent,
        border = androidx.compose.foundation.BorderStroke(1.dp, Color.White.copy(alpha = .30f)),
    ) {
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
private fun FocusCompanionDock(
    phase: FocusVoicePhase,
    observationEnabled: Boolean,
    messageCount: Int,
    onToggleDetails: () -> Unit,
    onInterrupt: () -> Unit,
    onOpenConversation: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val voiceLabel = when (phase) {
        FocusVoicePhase.LISTENING -> "AI 正在聆听"
        FocusVoicePhase.THINKING -> "AI 正在思考"
        FocusVoicePhase.SPEAKING -> "AI 正在回答"
        FocusVoicePhase.CONNECTING, FocusVoicePhase.RECONNECTING -> "AI 正在连接"
        FocusVoicePhase.ERROR -> "AI 暂未连接"
        FocusVoicePhase.IDLE -> if (observationEnabled) "AI 观察中" else "AI 陪伴中"
    }
    Row(
        modifier = modifier
            .campusGlass(
                shape = RoundedCornerShape(100.dp),
                role = CampusGlassRole.NAVIGATION,
                tint = Color.Black.copy(alpha = .16f),
            )
            .padding(horizontal = 7.dp, vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Row(
            modifier = Modifier
                .height(46.dp)
                .clip(RoundedCornerShape(100.dp))
                .clickable(onClick = onToggleDetails)
                .padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(Icons.Default.GraphicEq, contentDescription = null, tint = Color.White, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(7.dp))
            Text(voiceLabel, color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
        }
        if (phase == FocusVoicePhase.THINKING || phase == FocusVoicePhase.SPEAKING) {
            IconButton(onClick = onInterrupt, modifier = Modifier.size(46.dp)) {
                Icon(Icons.Default.Stop, contentDescription = "打断 AI 回答", tint = Color.White)
            }
        }
        Box {
            IconButton(onClick = onOpenConversation, modifier = Modifier.size(46.dp)) {
                Icon(Icons.Default.ChatBubbleOutline, contentDescription = "查看本次对话", tint = Color.White)
            }
            if (messageCount > 0) {
                Surface(
                    modifier = Modifier.align(Alignment.TopEnd),
                    shape = CircleShape,
                    color = Color(0xFFFF8A65),
                ) {
                    Text(
                        messageCount.coerceAtMost(9).toString(),
                        modifier = Modifier.padding(horizontal = 4.dp, vertical = 1.dp),
                        color = Color.White,
                        fontSize = 9.sp,
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
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

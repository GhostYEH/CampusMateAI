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
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.keyframes
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.campusai.R
import com.example.campusai.BuildConfig
import com.example.campusai.data.behavior.BehaviorDatasetCaptureState
import com.example.campusai.data.behavior.BehaviorDatasetLabel
import com.example.campusai.data.behavior.BehaviorDisplayState
import com.example.campusai.data.behavior.BehaviorInputDebugExporter
import com.example.campusai.data.behavior.BehaviorObservationSummary
import com.example.campusai.data.behavior.LearningContinuityState
import com.example.campusai.data.behavior.PresenceSnapshot
import com.example.campusai.data.behavior.PresenceState
import com.example.campusai.data.behavior.PersonDetectionSnapshot
import com.example.campusai.data.behavior.StudyBehavior
import com.example.campusai.data.behavior.isRunning
import com.example.campusai.data.expression.ExpressionServiceStatus
import com.example.campusai.data.focus.goal.FocusGoalPlan
import com.example.campusai.data.focus.goal.FocusGoalPlanStore
import com.example.campusai.data.focus.voice.AndroidSpeechRecognizerTranscriber
import com.example.campusai.data.focus.voice.AndroidTextToSpeechSynthesizer
import com.example.campusai.data.focus.voice.FocusVoiceController
import com.example.campusai.data.focus.voice.FocusVoicePhase
import com.example.campusai.data.focus.voice.FocusVoiceState
import com.example.campusai.data.focus.voice.RemoteFocusAiRepository
import com.example.campusai.data.focus.voice.RemoteRealtimeVoiceRepository
import com.example.campusai.data.focus.voice.SeeduplexRealtimeVoiceSession
import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.ExpressionResult
import com.example.campusai.data.model.FocusMode
import com.example.campusai.data.model.FocusSessionMode
import com.example.campusai.data.model.FocusSessionSummary
import com.example.campusai.data.repository.ApiFocusRepository
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.remainingSeconds
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.roundToInt
import java.time.Instant

private val FocusBlue: Color @Composable get() = Primary
private val FocusViolet: Color @Composable get() = PrimaryHover
private val FocusOrange: Color @Composable get() = Accent
private val FocusGreen: Color @Composable get() = Success
private val FocusBg: Color @Composable get() = Background

private enum class GuideDialogueState { GREETING, ASK_DURATION, ASK_MODE, CONFIRM, ENTER_SESSION }
private enum class GuideNpcState { IDLE, LISTENING, THINKING, HAPPY }

/** Focus home: configure a session and review focus progress. */
@Composable
fun FocusScreen(
    repository: ApiFocusRepository,
    appRepository: AppRepository,
    reduceMotion: Boolean,
    onBack: () -> Unit,
    relatedTaskId: String? = null,
    onOpenCounselorPlan: (String) -> Unit,
    onOpenAssistant: (durationSeconds: Int, taskName: String, sessionMode: FocusSessionMode) -> Unit,
    onOpenHistory: () -> Unit,
) {
    val stats by repository.stats.collectAsStateWithLifecycle()
    val records by repository.records.collectAsStateWithLifecycle()
    val activeSession by repository.activeSession.collectAsStateWithLifecycle()
    val remoteError by repository.error.collectAsStateWithLifecycle()
    val backendOnline by appRepository.backendOnline.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val manager = appRepository.expressionSessionManager
    val taskName = relatedTaskId?.let(appRepository::getTaskById)?.title ?: "本次专注"
    var mode by remember { mutableStateOf(FocusMode.FOCUS) }
    var sessionMode by remember { mutableStateOf(FocusSessionMode.QUIET) }
    var selectedSecondsLeft by remember { mutableIntStateOf(FocusMode.FOCUS.totalSeconds) }
    var selectedDurationMinutes by remember { mutableIntStateOf(25) }
    var customDurationInput by remember { mutableStateOf("60") }
    var showCustomDurationDialog by remember { mutableStateOf(false) }
    var showGoalDialog by remember { mutableStateOf(false) }
    var selectedGoal by remember(stats.goalMinutes) { mutableIntStateOf(stats.goalMinutes) }
    var showGoalPlanner by rememberSaveable { mutableStateOf(false) }
    var goalPlan by remember { mutableStateOf<FocusGoalPlan?>(null) }
    var guideState by rememberSaveable { mutableStateOf(GuideDialogueState.GREETING) }
    var arranging by rememberSaveable { mutableStateOf(false) }
    var countdown by rememberSaveable { mutableIntStateOf(0) }

    LaunchedEffect(backendOnline) {
        if (backendOnline) repository.refresh()
    }
    val bottomContentPadding = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + 26.dp
    val listState = rememberLazyListState()
    val startFocus: () -> Unit = {
        scope.launch {
            when (activeSession?.status) {
                null -> {
                    val startResult = repository.start(mode, goalPlan?.goal, relatedTaskId, selectedDurationMinutes * 60)
                    if (startResult.isSuccess) {
                        goalPlan?.let { plan -> FocusGoalPlanStore(context).save(plan.copy(sessionId = startResult.getOrNull()?.id)) }
                            ?: FocusGoalPlanStore(context).clear()
                        selectedSecondsLeft = mode.totalSeconds
                        manager.beginFocusSession()
                        onOpenAssistant(selectedDurationMinutes * 60, goalPlan?.goal ?: taskName, sessionMode)
                    }
                }
                else -> onOpenAssistant(activeSession?.plannedDurationSeconds?.takeIf { it > 0 } ?: mode.totalSeconds, taskName, sessionMode)
            }
        }
        Unit
    }
    LaunchedEffect(arranging) {
        if (arranging) {
            delay(500)
            arranging = false
            guideState = GuideDialogueState.ASK_DURATION
        }
    }
    LaunchedEffect(guideState) {
        if (guideState == GuideDialogueState.CONFIRM) {
            delay(900)
            for (number in 3 downTo 1) {
                countdown = number
                delay(700)
            }
            guideState = GuideDialogueState.ENTER_SESSION
            startFocus()
        }
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize().background(FocusBg),
        state = listState,
        contentPadding = PaddingValues(start = 16.dp, top = 20.dp, end = 16.dp, bottom = bottomContentPadding),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        (if (!backendOnline && remoteError == null) "专注大厅需要连接真实后端后才能使用" else remoteError)?.let { message ->
            item { Surface(color = AlertErrorBg, shape = RoundedCornerShape(16.dp)) { Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) { Icon(Icons.Default.CloudOff, null, tint = AlertErrorText); Spacer(Modifier.width(8.dp)); Text(message, Modifier.weight(1f), color = AlertErrorText, fontSize = 12.sp); TextButton(onClick = { scope.launch { appRepository.refreshBackendStatus(); if (appRepository.backendOnline.value) repository.refresh() } }) { Text("重试", color = FocusBlue) } } } }
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("专注大厅", color = TextPrimary, fontWeight = FontWeight.ExtraBold, fontSize = 32.sp)
                Text("CampusMate AI 导员", color = FocusViolet, fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
            }
        }
        item {
            FocusHallDialogue(
                state = guideState,
                arranging = arranging,
                countdown = countdown,
                selectedMinutes = selectedDurationMinutes,
                selectedMode = sessionMode,
                onReady = { arranging = true },
                onPlan = { showGoalPlanner = true },
                onOpenHistory = onOpenHistory,
                onSelectMinutes = { minutes -> selectedDurationMinutes = minutes; selectedSecondsLeft = minutes * 60; guideState = GuideDialogueState.ASK_MODE },
                onCustom = { showCustomDurationDialog = true },
                onSelectMode = { selected -> sessionMode = selected; guideState = GuideDialogueState.CONFIRM },
            )
        }
        item {
            Surface(shape = RoundedCornerShape(24.dp), color = Surface, border = BorderStroke(1.dp, Line)) {
                Column(Modifier.padding(16.dp)) {
                    Text("今日学习数据 ✦", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 17.sp)
                    Spacer(Modifier.height(14.dp))
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) { FocusStat(Modifier.weight(1f), Icons.Default.Timer, stats.todayMinutes.toString(), "分钟", "今日专注", PrimarySoft); FocusStat(Modifier.weight(1f), Icons.Default.LocalFireDepartment, stats.streakDays.toString(), "天", "连续天数", Accent.copy(alpha = .14f)); FocusStat(Modifier.weight(1f), Icons.Default.MilitaryTech, stats.todayCount.toString(), "次", "完成次数", Background) }
                }
            }
        }
    }
    if (showCustomDurationDialog) AlertDialog(
        onDismissRequest = { showCustomDurationDialog = false },
        title = { Text("自定义专注时长") },
        text = { OutlinedTextField(value = customDurationInput, onValueChange = { customDurationInput = it.filter(Char::isDigit) }, label = { Text("分钟（5–240）") }, singleLine = true) },
        confirmButton = { TextButton(onClick = { customDurationInput.toIntOrNull()?.coerceIn(5, 240)?.let { selectedDurationMinutes = it; selectedSecondsLeft = it * 60; guideState = GuideDialogueState.ASK_MODE }; showCustomDurationDialog = false }) { Text("确定", color = FocusBlue) } },
        dismissButton = { TextButton(onClick = { showCustomDurationDialog = false }) { Text("取消") } },
    )
    if (showGoalPlanner) FocusGoalPlannerDialog(
        repository = repository,
        initialPlan = goalPlan,
        onDismiss = { showGoalPlanner = false },
        onPlanReady = { plan ->
            goalPlan = plan
            showGoalPlanner = false
            guideState = GuideDialogueState.ASK_DURATION
        },
    )
}

@Composable
private fun FocusGoalPlannerDialog(
    repository: ApiFocusRepository,
    initialPlan: FocusGoalPlan?,
    onDismiss: () -> Unit,
    onPlanReady: (FocusGoalPlan) -> Unit,
) {
    val scope = rememberCoroutineScope()
    var input by rememberSaveable { mutableStateOf(initialPlan?.goal.orEmpty()) }
    var plan by remember { mutableStateOf(initialPlan) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    AlertDialog(
        onDismissRequest = { if (!loading) onDismiss() },
        title = { Text("设定本次学习目标") },
        text = {
            Column(Modifier.fillMaxWidth().heightIn(max = 560.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("先说清楚想达成什么，再把它变成今天可以完成的步骤。", color = Muted, fontSize = 12.sp)
                OutlinedTextField(value = input, onValueChange = { input = it.take(500); error = null; plan = null }, modifier = Modifier.fillMaxWidth(), label = { Text("学习目标") }, placeholder = { Text("例如：两周内掌握 Kotlin 协程并完成一个练习项目") }, minLines = 3, maxLines = 5, enabled = !loading)
                error?.let { Text(it, color = AlertErrorText, fontSize = 12.sp) }
                if (loading) Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) { CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp, color = FocusBlue); Text("AI 正在分析目标并拆解步骤…", color = FocusBlue, fontSize = 13.sp) }
                plan?.let { FocusGoalPlanPreview(it) }
            }
        },
        confirmButton = {
            if (plan != null) TextButton(onClick = { onPlanReady(plan!!) }, enabled = !loading) { Text("使用这份计划", color = FocusBlue) }
            else TextButton(onClick = {
                val goal = input.trim()
                if (goal.length < 4) error = "请先输入一个具体目标（至少 4 个字）"
                else { loading = true; scope.launch { repository.breakdownGoal(goal).onSuccess { plan = it }.onFailure { error = it.message ?: "目标分析失败，请稍后重试" }; loading = false } }
            }, enabled = !loading) { Text("分析并拆解", color = FocusBlue) }
        },
        dismissButton = { TextButton(onClick = onDismiss, enabled = !loading) { Text("取消") } },
    )
}

@Composable
private fun FocusGoalPlanPreview(plan: FocusGoalPlan) {
    Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
        Text("目标分析", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 14.sp)
        Surface(shape = RoundedCornerShape(14.dp), color = PrimarySoft) { Text(plan.analysis, modifier = Modifier.padding(12.dp), color = TextPrimary, fontSize = 12.sp, lineHeight = 18.sp) }
        Text("执行步骤（${plan.steps.size} 步）", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 14.sp)
        plan.steps.forEach { step ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(9.dp), verticalAlignment = Alignment.Top) {
                Surface(shape = CircleShape, color = FocusBlue.copy(alpha = .14f)) { Text(step.number.toString(), modifier = Modifier.padding(horizontal = 8.dp, vertical = 5.dp), color = FocusBlue, fontWeight = FontWeight.Bold, fontSize = 12.sp) }
                Column(Modifier.weight(1f)) { Text(step.title, color = TextPrimary, fontWeight = FontWeight.SemiBold, fontSize = 13.sp); Text("${step.estimatedMinutes} 分钟 · ${step.description}", color = Muted, fontSize = 11.sp, lineHeight = 16.sp) }
            }
        }
        plan.warnings.firstOrNull()?.let { Text("提示：$it", color = Muted, fontSize = 11.sp) }
    }
}

@Composable
private fun FocusDurationPicker(
    selectedMinutes: Int,
    enabled: Boolean,
    onSelectMinutes: (Int) -> Unit,
    onCustom: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("专注时间", color = TextPrimary, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(25, 45).forEach { minutes ->
                FilterChip(selected = selectedMinutes == minutes, onClick = { onSelectMinutes(minutes) }, enabled = enabled, label = { Text("$minutes 分钟") })
            }
            FilterChip(selected = selectedMinutes !in listOf(25, 45), onClick = onCustom, enabled = enabled, label = { Text(if (selectedMinutes !in listOf(25, 45)) "$selectedMinutes 分钟" else "自定义") })
        }
    }
}

@Composable
private fun FocusSessionModePicker(
    selected: FocusSessionMode,
    enabled: Boolean,
    onSelect: (FocusSessionMode) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("专注方式", color = TextPrimary, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
        FocusSessionMode.entries.forEach { option ->
            val selectedOption = option == selected
            Surface(
                onClick = { if (enabled) onSelect(option) },
                shape = RoundedCornerShape(16.dp),
                color = if (selectedOption) PrimarySoft else Background,
                border = if (selectedOption) BorderStroke(1.dp, FocusBlue) else null,
                enabled = enabled,
            ) {
                Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        when (option) {
                            FocusSessionMode.QUIET -> Icons.Default.Timer
                            FocusSessionMode.AI_COMPANION -> Icons.Default.SmartToy
                            FocusSessionMode.SMART_GUARD -> Icons.Default.Visibility
                        },
                        contentDescription = null,
                        tint = if (selectedOption) FocusBlue else Muted,
                    )
                    Spacer(Modifier.width(10.dp))
                    Column(Modifier.weight(1f)) {
                        Text(option.title, color = TextPrimary, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                        Text(option.description, color = Muted, fontSize = 11.sp)
                    }
                    if (selectedOption) Icon(Icons.Default.CheckCircle, contentDescription = null, tint = FocusBlue, modifier = Modifier.size(18.dp))
                }
            }
        }
    }
}

@Composable
private fun FocusHallHero(message: String, npcState: GuideNpcState, onTextComplete: () -> Unit = {}) {
    Surface(
        shape = RoundedCornerShape(28.dp),
        color = Color.Transparent,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(292.dp)
                .padding(18.dp),
        ) {
            Image(
                painter = painterResource(R.drawable.focus_hall_scene),
                contentDescription = "CampusMate AI 导员的学习空间",
                modifier = Modifier
                    .matchParentSize()
                    .clip(RoundedCornerShape(28.dp)),
                contentScale = ContentScale.Crop,
            )
            Text("✦", color = Color.White.copy(alpha = .82f), fontSize = 28.sp, modifier = Modifier.align(Alignment.TopEnd))
            Text("✦", color = FocusBlue.copy(alpha = .50f), fontSize = 18.sp, modifier = Modifier.align(Alignment.CenterStart))
            AnimatedContent(targetState = message, transitionSpec = { (fadeIn() + slideInVertically { it / 3 }) togetherWith (fadeOut() + slideOutVertically { -it / 4 }) }, label = "guide-bubble", modifier = Modifier.align(Alignment.TopStart).padding(end = 30.dp)) { currentMessage ->
                Surface(shape = RoundedCornerShape(18.dp), color = Color.White, border = BorderStroke(2.dp, FocusViolet.copy(alpha = .55f)), shadowElevation = 3.dp) { TypewriterBubble(currentMessage, onTextComplete) }
            }
            GuideSceneStatus(npcState, Modifier.align(Alignment.CenterEnd).padding(top = 34.dp, end = 2.dp))
            Text("FOCUS · LEARN · GROW", color = Color.White.copy(alpha = .82f), fontWeight = FontWeight.Bold, fontSize = 10.sp, modifier = Modifier.align(Alignment.BottomEnd).padding(6.dp))
        }
    }
}

/** A small live indicator sits beside the unchanged guide artwork. */
@Composable
private fun GuideSceneStatus(state: GuideNpcState, modifier: Modifier = Modifier) {
    when (state) {
        GuideNpcState.IDLE -> Unit
        GuideNpcState.LISTENING -> Surface(modifier = modifier, shape = RoundedCornerShape(16.dp), color = Color(0xFF192952).copy(alpha = .88f)) {
            Row(Modifier.padding(horizontal = 9.dp, vertical = 7.dp), horizontalArrangement = Arrangement.spacedBy(3.dp), verticalAlignment = Alignment.CenterVertically) {
                listOf(9.dp, 18.dp, 12.dp).forEach { height -> Box(Modifier.width(3.dp).height(height).background(Color(0xFF70E5F8), RoundedCornerShape(2.dp))) }
            }
        }
        GuideNpcState.THINKING -> Surface(modifier = modifier, shape = CircleShape, color = Color.White.copy(alpha = .92f), border = BorderStroke(1.dp, FocusViolet.copy(alpha = .55f))) {
            Text("…", modifier = Modifier.padding(horizontal = 10.dp, vertical = 2.dp), color = FocusViolet, fontWeight = FontWeight.Bold, fontSize = 20.sp)
        }
        GuideNpcState.HAPPY -> Text("✦", modifier = modifier, color = Color(0xFFFFD76A), fontSize = 30.sp)
    }
}

@Composable
private fun PixelCounselor(modifier: Modifier = Modifier, eyeScale: Float = 1f, state: GuideNpcState = GuideNpcState.IDLE) {
    Box(modifier = modifier.size(width = 190.dp, height = 172.dp), contentAlignment = Alignment.BottomCenter) {
        if (state == GuideNpcState.THINKING) Surface(modifier = Modifier.align(Alignment.TopEnd), shape = CircleShape, color = Color.White, border = BorderStroke(2.dp, FocusViolet.copy(alpha = .6f))) { Text("…", modifier = Modifier.padding(horizontal = 9.dp, vertical = 2.dp), color = FocusViolet, fontWeight = FontWeight.Bold) }
        if (state == GuideNpcState.LISTENING) Row(modifier = Modifier.align(Alignment.CenterEnd).padding(end = 4.dp), horizontalArrangement = Arrangement.spacedBy(3.dp), verticalAlignment = Alignment.CenterVertically) { listOf(10.dp, 22.dp, 14.dp).forEach { height -> Box(Modifier.width(3.dp).height(height).background(Color(0xFF70E5F8), RoundedCornerShape(2.dp))) } }
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.align(Alignment.BottomCenter)) {
            Box(contentAlignment = Alignment.Center) {
                Box(Modifier.offset(y = (-8).dp).size(14.dp).background(FocusViolet, CircleShape).border(2.dp, FocusBlue, CircleShape))
            Surface(
                modifier = Modifier.padding(top = 5.dp).size(width = 150.dp, height = 88.dp),
                shape = RoundedCornerShape(24.dp),
                color = Color.White,
                border = BorderStroke(4.dp, FocusViolet.copy(alpha = .7f)),
                shadowElevation = 5.dp,
            ) {
                Box(Modifier.padding(12.dp).clip(RoundedCornerShape(14.dp)).background(Color(0xFF26315B)), contentAlignment = Alignment.Center) {
                    Row(horizontalArrangement = Arrangement.spacedBy(26.dp), verticalAlignment = Alignment.CenterVertically) {
                        if (state == GuideNpcState.HAPPY) { Text("^", color = Color(0xFF70E5F8), fontWeight = FontWeight.Black, fontSize = 28.sp); Spacer(Modifier.width(20.dp)); Text("^", color = Color(0xFF70E5F8), fontWeight = FontWeight.Black, fontSize = 28.sp) } else { Box(Modifier.size(width = 10.dp, height = (20 * eyeScale).dp).background(Color(0xFF70E5F8), RoundedCornerShape(5.dp))); Box(Modifier.size(width = 10.dp, height = (20 * eyeScale).dp).background(Color(0xFF70E5F8), RoundedCornerShape(5.dp))) }
                    }
                }
            }
        }
        Row(modifier = Modifier.offset(y = (-8).dp), verticalAlignment = Alignment.CenterVertically) {
            Surface(shape = CircleShape, color = Color(0xFFE9E8FF), border = BorderStroke(2.dp, FocusViolet.copy(alpha = .45f))) { Box(Modifier.size(22.dp)) }
            Surface(
            modifier = Modifier.size(width = 106.dp, height = 48.dp),
            shape = RoundedCornerShape(topStart = 18.dp, topEnd = 18.dp, bottomStart = 10.dp, bottomEnd = 10.dp),
            color = Color(0xFFFCFCFF),
            border = BorderStroke(3.dp, FocusViolet.copy(alpha = .55f)),
        ) {
            Box(contentAlignment = Alignment.Center) {
                Surface(shape = CircleShape, color = FocusViolet.copy(alpha = .20f)) { Icon(Icons.Default.Bolt, null, tint = FocusViolet, modifier = Modifier.padding(6.dp).size(16.dp)) }
            }
            }
            Surface(shape = CircleShape, color = Color(0xFFE9E8FF), border = BorderStroke(2.dp, FocusViolet.copy(alpha = .45f))) { Box(Modifier.size(22.dp)) }
        }
        Row(modifier = Modifier.offset(y = (-15).dp), horizontalArrangement = Arrangement.spacedBy(40.dp)) { Box(Modifier.size(18.dp, 13.dp).background(FocusViolet, RoundedCornerShape(bottomStart = 5.dp, bottomEnd = 5.dp))); Box(Modifier.size(18.dp, 13.dp).background(FocusViolet, RoundedCornerShape(bottomStart = 5.dp, bottomEnd = 5.dp))) }
        }
    }
}

@Composable
private fun FocusHallAction(
    modifier: Modifier,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    subtitle: String,
    accent: Color,
    onClick: () -> Unit,
) {
    Surface(
        onClick = onClick,
        modifier = modifier,
        shape = RoundedCornerShape(20.dp),
        color = Surface,
        border = BorderStroke(1.dp, accent.copy(alpha = .16f)),
        shadowElevation = 2.dp,
    ) {
        Column(Modifier.padding(horizontal = 11.dp, vertical = 14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Surface(shape = CircleShape, color = accent.copy(alpha = .14f)) { Icon(icon, null, tint = accent, modifier = Modifier.padding(8.dp).size(20.dp)) }
            Text(title, color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 13.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(subtitle, color = Muted, fontSize = 10.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}

@Composable
private fun FocusHallDialogue(
    state: GuideDialogueState,
    arranging: Boolean,
    countdown: Int,
    selectedMinutes: Int,
    selectedMode: FocusSessionMode,
    onReady: () -> Unit,
    onPlan: () -> Unit,
    onOpenHistory: () -> Unit,
    onSelectMinutes: (Int) -> Unit,
    onCustom: () -> Unit,
    onSelectMode: (FocusSessionMode) -> Unit,
) {
    val message = when {
        arranging -> "好的！\n让我帮你安排一下。"
        state == GuideDialogueState.GREETING -> "你好呀！\n今天准备开始专注学习了吗？"
        state == GuideDialogueState.ASK_DURATION -> "你想专注多久？"
        state == GuideDialogueState.ASK_MODE -> "不错！\n接下来选择你的专注方式吧。"
        else -> "准备好了！"
    }
    val npcState = when {
        arranging -> GuideNpcState.THINKING
        state == GuideDialogueState.ASK_DURATION -> GuideNpcState.LISTENING
        state == GuideDialogueState.ASK_MODE -> GuideNpcState.THINKING
        state == GuideDialogueState.CONFIRM || state == GuideDialogueState.ENTER_SESSION -> GuideNpcState.HAPPY
        else -> GuideNpcState.IDLE
    }
    Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
        var typingComplete by remember(message) { mutableStateOf(false) }
        FocusHallHero(message, npcState) { typingComplete = true }
        if (typingComplete) when (state) {
            GuideDialogueState.GREETING -> if (!arranging) {
                HallDialogueChoice(Icons.Default.AutoAwesome, "设定目标并开始", "让 AI 分析并拆成可执行步骤", onPlan)
                HallDialogueChoice(Icons.Default.PlayArrow, "准备好了", "让我开始安排吧", onReady)
                HallDialogueChoice(Icons.Default.Assessment, "查看成长记录", "回顾我的专注", onOpenHistory)
            }
            GuideDialogueState.ASK_DURATION -> {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    listOf(25, 45, 60).forEach { minutes ->
                        OutlinedButton(onClick = { onSelectMinutes(minutes) }, modifier = Modifier.weight(1f), shape = RoundedCornerShape(16.dp)) { Text("$minutes 分钟") }
                    }
                }
                OutlinedButton(onClick = onCustom, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp)) { Text("自定义时长") }
            }
            GuideDialogueState.ASK_MODE -> FocusSessionMode.entries.forEach { option ->
                HallDialogueChoice(
                    icon = when (option) {
                        FocusSessionMode.QUIET -> Icons.Default.Timer
                        FocusSessionMode.AI_COMPANION -> Icons.Default.SmartToy
                        FocusSessionMode.SMART_GUARD -> Icons.Default.Visibility
                    },
                    title = option.title,
                    subtitle = option.description,
                    onClick = { onSelectMode(option) },
                    selected = option == selectedMode,
                )
            }
            GuideDialogueState.CONFIRM, GuideDialogueState.ENTER_SESSION -> Text(
                if (countdown > 0) countdown.toString() else "正在进入专注空间…",
                modifier = Modifier.fillMaxWidth(), color = FocusBlue, fontSize = 42.sp,
                fontWeight = FontWeight.ExtraBold, textAlign = androidx.compose.ui.text.style.TextAlign.Center,
            )
        }
    }
}

@Composable
private fun TypewriterBubble(message: String, onComplete: () -> Unit) {
    var shown by remember(message) { mutableStateOf("") }
    LaunchedEffect(message) {
        shown = ""
        message.forEach { character ->
            shown += character
            delay(65)
        }
        onComplete()
    }
    Text(shown, modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp), color = TextPrimary, fontWeight = FontWeight.SemiBold, fontSize = 16.sp, lineHeight = 23.sp)
}

@Composable
private fun HallDialogueChoice(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    subtitle: String,
    onClick: () -> Unit,
    selected: Boolean = false,
) {
    Surface(
        onClick = onClick,
        shape = RoundedCornerShape(20.dp),
        color = if (selected) PrimarySoft else Surface,
        border = BorderStroke(1.dp, if (selected) FocusBlue else Line),
    ) {
        Row(Modifier.fillMaxWidth().padding(15.dp), verticalAlignment = Alignment.CenterVertically) {
            Surface(shape = CircleShape, color = FocusBlue.copy(alpha = .13f)) { Icon(icon, null, tint = FocusBlue, modifier = Modifier.padding(9.dp).size(21.dp)) }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) { Text(title, color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 16.sp); Text(subtitle, color = Muted, fontSize = 12.sp) }
            Icon(Icons.Default.ChevronRight, null, tint = FocusViolet)
        }
    }
}

@Composable
fun FocusHistoryScreen(repository: ApiFocusRepository, onBack: () -> Unit) {
    val records by repository.records.collectAsStateWithLifecycle()
    LaunchedEffect(Unit) { repository.refresh() }
    LazyColumn(
        modifier = Modifier.fillMaxSize().background(FocusBg),
        contentPadding = PaddingValues(16.dp, 20.dp, 16.dp, 28.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, contentDescription = "返回", tint = TextPrimary) }
                Text("专注记录", color = TextPrimary, fontSize = 24.sp, fontWeight = FontWeight.ExtraBold)
            }
        }
        if (records.isEmpty()) item { Text("还没有专注记录，完成第一次专注后会显示在这里。", color = Muted, fontSize = 14.sp) }
        else items(records, key = { it.id }) { record ->
            Surface(shape = RoundedCornerShape(20.dp), color = Surface, border = BorderStroke(1.dp, Line)) {
                Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                    Surface(shape = CircleShape, color = PrimarySoft) { Icon(Icons.Default.Check, null, tint = FocusBlue, modifier = Modifier.padding(9.dp)) }
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) { Text("${FocusMode.byName(record.mode).label} · ${record.actualMinutes} 分钟", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 17.sp); Text(record.endedAt, color = Muted, fontSize = 13.sp) }
                    Text("已完成", color = FocusGreen, fontWeight = FontWeight.SemiBold)
                }
            }
        }
    }
}

@Composable
private fun FocusModeTabs(selected: FocusMode, enabled: Boolean, onSelect: (FocusMode) -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(PrimarySoft).padding(4.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        listOf(FocusMode.FOCUS, FocusMode.SHORT_BREAK, FocusMode.LONG_BREAK).forEach { item ->
            val active = item == selected
            Surface(onClick = { if (enabled) onSelect(item) }, modifier = Modifier.weight(1f), shape = RoundedCornerShape(18.dp), color = if (active) FocusBlue else Color.Transparent, enabled = enabled) { Row(Modifier.padding(vertical = 11.dp), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) { Icon(if (item == FocusMode.FOCUS) Icons.Default.Timer else Icons.Default.NightlightRound, null, modifier = Modifier.size(16.dp), tint = if (active) Color.White else Muted); Spacer(Modifier.width(4.dp)); Text("${item.label} ${item.minutes} 分钟", color = if (active) Color.White else TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.SemiBold) } }
        }
    }
}

@Composable
private fun FocusVoiceAssistantCard(
    state: FocusVoiceState,
    onEnable: () -> Unit,
    onInterrupt: () -> Unit,
) {
    val status = when (state.phase) {
        FocusVoicePhase.IDLE -> "未开启"
        FocusVoicePhase.CONNECTING -> "正在连接"
        FocusVoicePhase.LISTENING -> "正在聆听"
        FocusVoicePhase.THINKING -> "正在思考"
        FocusVoicePhase.SPEAKING -> "正在回答"
        FocusVoicePhase.RECONNECTING -> "正在重新连接"
        FocusVoicePhase.ERROR -> "连接失败"
    }
    Surface(shape = RoundedCornerShape(20.dp), color = Surface) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(shape = CircleShape, color = PrimarySoft) {
                    Icon(Icons.Default.SmartToy, null, Modifier.padding(9.dp), tint = FocusBlue)
                }
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text("CampusMate AI", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                    Text(status, color = Muted, fontSize = 12.sp)
                }
                if (state.phase == FocusVoicePhase.IDLE || state.phase == FocusVoicePhase.ERROR) {
                    Button(onClick = onEnable, shape = RoundedCornerShape(18.dp)) {
                        Icon(Icons.Default.Mic, null, modifier = Modifier.size(17.dp))
                        Spacer(Modifier.width(5.dp))
                        Text("开启陪伴", fontSize = 12.sp)
                    }
                } else {
                    StatusChip(Icons.Default.GraphicEq, "已连接")
                }
            }
            Text("开启后静默等待你自然开口；本页仅显示陪伴状态。", color = Muted, fontSize = 12.sp)
            state.errorMessage?.let { Text(it, color = AlertErrorText, fontSize = 12.sp) }
            if (state.phase == FocusVoicePhase.THINKING || state.phase == FocusVoicePhase.SPEAKING) {
                TextButton(onClick = onInterrupt, modifier = Modifier.align(Alignment.End)) { Text("打断回答", color = Muted) }
            }
        }
    }
}

@Composable
private fun AssistLine(icon: androidx.compose.ui.graphics.vector.ImageVector, text: String) { Row(verticalAlignment = Alignment.CenterVertically) { Icon(icon, null, tint = Muted, modifier = Modifier.size(17.dp)); Spacer(Modifier.width(10.dp)); Text(text, color = Muted, fontSize = 12.sp) } }

@Composable
private fun LearningStateMainCard(
    continuityState: LearningContinuityState,
    presence: PresenceSnapshot,
    expressionResult: ExpressionResult,
    expressionStatus: ExpressionServiceStatus,
    currentStudyMs: Long,
) {
    val presentation = if (presence.state == PresenceState.ABSENT) {
        BehaviorPresentation(
            title = "暂未检测到人在画面中",
            subtitle = "正在等待新的在场证据",
            icon = Icons.Default.PersonOff,
        )
    } else {
        behaviorPresentation(continuityState)
    }
    val background = when (continuityState) {
        LearningContinuityState.STUDYING -> PrimarySoft
        LearningContinuityState.PAUSED -> Background
        else -> Surface
    }
    Surface(shape = RoundedCornerShape(20.dp), color = background) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(shape = CircleShape, color = Surface) {
                    Icon(presentation.icon, null, Modifier.padding(8.dp), tint = FocusBlue)
                }
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(presentation.title, color = TextPrimary, fontSize = 20.sp, fontWeight = FontWeight.ExtraBold)
                    Text(presentation.subtitle, color = Muted, fontSize = 13.sp)
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                StatusChip(Icons.Default.SentimentSatisfied, formatExpressionChip(expressionResult))
                StatusChip(Icons.Default.Lock, "本机处理")
            }
            StatusChip(Icons.Default.Person, presenceLabel(presence.state))
            if (continuityState == LearningContinuityState.STUDYING && currentStudyMs >= 3_000L) {
                Text("已持续观察到学习行为 ${formatDuration(currentStudyMs)}", color = Muted, fontSize = 12.sp)
            }
            if (expressionStatus is ExpressionServiceStatus.Error) {
                Text("表情辅助暂不可用", color = Muted, fontSize = 11.sp)
            }
        }
    }
}

@Composable
private fun StatusChip(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String) {
    Surface(shape = RoundedCornerShape(50), color = Surface, border = BorderStroke(1.dp, Line)) {
        Row(Modifier.padding(horizontal = 9.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, null, tint = Muted, modifier = Modifier.size(14.dp))
            Spacer(Modifier.width(4.dp))
            Text(label, color = Muted, fontSize = 11.sp)
        }
    }
}

@Composable
private fun LearningRhythmCard(summary: BehaviorObservationSummary) {
    Surface(shape = RoundedCornerShape(18.dp), color = Background) {
        Column(Modifier.fillMaxWidth().padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(if (summary.sessionElapsedMs < 5 * 60 * 1_000L) "本次学习节奏" else "最近 5 分钟学习节奏", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 14.sp)
            if (summary.recentSegments.isEmpty()) {
                Box(Modifier.fillMaxWidth().height(10.dp).clip(RoundedCornerShape(20.dp)).background(Line))
            } else {
                Row(Modifier.fillMaxWidth().height(10.dp).clip(RoundedCornerShape(20.dp))) {
                    summary.recentSegments.forEach { segment ->
                        Box(Modifier.fillMaxHeight().weight(segment.durationMs.coerceAtLeast(1_000L).toFloat()).background(rhythmColor(segment.state)))
                    }
                }
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("学习行为 ${formatDuration(summary.recentStudyMs)}", color = Muted, fontSize = 12.sp)
                Text("暂时停顿 ${formatDuration(summary.recentPausedMs)}", color = Muted, fontSize = 12.sp)
            }
        }
    }
}

@Composable
private fun ObservationSummaryCard(focusElapsedSeconds: Int, summary: BehaviorObservationSummary) {
    Surface(shape = RoundedCornerShape(18.dp), color = Surface) {
        Column(Modifier.fillMaxWidth().padding(14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("本次观察摘要", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 14.sp)
            Row(Modifier.fillMaxWidth()) {
                ObservationMetric(Modifier.weight(1f), formatDuration(focusElapsedSeconds * 1_000L), "专注时长")
                ObservationMetric(Modifier.weight(1f), formatDuration(summary.totalStudyMs), "学习行为")
            }
            Row(Modifier.fillMaxWidth()) {
                ObservationMetric(Modifier.weight(1f), formatDuration(summary.longestContinuousStudyMs), "最长连续学习")
                ObservationMetric(Modifier.weight(1f), formatDuration(summary.totalPausedMs), "暂时停顿")
            }
            Text("状态切换 ${summary.meaningfulSwitchCount} 次", color = Muted, fontSize = 11.sp, modifier = Modifier.align(Alignment.End))
        }
    }
}

@Composable
private fun ObservationMetric(modifier: Modifier, value: String, label: String) {
    Column(modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, color = TextPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold)
        Text(label, color = Muted, fontSize = 11.sp)
    }
}

@Composable
private fun DeveloperTools(
    expanded: Boolean,
    onExpandedChange: (Boolean) -> Unit,
    selectedLabel: BehaviorDatasetLabel,
    onLabelSelected: (BehaviorDatasetLabel) -> Unit,
    captureState: BehaviorDatasetCaptureState,
    presence: PresenceSnapshot,
    personDetection: PersonDetectionSnapshot,
    personInferenceIntervalMs: Long,
    onStart: () -> Unit,
    onStop: () -> Unit,
    localVisualTestActive: Boolean,
    onStartLocalVisualTest: () -> Unit,
    onStopLocalVisualTest: () -> Unit,
) {
    Surface(modifier = Modifier.fillMaxWidth().clickable { onExpandedChange(!expanded) }, shape = RoundedCornerShape(14.dp), color = Background) {
        Column(Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Build, null, tint = Muted, modifier = Modifier.size(16.dp))
                Spacer(Modifier.width(7.dp))
                Text("开发者工具", color = Muted, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.weight(1f))
                Icon(if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore, null, tint = Muted, modifier = Modifier.size(18.dp))
            }
            if (expanded) {
                Spacer(Modifier.height(10.dp))
                DebugLocalVisualTestControls(
                    active = localVisualTestActive,
                    onStart = onStartLocalVisualTest,
                    onStop = onStopLocalVisualTest,
                )
                Spacer(Modifier.height(8.dp))
                DebugBehaviorDatasetControls(selectedLabel, onLabelSelected, captureState, presence, personDetection, personInferenceIntervalMs, onStart, onStop)
            }
        }
    }
}

@Composable
private fun DebugLocalVisualTestControls(
    active: Boolean,
    onStart: () -> Unit,
    onStop: () -> Unit,
) {
    Surface(shape = RoundedCornerShape(14.dp), color = PrimarySoft) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
            Text("本地视觉测试", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 13.sp)
            Text("仅 Debug：不连接后端，不创建或写入专注记录。", color = Muted, fontSize = 11.sp)
            if (active) {
                Text("Debug 本地视觉测试运行中", color = FocusBlue, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
                OutlinedButton(onClick = onStop, shape = RoundedCornerShape(12.dp)) {
                    Text("结束本地测试", color = FocusOrange, fontWeight = FontWeight.Bold)
                }
            } else {
                Button(onClick = onStart, shape = RoundedCornerShape(12.dp), colors = ButtonDefaults.buttonColors(containerColor = FocusBlue)) {
                    Text("开始本地视觉测试", fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
private fun DebugBehaviorDatasetControls(
    selectedLabel: BehaviorDatasetLabel,
    onLabelSelected: (BehaviorDatasetLabel) -> Unit,
    captureState: BehaviorDatasetCaptureState,
    presence: PresenceSnapshot,
    personDetection: PersonDetectionSnapshot,
    personInferenceIntervalMs: Long,
    onStart: () -> Unit,
    onStop: () -> Unit,
) {
    Surface(shape = RoundedCornerShape(14.dp), color = PrimarySoft) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Debug · 目标域数据采集", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 13.sp)
            Text("行为模型：V3.2-A / campusmate_visible_study_v32", color = Muted, fontSize = 11.sp)
            Text(
                "Presence: ${presence.state} · evidence ${presence.lastPresenceEvidenceAgoMs(System.currentTimeMillis())?.let(::formatDuration) ?: "无"}前 · face=${presence.faceDetected} · behavior=${presence.behaviorEvidence}",
                color = Muted,
                fontSize = 11.sp,
            )
            Text(
                "Person detector: ${personDetection.status} · detected=${personDetection.personDetected} · confidence=${personDetection.personConfidence?.let { "%.2f".format(it) } ?: "-"} · recent=${presence.recentPersonEvidence} · ${personInferenceIntervalMs}ms",
                color = Muted,
                fontSize = 11.sp,
            )
            personDetection.errorCategory?.let { category ->
                Text(
                    "Person error: $category · ${personDetection.error.orEmpty()}",
                    color = Muted,
                    fontSize = 11.sp,
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                BehaviorDatasetLabel.entries.forEach { label ->
                    FilterChip(
                        selected = selectedLabel == label,
                        onClick = { onLabelSelected(label) },
                        enabled = !captureState.isRunning,
                        label = { Text(label.displayName, fontSize = 12.sp) },
                    )
                }
            }
            val status = when {
                captureState.preparing -> "准备中 ${captureState.preparationSecondsRemaining} · ${captureState.label?.directoryName} · ${captureState.sessionId}"
                captureState.active -> {
                "采集中：${captureState.label?.directoryName} · ${captureState.sessionId} · ${captureState.capturedCount}/120"
                }
                captureState.sessionId != null -> {
                "已停止：${captureState.label?.displayName} · ${captureState.sessionId} · ${captureState.capturedCount} 张"
                }
                else -> {
                "选择标签后开始采集（约 1 张/秒）"
                }
            }
            Text(status, color = Muted, fontSize = 11.sp)
            if (captureState.isRunning) {
                OutlinedButton(onClick = onStop, shape = RoundedCornerShape(12.dp)) {
                    Text("停止采集", color = FocusOrange, fontWeight = FontWeight.Bold)
                }
            } else {
                Button(onClick = onStart, shape = RoundedCornerShape(12.dp), colors = ButtonDefaults.buttonColors(containerColor = FocusBlue)) {
                    Text("开始采集", fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
private fun FocusStat(modifier: Modifier, icon: androidx.compose.ui.graphics.vector.ImageVector, value: String, unit: String, label: String, background: Color) { Column(modifier.clip(RoundedCornerShape(20.dp)).background(background).padding(vertical = 13.dp), horizontalAlignment = Alignment.CenterHorizontally) { Icon(icon, null, tint = if (icon == Icons.Default.LocalFireDepartment) FocusOrange else FocusBlue, modifier = Modifier.size(25.dp)); Spacer(Modifier.height(6.dp)); Row(verticalAlignment = Alignment.Bottom) { Text(value, color = TextPrimary, fontSize = 26.sp, fontWeight = FontWeight.ExtraBold); Spacer(Modifier.width(2.dp)); Text(unit, color = Muted, fontSize = 10.sp) }; Text(label, color = Muted, fontSize = 11.sp) } }

private fun statusLabel(status: ExpressionServiceStatus) = when (status) {
    ExpressionServiceStatus.Off -> "未加载"
    ExpressionServiceStatus.Initializing -> "模型加载中"
    ExpressionServiceStatus.Ready -> "模型已就绪"
    ExpressionServiceStatus.Running -> "本机分析中"
    ExpressionServiceStatus.Paused -> "已暂停"
    ExpressionServiceStatus.NoFace -> "等待画面"
    ExpressionServiceStatus.LowConfidence -> "结果暂不稳定"
    is ExpressionServiceStatus.Error -> "不可用：${status.message}"
}

private fun formatCurrentExpression(result: ExpressionResult): String {
    if (result.label in setOf(ExpressionLabel.UNKNOWN, ExpressionLabel.NO_FACE)) {
        return "正在观察..."
    }
    return when (result.label) {
        ExpressionLabel.HAPPY -> "愉快"
        ExpressionLabel.NEUTRAL -> "平静"
        ExpressionLabel.SAD -> "低落"
        ExpressionLabel.ANGRY -> "不悦"
        ExpressionLabel.FEAR -> "紧张"
        ExpressionLabel.SURPRISE -> "惊讶"
        ExpressionLabel.DISGUST -> "厌恶"
        ExpressionLabel.UNKNOWN, ExpressionLabel.NO_FACE -> "正在观察..."
    }
}

private data class BehaviorPresentation(
    val title: String,
    val subtitle: String,
    val icon: androidx.compose.ui.graphics.vector.ImageVector,
)

private fun behaviorPresentation(state: LearningContinuityState): BehaviorPresentation = when (state) {
    LearningContinuityState.OBSERVING -> BehaviorPresentation(
        title = "正在观察",
        subtitle = "正在了解你当前的学习状态",
        icon = Icons.Default.Visibility,
    )
    LearningContinuityState.STUDYING -> BehaviorPresentation(
            title = "学习进行中",
            subtitle = "已检测到明确学习行为",
            icon = Icons.Default.MenuBook,
    )
    LearningContinuityState.THINKING_OR_ADJUSTING -> BehaviorPresentation(
        title = "短暂思考或调整中",
        subtitle = "暂未观察到明确学习行为",
        icon = Icons.Default.Psychology,
    )
    LearningContinuityState.PAUSED -> BehaviorPresentation(
            title = "暂时停顿",
            subtitle = "暂未检测到明确学习行为\n可能正在思考或短暂调整",
            icon = Icons.Default.PauseCircleOutline,
    )
}

private fun formatExpressionChip(result: ExpressionResult): String {
    if (!result.isStable || result.label in setOf(ExpressionLabel.UNKNOWN, ExpressionLabel.NO_FACE)) {
        return "表情观察中"
    }
    return formatCurrentExpression(result)
}

private fun presenceLabel(state: PresenceState): String = when (state) {
    PresenceState.PRESENT -> "人在画面中"
    PresenceState.OBSERVING -> "正在确认是否在场"
    PresenceState.ABSENT -> "暂未检测到人在画面中"
}

@Composable
private fun rhythmColor(state: LearningContinuityState): Color = when (state) {
    LearningContinuityState.STUDYING -> FocusBlue
    LearningContinuityState.THINKING_OR_ADJUSTING -> PrimarySoft
    LearningContinuityState.PAUSED -> Line
    LearningContinuityState.OBSERVING -> Muted.copy(alpha = 0.45f)
}

private fun formatDuration(durationMs: Long): String {
    val totalSeconds = (durationMs.coerceAtLeast(0L) / 1_000L).toInt()
    val minutes = totalSeconds / 60
    val seconds = totalSeconds % 60
    return if (minutes > 0) "${minutes}分${seconds}秒" else "${seconds}秒"
}

private fun formatBehavior(state: BehaviorDisplayState): String = when (state) {
    BehaviorDisplayState.Observing -> "正在观察..."
    BehaviorDisplayState.NoStableBehavior -> "正在持续观察..."
    is BehaviorDisplayState.Stable -> {
        val label = when (state.behavior) {
            StudyBehavior.VISIBLE_STUDY -> "检测到学习行为"
            StudyBehavior.IDLE -> "暂未检测到明确学习行为"
            // Only used if CURRENT_BEHAVIOR_MODEL is switched back to V2.
            StudyBehavior.READING -> "正在阅读"
            StudyBehavior.WRITING -> "正在书写"
            StudyBehavior.PHONE_USE -> "正在使用手机"
            else -> "正在持续观察..."
        }
        label
    }
}

/** Serializes only user-approved, structured local-assistance summaries for the counselor flow. */
internal fun FocusSessionSummary.toCounselorPrompt(): String = buildString {
    append("请仅根据以下由用户主动发送的本次专注辅助观察摘要，给出温和、可执行的学习安排建议。")
    append("这不是心理诊断依据；不要推断焦虑、疲劳、疾病或确定的走神，也不要把辅助观察描述为事实。\n")
    append("实际专注分钟数：$actualFocusMinutes\n")
    append("可能暂时离开事件次数：$noFaceEventCount\n")
    append("可能注意力偏离累计秒数：$possibleDistractionDurationSeconds\n")
    append("建议休息次数：$breakSuggestionCount\n")
    append("稳定表情分布：${stableExpressionDistribution.ifEmpty { mapOf("无稳定结果" to 0) }}\n")
    append("模型版本：$modelVersion\n")
    append("请明确说明：以上仅为本机辅助观察摘要，不包含、也未发送任何照片、视频或逐帧结果。")
}

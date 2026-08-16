package com.example.campusai.ui.screens.focus

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.view.PreviewView
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import androidx.compose.ui.layout.ContentScale
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
import com.example.campusai.R
import com.example.campusai.BuildConfig
import com.example.campusai.data.behavior.BehaviorDatasetCaptureState
import com.example.campusai.data.behavior.BehaviorDatasetLabel
import com.example.campusai.data.behavior.BehaviorDisplayState
import com.example.campusai.data.behavior.BehaviorInputDebugExporter
import com.example.campusai.data.behavior.BehaviorObservationSummary
import com.example.campusai.data.behavior.LearningContinuityState
import com.example.campusai.data.behavior.StudyBehavior
import com.example.campusai.data.expression.ExpressionServiceStatus
import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.ExpressionResult
import com.example.campusai.data.model.FocusMode
import com.example.campusai.data.model.FocusSessionSummary
import com.example.campusai.data.repository.ApiFocusRepository
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private val FocusBlue: Color @Composable get() = Primary
private val FocusViolet: Color @Composable get() = PrimaryHover
private val FocusOrange: Color @Composable get() = Accent
private val FocusGreen: Color @Composable get() = Success
private val FocusBg: Color @Composable get() = Background

/** A backend-session-first focus timer. The device never creates a local focus record. */
@Composable
fun FocusScreen(
    repository: ApiFocusRepository,
    appRepository: AppRepository,
    reduceMotion: Boolean,
    onBack: () -> Unit,
    relatedTaskId: String? = null,
    onOpenCounselorPlan: (String) -> Unit,
) {
    val stats by repository.stats.collectAsState()
    val records by repository.records.collectAsState()
    val activeSession by repository.activeSession.collectAsState()
    val remoteError by repository.error.collectAsState()
    val backendOnline by appRepository.backendOnline.collectAsState()
    val assistanceEnabled by appRepository.learningAssistanceEnabled.collectAsState()
    val scope = rememberCoroutineScope()
    val manager = appRepository.expressionSessionManager
    val expressionStatus by manager.status.collectAsState()
    val expressionResult by manager.result.collectAsState()
    val behaviorDisplayState by manager.behaviorDisplayState.collectAsState()
    val behaviorObservation by manager.behaviorObservation.collectAsState()
    val learningContinuityState by manager.learningContinuityState.collectAsState()
    val datasetCaptureState by BehaviorInputDebugExporter.datasetCaptureState.collectAsState()
    val gentleReminder by manager.gentleReminder.collectAsState()
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    var cameraPermissionGranted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED,
        )
    }
    var permissionDenied by remember { mutableStateOf(false) }
    var appForeground by remember { mutableStateOf(true) }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        cameraPermissionGranted = granted
        permissionDenied = !granted
    }
    var mode by remember { mutableStateOf(FocusMode.FOCUS) }
    var secondsLeft by remember { mutableIntStateOf(FocusMode.FOCUS.totalSeconds) }
    var showFinishDialog by remember { mutableStateOf(false) }
    var showGoalDialog by remember { mutableStateOf(false) }
    var showCompletedDialog by remember { mutableStateOf(false) }
    var previewExpanded by remember { mutableStateOf(false) }
    var developerToolsExpanded by rememberSaveable { mutableStateOf(false) }
    var datasetLabel by remember { mutableStateOf(BehaviorDatasetLabel.IDLE) }
    var selectedGoal by remember(stats.goalMinutes) { mutableIntStateOf(stats.goalMinutes) }

    LaunchedEffect(backendOnline) {
        if (backendOnline) repository.refresh()
    }
    LaunchedEffect(activeSession?.id, activeSession?.status) {
        activeSession?.let { session ->
            mode = session.mode
            if (secondsLeft == FocusMode.FOCUS.totalSeconds || secondsLeft > mode.totalSeconds) secondsLeft = mode.totalSeconds
        }
    }
    val running = activeSession?.status == "active"
    val paused = activeSession?.status == "paused"
    val analyzing = running && mode == FocusMode.FOCUS
    LaunchedEffect(running, activeSession?.id) {
        while (running && secondsLeft > 0) {
            delay(1000)
            secondsLeft--
            if (secondsLeft == 0) {
                repository.finish().onSuccess { showCompletedDialog = true; secondsLeft = mode.totalSeconds }
            }
        }
    }
    LaunchedEffect(assistanceEnabled, cameraPermissionGranted, analyzing, appForeground) {
        manager.updateEligibility(
            enabled = assistanceEnabled,
            permissionGranted = cameraPermissionGranted,
            running = analyzing,
            visible = true,
            foreground = appForeground,
        )
    }
    LaunchedEffect(assistanceEnabled) {
        if (!assistanceEnabled) previewExpanded = false
    }
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> appForeground = true
                Lifecycle.Event.ON_STOP -> appForeground = false
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            manager.detachPreviewAsync()
        }
    }
    val minutes = (secondsLeft / 60).toString().padStart(2, '0')
    val seconds = (secondsLeft % 60).toString().padStart(2, '0')
    val ringProgress = secondsLeft.toFloat() / mode.totalSeconds
    val observationNowMs = remember(secondsLeft, behaviorObservation) { System.currentTimeMillis() }
    val observationSummary = remember(behaviorObservation, observationNowMs) {
        behaviorObservation.summary(observationNowMs)
    }
    val focusElapsedSeconds = (mode.totalSeconds - secondsLeft).coerceAtLeast(0)
    val bottomContentPadding = BottomDockReservedHeight + WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + 26.dp

    LazyColumn(
        modifier = Modifier.fillMaxSize().background(FocusBg),
        contentPadding = PaddingValues(start = 16.dp, top = 20.dp, end = 16.dp, bottom = bottomContentPadding),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        (if (!backendOnline && remoteError == null) "专注自习需要连接真实后端后才能使用" else remoteError)?.let { message ->
            item { Surface(color = AlertErrorBg, shape = RoundedCornerShape(16.dp)) { Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) { Icon(Icons.Default.CloudOff, null, tint = AlertErrorText); Spacer(Modifier.width(8.dp)); Text(message, Modifier.weight(1f), color = AlertErrorText, fontSize = 12.sp); TextButton(onClick = { scope.launch { appRepository.refreshBackendStatus(); if (appRepository.backendOnline.value) repository.refresh() } }) { Text("重试", color = FocusBlue) } } } }
        }
        item {
            Column(Modifier.clip(RoundedCornerShape(28.dp)).background(Surface).padding(14.dp)) {
                FocusModeTabs(selected = mode, enabled = activeSession == null, onSelect = { chosen -> mode = chosen; secondsLeft = chosen.totalSeconds })
                Spacer(Modifier.height(22.dp))
                Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                    Box(contentAlignment = Alignment.Center, modifier = Modifier.size(258.dp)) {
                        CircularProgressIndicator(progress = { ringProgress }, modifier = Modifier.fillMaxSize(), color = FocusBlue, trackColor = PrimarySoft, strokeWidth = 12.dp)
                        CircularProgressIndicator(progress = { .82f }, modifier = Modifier.size(224.dp), color = Line, trackColor = Color.Transparent, strokeWidth = 2.dp)
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("$minutes:$seconds", color = TextPrimary, fontWeight = FontWeight.ExtraBold, fontSize = 55.sp)
                            Spacer(Modifier.height(9.dp))
                            Text(if (running) "正在专注" else if (paused) "已暂停" else "✦ 准备开始 ✦", color = Muted, fontSize = 16.sp)
                        }
                    }
                }
                Spacer(Modifier.height(22.dp))
                Button(
                    onClick = {
                        scope.launch {
                            when (activeSession?.status) {
                                null -> {
                                    val startResult = repository.start(mode, null, relatedTaskId)
                                    if (startResult.isSuccess) {
                                        secondsLeft = mode.totalSeconds
                                        manager.beginFocusSession()
                                    }
                                }
                                "active" -> repository.pause()
                                "paused" -> repository.resume()
                            }
                        }
                    },
                    modifier = Modifier.align(Alignment.CenterHorizontally).height(56.dp),
                    shape = RoundedCornerShape(28.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = FocusBlue),
                ) { Icon(if (running) Icons.Default.Pause else Icons.Default.PlayArrow, null); Spacer(Modifier.width(8.dp)); Text(if (running) "暂停" else if (paused) "继续" else "开始", fontWeight = FontWeight.Bold, fontSize = 19.sp) }
                if (activeSession != null) TextButton(onClick = { showFinishDialog = true }, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("结束本次${mode.label}", color = Muted) }
            }
        }
        item {
            Surface(shape = RoundedCornerShape(25.dp), color = Surface) {
                Column(Modifier.padding(18.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Surface(shape = CircleShape, color = PrimarySoft) { Icon(Icons.Default.SmartToy, null, Modifier.padding(9.dp), tint = FocusBlue) }
                        Spacer(Modifier.width(10.dp))
                        Column(Modifier.weight(1f)) { Text("学习状态辅助", color = TextPrimary, fontWeight = FontWeight.ExtraBold, fontSize = 18.sp); Text("画面仅在本机处理，不保存，不上传", color = Muted, fontSize = 12.sp) }
                        Switch(checked = assistanceEnabled, onCheckedChange = { enabled ->
                            scope.launch { appRepository.setLearningAssistanceEnabled(enabled) }
                            if (enabled && !cameraPermissionGranted) {
                                permissionLauncher.launch(Manifest.permission.CAMERA)
                            }
                        })
                    }
                    Spacer(Modifier.height(14.dp))
                    if (assistanceEnabled && cameraPermissionGranted) {
                        if (previewExpanded) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                IconButton(onClick = { previewExpanded = false }) {
                                    Icon(Icons.Default.ArrowBack, contentDescription = "收起观察画面", tint = FocusBlue)
                                }
                                Text("调整观察画面", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                            }
                            Spacer(Modifier.height(6.dp))
                        }
                        Box(
                            modifier = Modifier
                                .fillMaxWidth(if (previewExpanded) 1f else .78f)
                                .align(Alignment.CenterHorizontally)
                                .aspectRatio(4f / 5f)
                                .clip(RoundedCornerShape(14.dp)),
                            contentAlignment = Alignment.TopEnd,
                        ) {
                            key("focus-camera-preview") {
                                AndroidView(
                                    factory = { viewContext ->
                                        PreviewView(viewContext).apply {
                                            scaleType = PreviewView.ScaleType.FILL_CENTER
                                            implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                                            setOnClickListener { previewExpanded = !previewExpanded }
                                            manager.attachPreview(lifecycleOwner, this)
                                        }
                                    },
                                    update = { view ->
                                        view.setOnClickListener { previewExpanded = !previewExpanded }
                                    },
                                    modifier = Modifier.fillMaxSize(),
                                )
                            }
                            Surface(
                                onClick = { previewExpanded = !previewExpanded },
                                modifier = Modifier.padding(8.dp),
                                shape = CircleShape,
                                color = Color.Black.copy(alpha = .42f),
                            ) {
                                Icon(
                                    imageVector = if (previewExpanded) Icons.Default.FullscreenExit else Icons.Default.Fullscreen,
                                    contentDescription = if (previewExpanded) "收起观察画面" else "放大调整画面",
                                    modifier = Modifier.padding(8.dp).size(18.dp),
                                    tint = Color.White,
                                )
                            }
                        }
                        Spacer(Modifier.height(8.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.Center,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Icon(Icons.Default.TipsAndUpdates, contentDescription = null, tint = Muted, modifier = Modifier.size(14.dp))
                            Spacer(Modifier.width(5.dp))
                            Text("请保持头部、上半身和双手在画面内", color = Muted, fontSize = 11.sp)
                        }
                        if (previewExpanded) {
                            Spacer(Modifier.height(12.dp))
                            OutlinedButton(
                                onClick = { previewExpanded = false },
                                modifier = Modifier.align(Alignment.CenterHorizontally),
                                shape = RoundedCornerShape(14.dp),
                            ) {
                                Text("完成调整", color = FocusBlue, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                    Spacer(Modifier.height(16.dp))
                    LearningStateMainCard(
                        continuityState = learningContinuityState,
                        expressionResult = expressionResult,
                        expressionStatus = expressionStatus,
                        currentStudyMs = observationSummary.currentContinuousStudyMs,
                    )
                    Spacer(Modifier.height(14.dp))
                    LearningRhythmCard(observationSummary)
                    Spacer(Modifier.height(14.dp))
                    ObservationSummaryCard(
                        focusElapsedSeconds = focusElapsedSeconds,
                        summary = observationSummary,
                    )
                    if (BuildConfig.DEBUG) {
                        Spacer(Modifier.height(12.dp))
                        DeveloperTools(
                            expanded = developerToolsExpanded,
                            onExpandedChange = { developerToolsExpanded = it },
                            selectedLabel = datasetLabel,
                            onLabelSelected = { datasetLabel = it },
                            captureState = datasetCaptureState,
                            onStart = { BehaviorInputDebugExporter.startDatasetSession(context, datasetLabel) },
                            onStop = { BehaviorInputDebugExporter.stopDatasetSession() },
                        )
                    }
                    if (permissionDenied) {
                        Spacer(Modifier.height(10.dp))
                        AssistLine(Icons.Default.Lock, "未授予相机权限，学习状态辅助未启动")
                    }
                    gentleReminder?.let {
                        Spacer(Modifier.height(8.dp))
                        AssistLine(Icons.Default.Notifications, it)
                    }
                }
            }
        }
        item { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) { FocusStat(Modifier.weight(1f), Icons.Default.Timer, stats.todayMinutes.toString(), "分钟", "今日专注", PrimarySoft); FocusStat(Modifier.weight(1f), Icons.Default.MilitaryTech, stats.todayCount.toString(), "次", "完成次数", Surface); FocusStat(Modifier.weight(1f), Icons.Default.LocalFireDepartment, stats.streakDays.toString(), "天", "连续天数", Accent.copy(alpha = .14f)) } }
        item {
            Surface(shape = RoundedCornerShape(26.dp), color = Surface) {
                Row(Modifier.fillMaxWidth().heightIn(min = 164.dp).padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("自习目标", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                        Spacer(Modifier.height(8.dp))
                        Text("每日 ${stats.goalMinutes} 分钟", color = TextPrimary, fontWeight = FontWeight.ExtraBold, fontSize = 22.sp)
                        Text("设定目标，保持专注，见证成长", color = Muted, fontSize = 12.sp)
                        Spacer(Modifier.height(13.dp))
                        OutlinedButton(onClick = { selectedGoal = stats.goalMinutes; showGoalDialog = true }, shape = RoundedCornerShape(14.dp)) { Text("设定目标", color = FocusBlue, fontWeight = FontWeight.Bold) }
                    }
                    androidx.compose.foundation.Image(painter = painterResource(R.drawable.focus_goal_illustration), contentDescription = "学习目标插画", modifier = Modifier.size(142.dp), contentScale = ContentScale.Fit)
                }
            }
        }
        item { Text("最近记录", color = TextPrimary, fontWeight = FontWeight.ExtraBold, fontSize = 19.sp) }
        if (records.isEmpty()) item { Text("完成一次专注后，记录会从后端同步到这里。", color = Muted, fontSize = 13.sp, modifier = Modifier.padding(bottom = 12.dp)) }
        else items(records.take(8), key = { it.id }) { record ->
            Surface(shape = RoundedCornerShape(18.dp), color = Surface) { Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) { Icon(Icons.Default.CheckCircle, null, tint = FocusBlue); Spacer(Modifier.width(11.dp)); Column(Modifier.weight(1f)) { Text("${FocusMode.byName(record.mode).label} · ${record.actualMinutes} 分钟", color = TextPrimary, fontWeight = FontWeight.SemiBold); Text(record.endedAt, color = Muted, fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis) }; Text("已完成", color = FocusGreen, fontSize = 12.sp) } }
        }
    }
    if (showFinishDialog) AlertDialog(onDismissRequest = { showFinishDialog = false }, title = { Text("结束本次专注？") }, text = { Text("结束时间和时长由后端服务记录。", color = Muted) }, confirmButton = { TextButton(onClick = { scope.launch { repository.finish().onSuccess { showCompletedDialog = true; secondsLeft = mode.totalSeconds }; showFinishDialog = false } }) { Text("结束", color = FocusOrange) } }, dismissButton = { TextButton(onClick = { showFinishDialog = false }) { Text("继续专注") } })
    if (showGoalDialog) AlertDialog(onDismissRequest = { showGoalDialog = false }, title = { Text("设置每日自习目标") }, text = { Column { Text("目标将保存到后端数据库，并在不同设备间同步。", color = Muted, fontSize = 12.sp); Spacer(Modifier.height(12.dp)); Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { listOf(30, 60, 90, 120).forEach { goal -> FilterChip(selected = selectedGoal == goal, onClick = { selectedGoal = goal }, label = { Text("$goal 分钟") }) } } } }, confirmButton = { TextButton(onClick = { scope.launch { repository.updateGoal(selectedGoal).onSuccess { showGoalDialog = false } } }) { Text("保存", color = FocusBlue) } }, dismissButton = { TextButton(onClick = { showGoalDialog = false }) { Text("取消") } })
    if (showCompletedDialog) AlertDialog(onDismissRequest = { showCompletedDialog = false }, icon = { Icon(Icons.Default.Celebration, null, tint = FocusOrange) }, title = { Text("本次专注已完成！") }, text = { Text("记录已保存到后端数据库。", color = Muted) }, confirmButton = { TextButton(onClick = { showCompletedDialog = false }) { Text("知道了", color = FocusBlue) } })
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
private fun AssistLine(icon: androidx.compose.ui.graphics.vector.ImageVector, text: String) { Row(verticalAlignment = Alignment.CenterVertically) { Icon(icon, null, tint = Muted, modifier = Modifier.size(17.dp)); Spacer(Modifier.width(10.dp)); Text(text, color = Muted, fontSize = 12.sp) } }

@Composable
private fun LearningStateMainCard(
    continuityState: LearningContinuityState,
    expressionResult: ExpressionResult,
    expressionStatus: ExpressionServiceStatus,
    currentStudyMs: Long,
) {
    val presentation = behaviorPresentation(continuityState)
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
    onStart: () -> Unit,
    onStop: () -> Unit,
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
                DebugBehaviorDatasetControls(selectedLabel, onLabelSelected, captureState, onStart, onStop)
            }
        }
    }
}

@Composable
private fun DebugBehaviorDatasetControls(
    selectedLabel: BehaviorDatasetLabel,
    onLabelSelected: (BehaviorDatasetLabel) -> Unit,
    captureState: BehaviorDatasetCaptureState,
    onStart: () -> Unit,
    onStop: () -> Unit,
) {
    Surface(shape = RoundedCornerShape(14.dp), color = PrimarySoft) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Debug · 目标域数据采集", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 13.sp)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                BehaviorDatasetLabel.entries.forEach { label ->
                    FilterChip(
                        selected = selectedLabel == label,
                        onClick = { onLabelSelected(label) },
                        enabled = !captureState.active,
                        label = { Text(label.displayName, fontSize = 12.sp) },
                    )
                }
            }
            val status = if (captureState.active) {
                "采集中：${captureState.label?.displayName} · ${captureState.sessionId} · ${captureState.capturedCount}/180"
            } else if (captureState.sessionId != null) {
                "已停止：${captureState.label?.displayName} · ${captureState.sessionId} · ${captureState.capturedCount} 张"
            } else {
                "选择标签后开始采集（约 1 张/秒）"
            }
            Text(status, color = Muted, fontSize = 11.sp)
            if (captureState.active) {
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

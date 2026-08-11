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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.example.campusai.R
import com.example.campusai.data.expression.ExpressionServiceStatus
import com.example.campusai.data.focus.FocusState
import com.example.campusai.data.model.FocusMode
import com.example.campusai.data.model.FocusSessionSummary
import com.example.campusai.data.repository.ApiFocusRepository
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private val FocusBlue = Color(0xFF5264F5)
private val FocusViolet = Color(0xFF8959F5)
private val FocusOrange = Color(0xFFFF7959)
private val FocusGreen = Color(0xFF24B16A)
private val FocusBg = Color(0xFFF5F6FF)

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
    val assistanceEnabled by appRepository.learningAssistanceEnabled.collectAsState()
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()
    val manager = appRepository.expressionSessionManager

    // ── Manager state ──
    val managerStatus by manager.status.collectAsState()
    val managerResult by manager.result.collectAsState()
    val managerFocusState by manager.focusState.collectAsState()
    val managerReminder by manager.gentleReminder.collectAsState()

    // ── Focus session state ──
    var mode by remember { mutableStateOf(FocusMode.FOCUS) }
    var secondsLeft by remember { mutableIntStateOf(FocusMode.FOCUS.totalSeconds) }
    var showFinishDialog by remember { mutableStateOf(false) }
    var showGoalDialog by remember { mutableStateOf(false) }
    var showCompletedDialog by remember { mutableStateOf(false) }
    var selectedGoal by remember(stats.goalMinutes) { mutableIntStateOf(stats.goalMinutes) }

    // ── Preview expand/collapse ──
    var previewExpanded by remember { mutableStateOf(false) }

    // ── Camera permission ──
    var cameraPermissionGranted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED,
        )
    }
    var permissionRequested by remember { mutableStateOf(false) }

    val running = activeSession?.status == "active"
    val paused = activeSession?.status == "paused"

    // ── Eligibility helper ──
    fun updateEligibility(mgr: com.example.campusai.data.expression.ExpressionSessionManager) {
        scope.launch {
            mgr.updateEligibility(
                enabled = assistanceEnabled,
                permissionGranted = cameraPermissionGranted,
                running = running,
                visible = true,
                foreground = true,
                mode = mode,
            )
        }
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        cameraPermissionGranted = granted
        if (granted) {
            scope.launch {
                appRepository.setLearningAssistanceEnabled(true)
                updateEligibility(manager)
            }
        }
    }

    // ── Track active FOCUS session for beginFocusSession ──
    var sessionStarted by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) { repository.refresh() }
    LaunchedEffect(activeSession?.id, activeSession?.status) {
        activeSession?.let { session ->
            mode = session.mode
            if (secondsLeft == FocusMode.FOCUS.totalSeconds || secondsLeft > mode.totalSeconds) {
                secondsLeft = mode.totalSeconds
            }
        }
    }

    // ── Timer tick ──
    LaunchedEffect(running, activeSession?.id) {
        while (running && secondsLeft > 0) {
            delay(1000)
            secondsLeft--
            if (secondsLeft == 0) {
                repository.finish().onSuccess {
                    showCompletedDialog = true
                    secondsLeft = mode.totalSeconds
                }
            }
        }
    }

    // ── beginFocusSession: once per new FOCUS session ──
    LaunchedEffect(running, mode, activeSession?.id) {
        if (running && mode == FocusMode.FOCUS && !sessionStarted) {
            manager.beginFocusSession()
            sessionStarted = true
        }
        if (!running) {
            sessionStarted = false
        }
    }

    LaunchedEffect(assistanceEnabled, cameraPermissionGranted, running, paused, mode) {
        updateEligibility(manager)
    }

    // ── Lifecycle observer: page visibility & app foreground ──
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> {
                    scope.launch {
                        manager.updateEligibility(visible = true, foreground = true, mode = mode)
                    }
                }
                Lifecycle.Event.ON_PAUSE -> {
                    scope.launch {
                        manager.updateEligibility(visible = false, foreground = false, mode = mode)
                    }
                }
                else -> {}
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            scope.launch {
                manager.updateEligibility(visible = false, foreground = false, mode = mode)
            }
        }
    }

    // ── Attach lifecycle (always, for analysis without preview) ──
    DisposableEffect(lifecycleOwner) {
        manager.attachLifecycle(lifecycleOwner)
        onDispose {
            manager.detachLifecycle()
            scope.launch {
                manager.updateEligibility(visible = false, foreground = false, mode = mode)
            }
        }
    }

    // ── Build ──
    val minutes = (secondsLeft / 60).toString().padStart(2, '0')
    val seconds = (secondsLeft % 60).toString().padStart(2, '0')
    val ringProgress = secondsLeft.toFloat() / mode.totalSeconds

    LazyColumn(
        modifier = Modifier.fillMaxSize().background(FocusBg),
        contentPadding = PaddingValues(
            start = 16.dp, top = 20.dp, end = 16.dp,
            bottom = BottomDockReservedHeight + 26.dp,
        ),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        // ── Remote error ──
        remoteError?.let { message ->
            item {
                Surface(
                    color = Color(0xFFFFECE7),
                    shape = RoundedCornerShape(16.dp),
                ) {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.CloudOff, null, tint = FocusOrange)
                        Spacer(Modifier.width(8.dp))
                        Text(message, Modifier.weight(1f), color = TextPrimary, fontSize = 12.sp)
                        TextButton(onClick = { scope.launch { repository.refresh() } }) {
                            Text("重试")
                        }
                    }
                }
            }
        }

        // ── Gentle reminder ──
        managerReminder?.let { reminder ->
            item {
                Surface(
                    shape = RoundedCornerShape(16.dp),
                    color = Color(0xFFFFF8EC),
                    border = BorderStroke(1.dp, FocusOrange.copy(alpha = 0.3f)),
                ) {
                    Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Lightbulb, null, tint = FocusOrange)
                        Spacer(Modifier.width(10.dp))
                        Text(reminder, Modifier.weight(1f), color = TextPrimary, fontSize = 13.sp)
                    }
                }
            }
        }

        // ── Timer ring ──
        item {
            Column(
                Modifier.clip(RoundedCornerShape(28.dp)).background(Surface).padding(14.dp),
            ) {
                FocusModeTabs(
                    selected = mode,
                    enabled = activeSession == null,
                    onSelect = { chosen ->
                        mode = chosen
                        secondsLeft = chosen.totalSeconds
                    },
                )
                Spacer(Modifier.height(22.dp))
                Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                    Box(contentAlignment = Alignment.Center, modifier = Modifier.size(258.dp)) {
                        CircularProgressIndicator(
                            progress = { ringProgress },
                            modifier = Modifier.fillMaxSize(),
                            color = FocusBlue,
                            trackColor = PrimarySoft,
                            strokeWidth = 12.dp,
                        )
                        CircularProgressIndicator(
                            progress = { .82f },
                            modifier = Modifier.size(224.dp),
                            color = Color(0xFFDEE2FF),
                            trackColor = Color.Transparent,
                            strokeWidth = 2.dp,
                        )
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                "$minutes:$seconds",
                                color = TextPrimary,
                                fontWeight = FontWeight.ExtraBold,
                                fontSize = 55.sp,
                            )
                            Spacer(Modifier.height(9.dp))
                            Text(
                                if (running) "正在专注"
                                else if (paused) "已暂停"
                                else "✦ 准备开始 ✦",
                                color = Muted,
                                fontSize = 16.sp,
                            )
                        }
                    }
                }
                Spacer(Modifier.height(22.dp))
                Button(
                    onClick = {
                        scope.launch {
                            when (activeSession?.status) {
                                null -> repository.start(mode, null, relatedTaskId)
                                    .onSuccess { secondsLeft = mode.totalSeconds }
                                "active" -> repository.pause()
                                "paused" -> repository.resume()
                            }
                        }
                    },
                    modifier = Modifier.align(Alignment.CenterHorizontally).height(56.dp),
                    shape = RoundedCornerShape(28.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = FocusBlue),
                ) {
                    Icon(
                        if (running) Icons.Default.Pause else Icons.Default.PlayArrow,
                        null,
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        if (running) "暂停"
                        else if (paused) "继续"
                        else "开始",
                        fontWeight = FontWeight.Bold,
                        fontSize = 19.sp,
                    )
                }
                if (activeSession != null) {
                    TextButton(
                        onClick = { showFinishDialog = true },
                        modifier = Modifier.align(Alignment.CenterHorizontally),
                    ) {
                        Text("结束本次${mode.label}", color = Muted)
                    }
                }
            }
        }

        // ── Learning assistance card ──
        item {
            Surface(shape = RoundedCornerShape(25.dp), color = Surface) {
                Column(Modifier.padding(18.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Surface(shape = CircleShape, color = PrimarySoft) {
                            Icon(
                                Icons.Default.SmartToy, null,
                                Modifier.padding(9.dp), tint = FocusBlue,
                            )
                        }
                        Spacer(Modifier.width(10.dp))
                        Column(Modifier.weight(1f)) {
                            Text(
                                "学习状态辅助",
                                color = TextPrimary,
                                fontWeight = FontWeight.ExtraBold,
                                fontSize = 18.sp,
                            )
                            Text(
                                "画面仅在本机处理，不保存，不上传",
                                color = Muted,
                                fontSize = 12.sp,
                            )
                        }
                        Switch(
                            checked = assistanceEnabled,
                            onCheckedChange = { enabled ->
                                if (enabled && !cameraPermissionGranted) {
                                    permissionRequested = true
                                    permissionLauncher.launch(Manifest.permission.CAMERA)
                                } else {
                                    scope.launch {
                                        appRepository.setLearningAssistanceEnabled(enabled)
                                        updateEligibility(manager)
                                    }
                                }
                            },
                        )
                    }

                    // ── Camera permission denied state ──
                    if (assistanceEnabled && !cameraPermissionGranted && permissionRequested) {
                        Spacer(Modifier.height(12.dp))
                        Surface(
                            shape = RoundedCornerShape(14.dp),
                            color = Color(0xFFFFECE7),
                        ) {
                            Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.CameraAlt, null, tint = FocusOrange, modifier = Modifier.size(18.dp))
                                Spacer(Modifier.width(8.dp))
                                Text("需要摄像头权限才能运行学习状态辅助", color = TextPrimary, fontSize = 12.sp, modifier = Modifier.weight(1f))
                                TextButton(onClick = { permissionLauncher.launch(Manifest.permission.CAMERA) }) {
                                    Text("授权", color = FocusBlue, fontWeight = FontWeight.Bold)
                                }
                            }
                        }
                    }

                    Spacer(Modifier.height(14.dp))

                    // ── Real status display ──
                    Surface(
                        shape = RoundedCornerShape(17.dp),
                        color = Color(0xFFFAFBFF),
                        border = BorderStroke(1.dp, Line),
                    ) {
                        Column(Modifier.padding(13.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
                            // Service status
                            AssistLine(
                                Icons.Default.Memory,
                                statusText(managerStatus, assistanceEnabled, cameraPermissionGranted, running, mode),
                            )
                            // Focus state
                            AssistLine(
                                Icons.Default.Visibility,
                                focusStateText(managerFocusState),
                            )
                            // Expression
                            val exprText = expressionText(managerResult)
                            AssistLine(
                                Icons.Default.SentimentSatisfied,
                                exprText,
                            )
                            // Session timer
                            AssistLine(
                                Icons.Default.Schedule,
                                "本次专注时长：${mode.minutes - secondsLeft / 60} 分钟",
                            )
                            // Behavior (NoOp)
                            AssistLine(
                                Icons.Default.Accessibility,
                                "动作识别模型暂未接入",
                            )
                        }
                    }

                    // ── Preview toggle ──
                    if (assistanceEnabled && cameraPermissionGranted && mode == FocusMode.FOCUS) {
                        Spacer(Modifier.height(10.dp))
                        TextButton(
                            onClick = { previewExpanded = !previewExpanded },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Icon(
                                if (previewExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                                null,
                                tint = FocusBlue,
                            )
                            Spacer(Modifier.width(4.dp))
                            Text(
                                if (previewExpanded) "收起画面 ▴" else "查看画面 ▾",
                                color = FocusBlue,
                                fontWeight = FontWeight.SemiBold,
                            )
                        }

                        if (previewExpanded) {
                            AndroidView(
                                factory = { ctx ->
                                    PreviewView(ctx).apply {
                                        scaleType = PreviewView.ScaleType.FILL_CENTER
                                        implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                                    }
                                },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(220.dp)
                                    .clip(RoundedCornerShape(14.dp))
                                    .border(2.dp, FocusBlue.copy(alpha = 0.4f), RoundedCornerShape(14.dp)),
                                update = { view ->
                                    manager.attachPreview(view)
                                },
                            )
                            Spacer(Modifier.height(6.dp))
                            Text(
                                "画面仅在本机处理，不会保存或上传",
                                color = Muted,
                                fontSize = 10.sp,
                                modifier = Modifier.align(Alignment.CenterHorizontally),
                            )
                        }
                    }

                    // Detach preview when collapsed
                    if (!previewExpanded) {
                        LaunchedEffect(Unit) { manager.detachPreview() }
                    }
                }
            }
        }

        // ── Stats row ──
        item {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                FocusStat(Modifier.weight(1f), Icons.Default.Timer, stats.todayMinutes.toString(), "分钟", "今日专注", PrimarySoft)
                FocusStat(Modifier.weight(1f), Icons.Default.MilitaryTech, stats.todayCount.toString(), "次", "完成次数", Color(0xFFEFF7FF))
                FocusStat(Modifier.weight(1f), Icons.Default.LocalFireDepartment, stats.streakDays.toString(), "天", "连续天数", Color(0xFFFFF3EC))
            }
        }

        // ── Goal card ──
        item {
            Surface(shape = RoundedCornerShape(26.dp), color = Surface) {
                Row(
                    Modifier.fillMaxWidth().heightIn(min = 164.dp).padding(18.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text("自习目标", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                        Spacer(Modifier.height(8.dp))
                        Text("每日 ${stats.goalMinutes} 分钟", color = TextPrimary, fontWeight = FontWeight.ExtraBold, fontSize = 22.sp)
                        Text("设定目标，保持专注，见证成长", color = Muted, fontSize = 12.sp)
                        Spacer(Modifier.height(13.dp))
                        OutlinedButton(
                            onClick = { selectedGoal = stats.goalMinutes; showGoalDialog = true },
                            shape = RoundedCornerShape(14.dp),
                        ) {
                            Text("设定目标", color = FocusBlue, fontWeight = FontWeight.Bold)
                        }
                    }
                    androidx.compose.foundation.Image(
                        painter = painterResource(R.drawable.focus_goal_illustration),
                        contentDescription = "学习目标插画",
                        modifier = Modifier.size(142.dp),
                        contentScale = ContentScale.Fit,
                    )
                }
            }
        }

        // ── Recent records ──
        item {
            Text("最近记录", color = TextPrimary, fontWeight = FontWeight.ExtraBold, fontSize = 19.sp)
        }
        if (records.isEmpty()) {
            item {
                Text(
                    "完成一次专注后，记录会从后端同步到这里。",
                    color = Muted,
                    fontSize = 13.sp,
                    modifier = Modifier.padding(bottom = 12.dp),
                )
            }
        } else {
            items(records.take(8), key = { it.id }) { record ->
                Surface(shape = RoundedCornerShape(18.dp), color = Surface) {
                    Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.CheckCircle, null, tint = FocusBlue)
                        Spacer(Modifier.width(11.dp))
                        Column(Modifier.weight(1f)) {
                            Text(
                                "${FocusMode.byName(record.mode).label} · ${record.actualMinutes} 分钟",
                                color = TextPrimary,
                                fontWeight = FontWeight.SemiBold,
                            )
                            Text(
                                record.endedAt,
                                color = Muted,
                                fontSize = 11.sp,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                        Text("已完成", color = FocusGreen, fontSize = 12.sp)
                    }
                }
            }
        }
    }

    // ── Dialogs ──
    if (showFinishDialog) {
        AlertDialog(
            onDismissRequest = { showFinishDialog = false },
            title = { Text("结束本次专注？") },
            text = { Text("结束时间和时长由后端服务记录。", color = Muted) },
            confirmButton = {
                TextButton(onClick = {
                    scope.launch {
                        repository.finish().onSuccess {
                            showCompletedDialog = true
                            secondsLeft = mode.totalSeconds
                        }
                        showFinishDialog = false
                    }
                }) {
                    Text("结束", color = FocusOrange)
                }
            },
            dismissButton = {
                TextButton(onClick = { showFinishDialog = false }) { Text("继续专注") }
            },
        )
    }
    if (showGoalDialog) {
        AlertDialog(
            onDismissRequest = { showGoalDialog = false },
            title = { Text("设置每日自习目标") },
            text = {
                Column {
                    Text("目标将保存到后端数据库，并在不同设备间同步。", color = Muted, fontSize = 12.sp)
                    Spacer(Modifier.height(12.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf(30, 60, 90, 120).forEach { goal ->
                            FilterChip(
                                selected = selectedGoal == goal,
                                onClick = { selectedGoal = goal },
                                label = { Text("$goal 分钟") },
                            )
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    scope.launch {
                        repository.updateGoal(selectedGoal).onSuccess { showGoalDialog = false }
                    }
                }) {
                    Text("保存", color = FocusBlue)
                }
            },
            dismissButton = {
                TextButton(onClick = { showGoalDialog = false }) { Text("取消") }
            },
        )
    }
    if (showCompletedDialog) {
        AlertDialog(
            onDismissRequest = { showCompletedDialog = false },
            icon = { Icon(Icons.Default.Celebration, null, tint = FocusOrange) },
            title = { Text("本次专注已完成！") },
            text = { Text("记录已保存到后端数据库。", color = Muted) },
            confirmButton = {
                TextButton(onClick = { showCompletedDialog = false }) {
                    Text("知道了", color = FocusBlue)
                }
            },
        )
    }
}

// ── Helpers ──

private fun statusText(
    status: ExpressionServiceStatus,
    enabled: Boolean,
    hasPermission: Boolean,
    running: Boolean,
    mode: FocusMode,
): String = when {
    !enabled -> "未开启"
    !hasPermission -> "需要摄像头权限"
    !running && mode != FocusMode.FOCUS -> "开始专注后运行"
    !running -> "开始专注后运行"
    status is ExpressionServiceStatus.Initializing -> "正在加载本机模型…"
    status is ExpressionServiceStatus.Ready -> "模型已就绪"
    status is ExpressionServiceStatus.Running -> "本机识别运行中"
    status is ExpressionServiceStatus.Paused -> "已暂停"
    status is ExpressionServiceStatus.NoFace -> "暂未检测到人脸"
    status is ExpressionServiceStatus.LowConfidence -> "当前识别置信度较低"
    status is ExpressionServiceStatus.Error -> "学习状态辅助暂不可用"
    else -> "未开启"
}

private fun focusStateText(state: FocusState): String = when (state) {
    FocusState.FOCUSED -> "专注"
    FocusState.POSSIBLY_DISTRACTED -> "可能分心"
    FocusState.BREAK_SUGGESTED -> "建议短暂休息"
    FocusState.NO_FACE -> "可能暂时离开"
    FocusState.UNAVAILABLE -> "暂不可用"
}

private fun expressionText(result: com.example.campusai.data.model.ExpressionResult): String {
    if (!result.isStable) return "表情识别中…"
    if (result.label == com.example.campusai.data.model.ExpressionLabel.UNKNOWN ||
        result.label == com.example.campusai.data.model.ExpressionLabel.NO_FACE
    ) {
        return "表情识别中…"
    }
    val labelName = when (result.label) {
        com.example.campusai.data.model.ExpressionLabel.HAPPY -> "开心"
        com.example.campusai.data.model.ExpressionLabel.NEUTRAL -> "中性"
        com.example.campusai.data.model.ExpressionLabel.SAD -> "低落"
        com.example.campusai.data.model.ExpressionLabel.ANGRY -> "生气"
        com.example.campusai.data.model.ExpressionLabel.FEAR -> "紧张"
        com.example.campusai.data.model.ExpressionLabel.SURPRISE -> "惊讶"
        com.example.campusai.data.model.ExpressionLabel.DISGUST -> "厌恶"
        com.example.campusai.data.model.ExpressionLabel.UNKNOWN -> return "表情识别中…"
        com.example.campusai.data.model.ExpressionLabel.NO_FACE -> return "表情识别中…"
    }
    val pct = "%.0f".format((result.confidence * 100).coerceIn(0.0, 100.0))
    return "稳定表情：$labelName  置信度：${pct}%"
}

@Composable
private fun FocusModeTabs(selected: FocusMode, enabled: Boolean, onSelect: (FocusMode) -> Unit) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(Color(0xFFF5F6FF)).padding(4.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        listOf(FocusMode.FOCUS, FocusMode.SHORT_BREAK, FocusMode.LONG_BREAK).forEach { item ->
            val active = item == selected
            Surface(
                onClick = { if (enabled) onSelect(item) },
                modifier = Modifier.weight(1f),
                shape = RoundedCornerShape(18.dp),
                color = if (active) FocusBlue else Color.Transparent,
                enabled = enabled,
            ) {
                Row(
                    Modifier.padding(vertical = 11.dp),
                    horizontalArrangement = Arrangement.Center,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        if (item == FocusMode.FOCUS) Icons.Default.Timer else Icons.Default.NightlightRound,
                        null,
                        modifier = Modifier.size(16.dp),
                        tint = if (active) Color.White else Muted,
                    )
                    Spacer(Modifier.width(4.dp))
                    Text(
                        "${item.label} ${item.minutes} 分钟",
                        color = if (active) Color.White else TextPrimary,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            }
        }
    }
}

@Composable
private fun AssistLine(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    text: String,
) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = Muted, modifier = Modifier.size(17.dp))
        Spacer(Modifier.width(10.dp))
        Text(text, color = Muted, fontSize = 12.sp)
    }
}

@Composable
private fun FocusStat(
    modifier: Modifier,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    value: String,
    unit: String,
    label: String,
    background: Color,
) {
    Column(
        modifier.clip(RoundedCornerShape(20.dp)).background(background).padding(vertical = 13.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(
            icon, null,
            tint = if (icon == Icons.Default.LocalFireDepartment) FocusOrange else FocusBlue,
            modifier = Modifier.size(25.dp),
        )
        Spacer(Modifier.height(6.dp))
        Row(verticalAlignment = Alignment.Bottom) {
            Text(value, color = TextPrimary, fontSize = 26.sp, fontWeight = FontWeight.ExtraBold)
            Spacer(Modifier.width(2.dp))
            Text(unit, color = Muted, fontSize = 10.sp)
        }
        Text(label, color = Muted, fontSize = 11.sp)
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

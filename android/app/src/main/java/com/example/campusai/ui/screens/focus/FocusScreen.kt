package com.example.campusai.ui.screens.focus

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Face
import androidx.compose.material.icons.filled.LocalFireDepartment
import androidx.compose.material.icons.filled.SelfImprovement
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material.icons.filled.Videocam
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.example.campusai.data.expression.ExpressionServiceStatus
import com.example.campusai.data.expression.ExpressionSessionManager
import com.example.campusai.data.focus.FocusState
import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.FocusMode
import com.example.campusai.data.model.FocusSessionSummary
import com.example.campusai.data.model.FocusTimerState
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.FocusRepository
import com.example.campusai.ui.components.AnimatedCircularProgress
import com.example.campusai.ui.components.CampusCard
import com.example.campusai.ui.components.CampusPageHeader
import com.example.campusai.ui.components.ConfirmDialog
import com.example.campusai.ui.components.EmptyState
import com.example.campusai.ui.components.FilterChipRow
import com.example.campusai.ui.components.StatusTag
import com.example.campusai.ui.components.StatusTone
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.strings.CampusStrings
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** The sole timer and camera entry point for focused learning. */
@Composable
fun FocusScreen(
    repository: FocusRepository,
    appRepository: AppRepository,
    reduceMotion: Boolean,
    onBack: () -> Unit,
    onOpenCounselorPlan: (String) -> Unit,
) {
    val records by repository.records.collectAsState()
    val stats by repository.stats.collectAsState()
    val persistedTimer by repository.timer.collectAsState()
    val loading by repository.loading.collectAsState()
    val mockMode by appRepository.mockMode.collectAsState()
    val assistanceEnabled by appRepository.learningAssistanceEnabled.collectAsState()
    val manager = appRepository.expressionSessionManager
    val expressionStatus by manager.status.collectAsState()
    val expression by manager.result.collectAsState()
    val focusState by manager.focusState.collectAsState()
    val gentleReminder by manager.gentleReminder.collectAsState()
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    var mode by remember { mutableStateOf(FocusMode.FOCUS) }
    var secondsLeft by remember { mutableIntStateOf(FocusMode.FOCUS.totalSeconds) }
    var running by remember { mutableStateOf(false) }
    var restored by remember { mutableStateOf(false) }
    var sessionStarted by remember { mutableStateOf(false) }
    var showEndConfirm by remember { mutableStateOf(false) }
    var showCompleted by remember { mutableStateOf(false) }
    var permissionDenied by remember { mutableStateOf(false) }
    var lastSummary by remember { mutableStateOf<FocusSessionSummary?>(null) }
    var appForeground by remember { mutableStateOf(true) }
    val cameraPermissionGranted = mockMode || ContextCompat.checkSelfPermission(
        context,
        Manifest.permission.CAMERA,
    ) == PackageManager.PERMISSION_GRANTED
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        permissionDenied = !granted
        scope.launch {
            manager.updateEligibility(
                enabled = granted,
                permissionGranted = granted,
                running = running,
                visible = true,
                foreground = appForeground,
            )
        }
    }

    LaunchedEffect(loading) {
        if (!loading && !restored) {
            restored = true
            val saved = persistedTimer ?: return@LaunchedEffect
            val savedMode = FocusMode.byName(saved.mode)
            val remaining = saved.currentRemaining(System.currentTimeMillis())
            if (saved.running && remaining <= 0) {
                repository.addRecord(savedMode, savedMode.minutes, finished = true)
                repository.saveTimer(null)
                showCompleted = true
            } else {
                mode = savedMode
                secondsLeft = remaining
                running = saved.running
                if (saved.running && savedMode == FocusMode.FOCUS) {
                    sessionStarted = true
                    manager.beginFocusSession()
                }
            }
        }
    }

    fun persistTimer(isRunning: Boolean, remaining: Int, currentMode: FocusMode) {
        scope.launch {
            repository.saveTimer(
                FocusTimerState(currentMode.name, remaining, isRunning, System.currentTimeMillis()),
            )
        }
    }

    fun finishSession(completed: Boolean) {
        val elapsedSeconds = mode.totalSeconds - secondsLeft
        val actualMinutes = if (completed) mode.minutes else elapsedSeconds / 60
        val shouldRecord = completed || actualMinutes > 0
        running = false
        scope.launch {
            manager.updateEligibility(
                enabled = assistanceEnabled,
                permissionGranted = cameraPermissionGranted,
                running = false,
                visible = true,
                foreground = appForeground,
            )
            val summary = if (mode == FocusMode.FOCUS && sessionStarted) {
                manager.finishFocusSession(actualMinutes)
            } else {
                null
            }
            if (shouldRecord) repository.addRecord(mode, actualMinutes, completed, summary)
            repository.saveTimer(null)
            lastSummary = summary
            sessionStarted = false
        }
        secondsLeft = mode.totalSeconds
        if (completed) showCompleted = true
    }

    LaunchedEffect(assistanceEnabled, cameraPermissionGranted, running, appForeground) {
        manager.updateEligibility(
            enabled = assistanceEnabled,
            permissionGranted = cameraPermissionGranted,
            running = running && mode == FocusMode.FOCUS,
            visible = true,
            foreground = appForeground,
        )
    }

    LaunchedEffect(running) {
        while (running && secondsLeft > 0) {
            delay(1_000)
            secondsLeft--
            if (secondsLeft % 10 == 0) persistTimer(true, secondsLeft, mode)
            if (secondsLeft <= 0) finishSession(completed = true)
        }
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
            manager.releaseAsync()
            if (secondsLeft != mode.totalSeconds || running) persistTimer(running, secondsLeft, mode)
        }
    }

    val minutes = (secondsLeft / 60).toString().padStart(2, '0')
    val secs = (secondsLeft % 60).toString().padStart(2, '0')
    val progress = secondsLeft.toFloat() / mode.totalSeconds.toFloat()
    val activeMinutes = ((mode.totalSeconds - secondsLeft) / 60).coerceAtLeast(0)

    LazyColumn(
        modifier = Modifier.fillMaxSize().background(Background).padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = PaddingValues(
            top = 12.dp,
            bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + BottomDockReservedHeight + 16.dp,
        ),
    ) {
        item { CampusPageHeader(CampusStrings.Focus.TITLE, CampusStrings.Focus.SUBTITLE, onBack) }
        item {
            CampusCard(modifier = Modifier.enterAnimation(enabled = !reduceMotion), padding = PaddingValues(20.dp)) {
                FilterChipRow(
                    options = listOf(CampusStrings.Focus.MODE_FOCUS, CampusStrings.Focus.MODE_SHORT, CampusStrings.Focus.MODE_LONG),
                    selected = when (mode) {
                        FocusMode.FOCUS -> CampusStrings.Focus.MODE_FOCUS
                        FocusMode.SHORT_BREAK -> CampusStrings.Focus.MODE_SHORT
                        FocusMode.LONG_BREAK -> CampusStrings.Focus.MODE_LONG
                    },
                    onSelect = { label -> if (!running) {
                        mode = when (label) {
                            CampusStrings.Focus.MODE_SHORT -> FocusMode.SHORT_BREAK
                            CampusStrings.Focus.MODE_LONG -> FocusMode.LONG_BREAK
                            else -> FocusMode.FOCUS
                        }
                        secondsLeft = mode.totalSeconds
                        scope.launch { repository.saveTimer(null) }
                    } },
                )
                Spacer(Modifier.height(18.dp))
                Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                    Box(contentAlignment = Alignment.Center, modifier = Modifier.size(190.dp)) {
                        AnimatedCircularProgress(
                            targetProgress = progress,
                            modifier = Modifier.fillMaxSize(),
                            color = if (running) Primary else Primary.copy(alpha = .55f),
                            trackColor = PrimarySoft,
                            strokeWidth = 10.dp,
                        )
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("$minutes:$secs", fontSize = 46.sp, fontWeight = FontWeight.Bold, color = Primary, letterSpacing = 2.sp)
                            Text(if (running) "专注进行中" else if (secondsLeft != mode.totalSeconds) "已暂停" else "准备开始", color = Muted, fontSize = 11.sp)
                        }
                    }
                }
                Spacer(Modifier.height(18.dp))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp, Alignment.CenterHorizontally)) {
                    Box(Modifier.clip(RoundedCornerShape(12.dp)).background(Primary).campusClickable {
                        if (!running && mode == FocusMode.FOCUS && !sessionStarted) {
                            sessionStarted = true
                            scope.launch { manager.beginFocusSession() }
                        }
                        running = !running
                        persistTimer(running, secondsLeft, mode)
                    }.padding(horizontal = 26.dp, vertical = 12.dp)) {
                        Text(if (running) CampusStrings.Focus.PAUSE else if (secondsLeft != mode.totalSeconds) CampusStrings.Focus.RESUME else CampusStrings.Focus.START, color = Color.White, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                    }
                    if (secondsLeft != mode.totalSeconds) {
                        Box(Modifier.clip(RoundedCornerShape(12.dp)).background(PrimarySoft).campusClickable { showEndConfirm = true }.padding(horizontal = 26.dp, vertical = 12.dp)) {
                            Text(CampusStrings.Focus.END, color = Primary, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                        }
                    }
                }
            }
        }
        item {
            LearningAssistanceCard(
                manager = manager,
                enabled = assistanceEnabled,
                mockMode = mockMode,
                cameraPermissionGranted = cameraPermissionGranted,
                permissionDenied = permissionDenied,
                running = running && mode == FocusMode.FOCUS,
                activeMinutes = activeMinutes,
                status = expressionStatus,
                focusState = focusState,
                expression = expression.label,
                modelVersion = expression.modelVersion,
                reminder = gentleReminder,
                onToggle = { enabled ->
                    scope.launch { appRepository.setLearningAssistanceEnabled(enabled) }
                    if (enabled && !mockMode && !cameraPermissionGranted) permissionLauncher.launch(Manifest.permission.CAMERA)
                },
            )
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                StatCard(Modifier.weight(1f), Icons.Default.Timer, "${stats.todayMinutes}", CampusStrings.Focus.MINUTES_UNIT, CampusStrings.Focus.STATS_TODAY)
                StatCard(Modifier.weight(1f), Icons.Default.SelfImprovement, "${stats.todayCount}", CampusStrings.Focus.TIMES_UNIT, CampusStrings.Focus.STATS_COUNT)
                StatCard(Modifier.weight(1f), Icons.Default.LocalFireDepartment, "${stats.streakDays}", CampusStrings.Focus.DAYS_UNIT, CampusStrings.Focus.STATS_STREAK)
            }
        }
        item {
            CampusCard {
                Text(CampusStrings.Focus.GOAL_TITLE, color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(4.dp))
                Text(CampusStrings.Focus.GOAL_FORMAT.format(stats.goalMinutes), color = Muted, fontSize = 11.5.sp)
                Spacer(Modifier.height(10.dp))
                FilterChipRow(
                    options = listOf("30", "60", "90", "120"),
                    selected = stats.goalMinutes.toString(),
                    onSelect = { scope.launch { repository.setGoal(it.toInt()) } },
                )
                Spacer(Modifier.height(12.dp))
                Box(Modifier.fillMaxWidth().height(8.dp).clip(CircleShape).background(PrimarySoft)) {
                    Box(Modifier.fillMaxWidth((stats.todayMinutes.toFloat() / stats.goalMinutes).coerceIn(0f, 1f)).height(8.dp).clip(CircleShape).background(Primary))
                }
            }
        }
        item {
            CampusCard(padding = PaddingValues(14.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.AutoAwesome, null, tint = Primary, modifier = Modifier.size(22.dp))
                    Spacer(Modifier.width(10.dp))
                    Column(Modifier.weight(1f)) {
                        Text("让 AI 导员分析本次专注", color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                        Text("仅在你点击后发送结构化本机摘要，不含画面或逐帧结果", color = Muted, fontSize = 11.sp)
                    }
                    Button(
                        onClick = { lastSummary?.let { onOpenCounselorPlan(it.toCounselorPrompt()) } },
                        enabled = lastSummary != null,
                        colors = ButtonDefaults.buttonColors(containerColor = Primary),
                    ) { Text("分析", fontSize = 12.sp) }
                }
            }
        }
        item { Text(CampusStrings.Focus.RECORDS_TITLE, color = TextPrimary, fontSize = 15.sp, fontWeight = FontWeight.Bold) }
        if (records.isEmpty()) item { EmptyState(Icons.Default.Timer, CampusStrings.Focus.RECORDS_EMPTY) }
        else items(records.take(10), key = { it.id }) { record ->
            CampusCard(padding = PaddingValues(13.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(FocusMode.byName(record.mode).label + " · " + record.date, color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                        Spacer(Modifier.height(3.dp))
                        Text("${record.actualMinutes}/${record.plannedMinutes} ${CampusStrings.Focus.MINUTES_UNIT} · ${record.endedAt}", color = Muted, fontSize = 11.sp)
                    }
                    StatusTag(if (record.finished) CampusStrings.Focus.FINISHED_TAG else CampusStrings.Focus.UNFINISHED_TAG, if (record.finished) StatusTone.SUCCESS else StatusTone.NEUTRAL)
                }
            }
        }
    }
    if (showEndConfirm) ConfirmDialog(CampusStrings.Focus.END_TITLE, CampusStrings.Focus.END_MESSAGE, CampusStrings.Focus.END, true, { showEndConfirm = false; finishSession(false) }, { showEndConfirm = false })
    if (showCompleted) AlertDialog(
        onDismissRequest = { showCompleted = false },
        title = { Text(CampusStrings.Focus.COMPLETED_TITLE, fontWeight = FontWeight.Bold) },
        text = { Text(CampusStrings.Focus.COMPLETED_MESSAGE, color = Muted) },
        confirmButton = { TextButton({ showCompleted = false }) { Text(CampusStrings.Common.CONFIRM, color = Primary) } },
        containerColor = Surface,
    )
}

@Composable
private fun LearningAssistanceCard(
    manager: ExpressionSessionManager,
    enabled: Boolean,
    mockMode: Boolean,
    cameraPermissionGranted: Boolean,
    permissionDenied: Boolean,
    running: Boolean,
    activeMinutes: Int,
    status: ExpressionServiceStatus,
    focusState: FocusState,
    expression: ExpressionLabel,
    modelVersion: String,
    reminder: String?,
    onToggle: (Boolean) -> Unit,
) {
    val lifecycleOwner = LocalLifecycleOwner.current
    CampusCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.Face, null, tint = Primary)
            Spacer(Modifier.width(8.dp))
            Column(Modifier.weight(1f)) {
                Text("学习状态辅助", color = TextPrimary, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                Text("画面仅在本机处理，不保存、不上传", color = Muted, fontSize = 11.sp)
            }
            Switch(enabled, onCheckedChange = onToggle)
        }
        if (enabled && !mockMode && cameraPermissionGranted) {
            Spacer(Modifier.height(12.dp))
            AndroidView(
                factory = { viewContext -> PreviewView(viewContext).also { manager.attachPreview(lifecycleOwner, it) } },
                update = { manager.attachPreview(lifecycleOwner, it) },
                onRelease = { scopeView ->
                    // The screen-level lifecycle effect performs the suspending unbind immediately.
                },
                modifier = Modifier.fillMaxWidth().height(180.dp).clip(RoundedCornerShape(14.dp)),
            )
        }
        Spacer(Modifier.height(10.dp))
        Text("${if (mockMode) "Mock" else "本机 LiteRT"} · ${statusLabel(status)} · $modelVersion", color = Muted, fontSize = 11.sp)
        Text("当前辅助观察：${focusStateLabel(focusState)} · 稳定表情：${expressionLabel(expression)}", color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
        Text("本次专注持续：$activeMinutes 分钟${if (running) "（分析中）" else ""}", color = Muted, fontSize = 11.sp)
        if (permissionDenied) Text("未授予相机权限，学习状态辅助未启动。", color = Muted, fontSize = 11.sp)
        if (reminder != null) Text(reminder, color = Primary, fontSize = 12.sp, modifier = Modifier.padding(top = 6.dp))
    }
}

private fun statusLabel(status: ExpressionServiceStatus) = when (status) {
    ExpressionServiceStatus.Off -> "未加载"
    ExpressionServiceStatus.Initializing -> "模型加载中"
    ExpressionServiceStatus.Ready -> "模型已就绪"
    ExpressionServiceStatus.Running -> "本机分析中"
    ExpressionServiceStatus.Paused -> "已暂停并释放相机"
    ExpressionServiceStatus.NoFace -> "等待画面"
    ExpressionServiceStatus.LowConfidence -> "结果暂不稳定"
    is ExpressionServiceStatus.Error -> "不可用：${status.message}"
}

private fun focusStateLabel(state: FocusState) = when (state) {
    FocusState.FOCUSED -> "正在辅助观察"
    FocusState.POSSIBLY_DISTRACTED -> "可能注意力偏离"
    FocusState.BREAK_SUGGESTED -> "建议休息"
    FocusState.NO_FACE -> "可能暂时离开"
    FocusState.UNAVAILABLE -> "暂不可用"
}

private fun expressionLabel(label: ExpressionLabel) = when (label) {
    ExpressionLabel.HAPPY -> "愉快"
    ExpressionLabel.NEUTRAL -> "中性"
    ExpressionLabel.SAD -> "低落"
    ExpressionLabel.ANGRY -> "生气"
    ExpressionLabel.FEAR -> "紧张"
    ExpressionLabel.SURPRISE -> "惊讶"
    ExpressionLabel.DISGUST -> "厌恶"
    ExpressionLabel.UNKNOWN -> "暂不稳定"
    ExpressionLabel.NO_FACE -> "无画面"
}

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

@Composable
private fun StatCard(modifier: Modifier, icon: androidx.compose.ui.graphics.vector.ImageVector, value: String, unit: String, label: String) {
    Column(modifier.clip(RoundedCornerShape(16.dp)).background(Surface).padding(vertical = 13.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(icon, null, tint = Primary, modifier = Modifier.size(18.dp))
        Spacer(Modifier.height(7.dp))
        Row(verticalAlignment = Alignment.Bottom) { Text(value, color = TextPrimary, fontSize = 19.sp, fontWeight = FontWeight.Bold); Spacer(Modifier.width(2.dp)); Text(unit, color = Muted, fontSize = 10.sp) }
        Text(label, color = Muted, fontSize = 10.5.sp)
    }
}

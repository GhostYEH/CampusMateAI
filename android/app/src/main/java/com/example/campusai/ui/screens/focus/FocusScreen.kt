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
import androidx.compose.foundation.lazy.itemsIndexed
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
import com.example.campusai.data.behavior.BehaviorPrediction
import com.example.campusai.data.behavior.StudyBehavior
import com.example.campusai.data.expression.ExpressionServiceStatus
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
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val manager = appRepository.expressionSessionManager
    val behaviorPrediction by manager.behaviorPrediction.collectAsState()
    val assistanceStatus by manager.status.collectAsState()
    val focusState by manager.focusState.collectAsState()
    val gentleReminder by manager.gentleReminder.collectAsState()

    var cameraPermissionGranted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED,
        )
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        cameraPermissionGranted = granted
    }

    var mode by remember { mutableStateOf(FocusMode.FOCUS) }
    var secondsLeft by remember { mutableIntStateOf(FocusMode.FOCUS.totalSeconds) }
    var showFinishDialog by remember { mutableStateOf(false) }
    var showGoalDialog by remember { mutableStateOf(false) }
    var showCompletedDialog by remember { mutableStateOf(false) }
    var selectedGoal by remember(stats.goalMinutes) { mutableIntStateOf(stats.goalMinutes) }

    val running = activeSession?.status == "active"
    val paused = activeSession?.status == "paused"

    DisposableEffect(lifecycleOwner) {
        manager.attachLifecycle(lifecycleOwner)
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> scope.launch {
                    manager.updateEligibility(foreground = true)
                }
                Lifecycle.Event.ON_PAUSE -> scope.launch {
                    manager.updateEligibility(foreground = false)
                }
                else -> {}
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            scope.launch {
                manager.updateEligibility(visible = false, foreground = false)
                manager.detachLifecycle()
            }
        }
    }

    LaunchedEffect(assistanceEnabled, cameraPermissionGranted, running, mode) {
        if (assistanceEnabled && !cameraPermissionGranted) {
            permissionLauncher.launch(Manifest.permission.CAMERA)
        }
        manager.updateEligibility(
            enabled = assistanceEnabled,
            permissionGranted = cameraPermissionGranted,
            running = running,
            visible = true,
            foreground = true,
            mode = mode,
        )
    }


    LaunchedEffect(backendOnline) {
        if (backendOnline) repository.refresh()
    }
    LaunchedEffect(activeSession?.id, activeSession?.status) {
        activeSession?.let { session ->
            mode = session.mode
            if (secondsLeft == FocusMode.FOCUS.totalSeconds || secondsLeft > mode.totalSeconds) secondsLeft = mode.totalSeconds
        }
    }

    LaunchedEffect(running, activeSession?.id) {
        while (running && secondsLeft > 0) {
            delay(1000)
            secondsLeft--
            if (secondsLeft == 0) {
                repository.finish().onSuccess { showCompletedDialog = true; secondsLeft = mode.totalSeconds }
            }
        }
    }
    val minutes = (secondsLeft / 60).toString().padStart(2, '0')
    val seconds = (secondsLeft % 60).toString().padStart(2, '0')
    val ringProgress = secondsLeft.toFloat() / mode.totalSeconds

    LazyColumn(
        modifier = Modifier.fillMaxSize().background(FocusBg),
        contentPadding = PaddingValues(start = 16.dp, top = 20.dp, end = 16.dp, bottom = BottomDockReservedHeight + 26.dp),
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
                                null -> repository.start(mode, null, relatedTaskId).onSuccess { secondsLeft = mode.totalSeconds }
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
                        Switch(checked = assistanceEnabled, onCheckedChange = { enabled -> scope.launch { appRepository.setLearningAssistanceEnabled(enabled) } })
                    }
                    Spacer(Modifier.height(14.dp))
                    Surface(shape = RoundedCornerShape(17.dp), color = Background, border = BorderStroke(1.dp, Line)) {
                        Column(Modifier.padding(13.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
                            AssistLine(Icons.Default.Memory, "本机 ONNX：状态由设备能力决定")
                            AssistLine(Icons.Default.Visibility, "当前辅助观察：${if (assistanceEnabled) "已开启" else "暂不可用"}")
                            AssistLine(Icons.Default.Gesture, behaviorPredictionText(behaviorPrediction))
                            AssistLine(Icons.Default.SentimentSatisfied, "稳定表情：仅作本地提示")
                            AssistLine(Icons.Default.Schedule, "本次专注时长：${mode.minutes - secondsLeft / 60} 分钟")
                        }
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
        else itemsIndexed(records.take(8), key = { index, record -> "focus-record|${record.id}|$index" }) { _, record ->
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

private fun behaviorPredictionText(prediction: BehaviorPrediction?): String {
    if (prediction == null) {
        return "动作识别准备中"
    }
    return when (prediction.modelState) {
        "NOT_INITIALIZED" -> "动作识别准备中"
        "MODEL_NOT_AVAILABLE" -> "动作模型暂不可用"
        "INFERENCE_ERROR" -> "动作识别异常"
        "NO_FRAME" -> "动作识别等待画面"
        "READY_RGB_V1" -> {
            val readProb = prediction.probabilities[StudyBehavior.READING] ?: 0f
            val writeProb = prediction.probabilities[StudyBehavior.WRITING] ?: 0f
            if (readProb >= writeProb && readProb > 0f) {
                "动作识别：阅读 ${(readProb * 100).toInt()}%"
            } else if (writeProb > 0f) {
                "动作识别：书写 ${(writeProb * 100).toInt()}%"
            } else {
                "动作识别等待画面"
            }
        }
        else -> "动作识别准备中"
    }
}

@Composable
private fun FocusStat(modifier: Modifier, icon: androidx.compose.ui.graphics.vector.ImageVector, value: String, unit: String, label: String, background: Color) { Column(modifier.clip(RoundedCornerShape(20.dp)).background(background).padding(vertical = 13.dp), horizontalAlignment = Alignment.CenterHorizontally) { Icon(icon, null, tint = if (icon == Icons.Default.LocalFireDepartment) FocusOrange else FocusBlue, modifier = Modifier.size(25.dp)); Spacer(Modifier.height(6.dp)); Row(verticalAlignment = Alignment.Bottom) { Text(value, color = TextPrimary, fontSize = 26.sp, fontWeight = FontWeight.ExtraBold); Spacer(Modifier.width(2.dp)); Text(unit, color = Muted, fontSize = 10.sp) }; Text(label, color = Muted, fontSize = 11.sp) } }

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

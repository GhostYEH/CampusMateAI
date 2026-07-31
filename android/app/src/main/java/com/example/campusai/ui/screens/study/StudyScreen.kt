package com.example.campusai.ui.screens.study

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.*
import androidx.compose.foundation.border
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.HelpOutline
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import com.example.campusai.data.expression.CameraExpressionRecognitionService
import com.example.campusai.data.expression.ExpressionServiceStatus
import com.example.campusai.data.expression.ObservableExpressionRecognitionService
import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.ExpressionResult
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.AnimatedBar
import com.example.campusai.ui.components.AnimatedCircularProgress
import com.example.campusai.ui.components.ModeBadge
import com.example.campusai.ui.components.MockBadge
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun StudyScreen(repository: AppRepository) {
    val mockMode by repository.mockMode.collectAsState()
    val reduceMotion by repository.reduceMotion.collectAsState()
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val coroutineScope = rememberCoroutineScope()
    val expressionService = remember(mockMode) {
        repository.createExpressionRecognitionService(mockMode)
    }
    val disposalScope = remember(expressionService) {
        CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    }
    val observableService = expressionService as ObservableExpressionRecognitionService
    val expressionStatus by observableService.status.collectAsState()
    val expressionResult by expressionService.results().collectAsState(
        initial = ExpressionResult(
            ExpressionLabel.UNKNOWN,
            0.0,
            emptyMap(),
            System.currentTimeMillis(),
            false,
            "not-loaded",
        ),
    )
    var expressionEnabled by remember(expressionService) { mutableStateOf(false) }
    var permissionDenied by remember(expressionService) { mutableStateOf(false) }
    var seconds by remember { mutableStateOf(25 * 60) }
    var timerRunning by remember { mutableStateOf(false) }
    val cameraPermissionGranted = mockMode || ContextCompat.checkSelfPermission(
        context,
        Manifest.permission.CAMERA,
    ) == PackageManager.PERMISSION_GRANTED
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        permissionDenied = !granted
        if (granted) {
            expressionEnabled = true
            coroutineScope.launch {
                expressionService.initialize()
                if (timerRunning) expressionService.start()
            }
        }
    }

    LaunchedEffect(timerRunning) {
        while (timerRunning && seconds > 0) {
            delay(1000)
            seconds--
            if (seconds <= 0) timerRunning = false
        }
    }

    LaunchedEffect(timerRunning, expressionEnabled, expressionService) {
        if (!expressionEnabled) return@LaunchedEffect
        if (timerRunning) {
            expressionService.start()
        } else {
            expressionService.pause()
        }
    }

    DisposableEffect(expressionService) {
        onDispose {
            (expressionService as? CameraExpressionRecognitionService)?.unbindCamera()
            disposalScope.launch {
                expressionService.dispose()
                disposalScope.cancel()
            }
        }
    }

    val minutes = (seconds / 60).toString().padStart(2, '0')
    val secs = (seconds % 60).toString().padStart(2, '0')

    val totalSeconds = 25 * 60
    val timerProgress = seconds.toFloat() / totalSeconds.toFloat()

    val animatedAlpha by animateFloatAsState(
        targetValue = 1f,
        animationSpec = tween(400, easing = CubicBezierEasing(0.2f, 0.8f, 0.2f, 1f))
    )

    val timerScale by animateFloatAsState(
        targetValue = if (timerRunning) 1.02f else 1f,
        animationSpec = spring(dampingRatio = 0.7f, stiffness = 200f),
        label = "timer-scale",
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp, vertical = 16.dp)
            .graphicsLayer { alpha = animatedAlpha }
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text("学习陪伴", style = MaterialTheme.typography.headlineMedium)
                Text("集中处理与当前模块相关的校园事务。", color = Muted, fontSize = 13.sp)
            }
            ModeBadge(mockMode)
        }

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .background(Surface)
                .border(1.dp, Line, RoundedCornerShape(10.dp))
                .padding(24.dp)
                .enterAnimation(enabled = !reduceMotion),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Text("本次专注", color = Muted, fontSize = 14.sp)
            Box(contentAlignment = Alignment.Center, modifier = Modifier.size(170.dp).scale(timerScale)) {
                AnimatedCircularProgress(
                    targetProgress = timerProgress,
                    color = if (timerRunning) Primary else Primary.copy(alpha = 0.5f),
                    trackColor = PrimarySoft,
                    strokeWidth = 9.dp,
                    modifier = Modifier.fillMaxSize(),
                )
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        "$minutes:$secs",
                        fontSize = 44.sp,
                        fontWeight = FontWeight.Bold,
                        color = Primary,
                        letterSpacing = 2.sp,
                    )
                    Text(
                        if (timerRunning) "专注中…" else "准备就绪",
                        color = Muted,
                        fontSize = 11.sp,
                    )
                }
            }
            Row(
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Button(
                    onClick = { timerRunning = !timerRunning },
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Primary),
                    contentPadding = PaddingValues(horizontal = 20.dp, vertical = 12.dp)
                ) {
                    Icon(
                        if (timerRunning) Icons.Default.Pause else Icons.Default.PlayArrow,
                        null, modifier = Modifier.size(18.dp)
                    )
                    Spacer(Modifier.width(4.dp))
                    Text(if (timerRunning) "暂停" else "开始专注", fontWeight = FontWeight.SemiBold)
                }
                OutlinedButton(
                    onClick = { timerRunning = false; seconds = 25 * 60 },
                    shape = RoundedCornerShape(8.dp),
                    contentPadding = PaddingValues(horizontal = 20.dp, vertical = 12.dp),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = Primary)
                ) {
                    Icon(Icons.Default.Refresh, null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("重置", fontWeight = FontWeight.SemiBold)
                }
            }
        }

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .background(Surface)
                .border(1.dp, Line, RoundedCornerShape(10.dp))
                .padding(14.dp)
                .enterAnimation(delayMs = 60, enabled = !reduceMotion),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("表情识别辅助", style = MaterialTheme.typography.titleSmall)
                if (mockMode) {
                    MockBadge()
                } else {
                    Surface(
                        color = PrimarySoft,
                        shape = RoundedCornerShape(999.dp),
                    ) {
                        Text(
                            "本机 LiteRT",
                            modifier = Modifier.padding(horizontal = 9.dp, vertical = 4.dp),
                            color = Primary,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
                }
            }
            if (
                expressionEnabled &&
                !mockMode &&
                cameraPermissionGranted &&
                expressionService is CameraExpressionRecognitionService
            ) {
                AndroidView(
                    factory = { previewContext ->
                        PreviewView(previewContext).apply {
                            scaleType = PreviewView.ScaleType.FILL_CENTER
                            implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                            expressionService.bindCamera(lifecycleOwner, this)
                        }
                    },
                    update = { expressionService.bindCamera(lifecycleOwner, it) },
                    onRelease = { expressionService.unbindCamera() },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(164.dp)
                        .clip(RoundedCornerShape(10.dp)),
                )
            }
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Box(
                    modifier = Modifier
                        .size(44.dp)
                        .clip(CircleShape)
                        .background(PrimarySoft),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        expressionStatusIcon(expressionStatus),
                        null,
                        tint = Primary,
                        modifier = Modifier.size(28.dp),
                    )
                }
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        expressionStatusTitle(
                            enabled = expressionEnabled,
                            status = expressionStatus,
                            result = expressionResult,
                        ),
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 14.sp,
                    )
                    Text(
                        expressionStatusDetail(
                            enabled = expressionEnabled,
                            permissionDenied = permissionDenied,
                            status = expressionStatus,
                            result = expressionResult,
                        ),
                        color = if (expressionStatus is ExpressionServiceStatus.Error) Danger else Muted,
                        fontSize = 11.sp,
                    )
                }
            }
            Button(
                onClick = {
                    if (expressionEnabled) {
                        expressionEnabled = false
                        coroutineScope.launch { expressionService.stop() }
                    } else if (cameraPermissionGranted) {
                        permissionDenied = false
                        expressionEnabled = true
                        coroutineScope.launch {
                            expressionService.initialize()
                            if (timerRunning) expressionService.start()
                        }
                    } else {
                        permissionLauncher.launch(Manifest.permission.CAMERA)
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = expressionStatus !is ExpressionServiceStatus.Initializing,
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (expressionEnabled) PrimarySoft else Primary,
                    contentColor = if (expressionEnabled) Primary else MaterialTheme.colorScheme.onPrimary,
                ),
                shape = RoundedCornerShape(8.dp),
            ) {
                if (expressionStatus is ExpressionServiceStatus.Initializing) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                        color = Primary,
                    )
                } else {
                    Icon(
                        if (expressionEnabled) Icons.Default.VideocamOff else Icons.Default.Videocam,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                }
                Spacer(Modifier.width(6.dp))
                Text(
                    when {
                        expressionStatus is ExpressionServiceStatus.Initializing -> "正在加载本机模型"
                        expressionEnabled -> "关闭表情辅助"
                        else -> "开启表情辅助"
                    },
                )
            }
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(8.dp))
                    .background(AlertInfoBg)
                    .padding(10.dp, 12.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(Icons.Default.Info, null, tint = AlertInfoText, modifier = Modifier.size(16.dp))
                Text(
                    "低置信度时会显示\"暂时无法稳定判断当前表情\"，且不会触发情绪安慰。",
                    color = AlertInfoText, fontSize = 12.sp
                )
            }
        }

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .background(Surface)
                .border(1.dp, Line, RoundedCornerShape(10.dp))
                .padding(14.dp)
                .enterAnimation(delayMs = 120, enabled = !reduceMotion),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text("本周学习记录", style = MaterialTheme.typography.titleSmall)
            val heights = listOf(32, 56, 45, 80, 62, 90, 40)
            val labels = listOf("一", "二", "三", "四", "五", "六", "日")
            val barColors = listOf(
                Primary.copy(alpha = 0.4f), Primary.copy(alpha = 0.4f), Primary.copy(alpha = 0.4f),
                Primary.copy(alpha = 0.75f), Primary.copy(alpha = 0.5f),
                Primary.copy(alpha = 0.85f), Primary.copy(alpha = 0.4f),
            )
            Row(
                modifier = Modifier.fillMaxWidth().height(80.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                heights.forEachIndexed { i, h ->
                    Column(
                        modifier = Modifier.weight(1f),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .weight(1f),
                            contentAlignment = Alignment.BottomCenter
                        ) {
                            AnimatedBar(
                                fraction = h / 100f,
                                delayMs = i * 80,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .fillMaxHeight()
                                    .clip(RoundedCornerShape(4.dp)),
                                color = barColors[i],
                            )
                        }
                        Text(labels[i], fontSize = 10.sp, color = Muted)
                    }
                }
            }
        }
    }
}

private fun expressionStatusIcon(status: ExpressionServiceStatus) = when (status) {
    ExpressionServiceStatus.NoFace -> Icons.Default.FaceRetouchingOff
    ExpressionServiceStatus.LowConfidence -> Icons.AutoMirrored.Filled.HelpOutline
    is ExpressionServiceStatus.Error -> Icons.Default.ErrorOutline
    ExpressionServiceStatus.Initializing -> Icons.Default.Downloading
    ExpressionServiceStatus.Off -> Icons.Default.VisibilityOff
    else -> Icons.Default.EmojiEmotions
}

private fun expressionStatusTitle(
    enabled: Boolean,
    status: ExpressionServiceStatus,
    result: ExpressionResult,
): String = when {
    !enabled -> "表情辅助已关闭"
    status is ExpressionServiceStatus.Error -> "本机识别暂不可用"
    status == ExpressionServiceStatus.Initializing -> "正在加载本机模型"
    status == ExpressionServiceStatus.Paused -> "开始专注后才会分析画面"
    status == ExpressionServiceStatus.NoFace || result.label == ExpressionLabel.NO_FACE ->
        "画面中暂未检测到人脸"
    status == ExpressionServiceStatus.LowConfidence || result.label == ExpressionLabel.UNKNOWN ->
        "暂时无法稳定判断当前表情"
    !result.isStable -> "正在观察连续画面…"
    else -> "当前表情可能偏${result.label.chineseName()}"
}

private fun expressionStatusDetail(
    enabled: Boolean,
    permissionDenied: Boolean,
    status: ExpressionServiceStatus,
    result: ExpressionResult,
): String = when {
    permissionDenied -> "未获得摄像头权限；可再次点击并在系统提示中授权。"
    !enabled -> "仅在你主动开启且进入专注时，在本机内存中处理画面。"
    status is ExpressionServiceStatus.Error -> status.message
    result.isStable -> "稳定置信度 ${(result.confidence * 100).toInt()}%；结果仅供辅助参考，不代表心理状态或医学判断。"
    else -> "摄像头画面不保存、不上传，也不会写入日志。"
}

private fun ExpressionLabel.chineseName(): String = when (this) {
    ExpressionLabel.HAPPY -> "愉快"
    ExpressionLabel.NEUTRAL -> "中性"
    ExpressionLabel.SAD -> "低落"
    ExpressionLabel.ANGRY -> "生气"
    ExpressionLabel.FEAR -> "紧张"
    ExpressionLabel.SURPRISE -> "惊讶"
    ExpressionLabel.DISGUST -> "厌恶"
    ExpressionLabel.UNKNOWN -> "不确定"
    ExpressionLabel.NO_FACE -> "无脸"
}


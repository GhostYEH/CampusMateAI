package com.example.campusai.ui.screens.counselor

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.view.PreviewView
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.expression.CameraExpressionRecognitionService
import com.example.campusai.data.expression.ExpressionServiceStatus
import com.example.campusai.data.expression.ObservableExpressionRecognitionService
import com.example.campusai.data.model.ChatMessage
import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.ExpressionResult
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.MockBadge
import com.example.campusai.ui.components.ModeBadge
import com.example.campusai.ui.components.TypingIndicator
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.components.slideInAnimation
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

@Composable
fun CounselorScreen(repository: AppRepository) {
    val mockMode by repository.mockMode.collectAsState()
    val reduceMotion by repository.reduceMotion.collectAsState()
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()
    val expressionService = remember(mockMode) {
        repository.createExpressionRecognitionService(mockMode)
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
    val cameraPermissionGranted = mockMode || ContextCompat.checkSelfPermission(
        context,
        Manifest.permission.CAMERA,
    ) == PackageManager.PERMISSION_GRANTED
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        permissionDenied = !granted
        if (granted) expressionEnabled = true
    }
    val disposalScope = remember(expressionService) {
        kotlinx.coroutines.CoroutineScope(
            kotlinx.coroutines.SupervisorJob() + kotlinx.coroutines.Dispatchers.Main.immediate,
        )
    }
    val listState = rememberLazyListState()
    var input by remember { mutableStateOf("") }
    var sending by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(expressionEnabled, expressionService) {
        if (expressionEnabled) {
            expressionService.initialize()
            expressionService.start()
        } else if (expressionStatus !is ExpressionServiceStatus.Off) {
            expressionService.stop()
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

    var messages by remember {
        mutableStateOf(
            listOf(
                ChatMessage(
                    "assistant",
                    "你好，我是 AI 导员小夏。课程流程、奖助政策、校园服务，都可以来问我。当前回答来自 Mock 知识库，仅供演示参考。",
                ),
            ),
        )
    }

    fun sendMessage(text: String) {
        val question = text.trim()
        if (question.isEmpty() || sending) return
        val expressionAtSend = expressionResult.takeIf {
            expressionEnabled &&
                it.isStable &&
                it.confidence >= 0.60 &&
                it.label != ExpressionLabel.UNKNOWN &&
                it.label != ExpressionLabel.NO_FACE
        }
        scope.launch {
            messages = messages + ChatMessage("user", question, expressionAtSend?.label)
            input = ""
            sending = true
            error = null
            try {
                messages = messages + ChatMessage(
                    "assistant",
                    repository.chat(question, expressionAtSend),
                )
            } catch (_: Exception) {
                error = "暂时无法连接校园知识库，请检查网络后重试。"
            } finally {
                sending = false
            }
        }
    }

    Column(Modifier.fillMaxSize().background(Background)) {
        LazyColumn(
            modifier = Modifier.weight(1f),
            state = listState,
            contentPadding = PaddingValues(16.dp, 12.dp, 16.dp, 18.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item { CounselorHeader(mockMode) }
            item { CounselorHero(reduceMotion, mockMode) }
            item {
                CounselorExpressionPanel(
                    enabled = expressionEnabled,
                    mockMode = mockMode,
                    permissionDenied = permissionDenied,
                    cameraPermissionGranted = cameraPermissionGranted,
                    status = expressionStatus,
                    result = expressionResult,
                    reduceMotion = reduceMotion,
                    expressionService = expressionService,
                    lifecycleOwner = lifecycleOwner,
                    onToggle = {
                        if (expressionEnabled) {
                            expressionEnabled = false
                            scope.launch { expressionService.stop() }
                        } else if (cameraPermissionGranted) {
                            permissionDenied = false
                            expressionEnabled = true
                        } else {
                            permissionLauncher.launch(Manifest.permission.CAMERA)
                        }
                    },
                )
            }
            item {
                Text("你可以这样问", fontSize = 14.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(9.dp))
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(
                        listOf(
                            "奖学金申请需要什么材料？",
                            "课程重修怎么办理？",
                            "校园卡丢了怎么补办？",
                        ),
                    ) { question ->
                        SuggestionChip(
                            onClick = { sendMessage(question) },
                            label = { Text(question, maxLines = 1) },
                            icon = { Icon(Icons.Default.AutoAwesome, null, Modifier.size(16.dp)) },
                            shape = RoundedCornerShape(12.dp),
                            colors = SuggestionChipDefaults.suggestionChipColors(
                                containerColor = Surface,
                                labelColor = TextPrimary,
                                iconContentColor = Primary,
                            ),
                            border = SuggestionChipDefaults.suggestionChipBorder(
                                enabled = true,
                                borderColor = Line,
                            ),
                        )
                    }
                }
            }
            items(messages) { message ->
                ChatBubble(message, reduceMotion)
            }
            if (sending) {
                item { TypingBubble(reduceMotion) }
            }
            error?.let { message ->
                item {
                    Row(
                        Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp))
                            .background(AlertErrorBg).padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Icon(Icons.Default.CloudOff, null, tint = AlertErrorText, modifier = Modifier.size(18.dp))
                        Text(message, color = AlertErrorText, fontSize = 12.sp, modifier = Modifier.weight(1f))
                        TextButton(onClick = { error = null }) { Text("知道了") }
                    }
                }
            }
        }
        ChatComposer(
            value = input,
            sending = sending,
            onValueChange = { input = it },
            onSend = { sendMessage(input) },
        )
    }

    LaunchedEffect(messages.size, sending) {
        if (!reduceMotion && messages.isNotEmpty()) {
            listState.animateScrollToItem(listState.layoutInfo.totalItemsCount.coerceAtLeast(1) - 1)
        }
    }
}

@Composable
@Composable
private fun CounselorExpressionPanel(
    enabled: Boolean,
    mockMode: Boolean,
    permissionDenied: Boolean,
    cameraPermissionGranted: Boolean,
    status: ExpressionServiceStatus,
    result: ExpressionResult,
    reduceMotion: Boolean,
    expressionService: com.example.campusai.data.expression.ExpressionRecognitionService,
    lifecycleOwner: androidx.lifecycle.LifecycleOwner,
    onToggle: () -> Unit,
) {
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(20.dp))
            .background(Surface)
            .border(1.dp, Line, RoundedCornerShape(20.dp))
            .padding(14.dp)
            .enterAnimation(enabled = !reduceMotion),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text("表情辅助", fontWeight = FontWeight.Bold, fontSize = 15.sp)
                Text(
                    "只发送稳定的表情标签，不上传摄像头画面",
                    color = Muted,
                    fontSize = 11.sp,
                )
            }
            Surface(color = PrimarySoft, shape = RoundedCornerShape(999.dp)) {
                Text(
                    if (mockMode) "Mock CNN" else "本机 LiteRT",
                    modifier = Modifier.padding(horizontal = 9.dp, vertical = 4.dp),
                    color = Primary,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        }
        if (enabled && !mockMode && cameraPermissionGranted &&
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
                    .height(150.dp)
                    .clip(RoundedCornerShape(12.dp)),
            )
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                when (status) {
                    ExpressionServiceStatus.NoFace -> Icons.Default.FaceRetouchingOff
                    ExpressionServiceStatus.LowConfidence -> Icons.Default.HelpOutline
                    is ExpressionServiceStatus.Error -> Icons.Default.ErrorOutline
                    ExpressionServiceStatus.Initializing -> Icons.Default.Downloading
                    ExpressionServiceStatus.Off -> Icons.Default.VisibilityOff
                    else -> Icons.Default.EmojiEmotions
                },
                contentDescription = null,
                tint = Primary,
                modifier = Modifier.size(23.dp),
            )
            Spacer(Modifier.width(9.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    expressionTitle(enabled, status, result),
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 13.sp,
                )
                Text(
                    when {
                        permissionDenied -> "未获得摄像头权限，可再次点击开启"
                        !enabled -> "关闭后不分析表情，消息也不会附带表情信号"
                        status is ExpressionServiceStatus.Error -> status.message
                        result.isStable -> "置信度 ${(result.confidence * 100).toInt()}%，仅供辅助参考"
                        else -> "正在观察连续画面，未达到稳定条件"
                    },
                    color = if (status is ExpressionServiceStatus.Error) Danger else Muted,
                    fontSize = 10.sp,
                )
            }
        }
        Button(
            onClick = onToggle,
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(10.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = if (enabled) PrimarySoft else Primary,
                contentColor = if (enabled) Primary else Color.White,
            ),
        ) {
            Icon(
                if (enabled) Icons.Default.VideocamOff else Icons.Default.Videocam,
                contentDescription = null,
                modifier = Modifier.size(17.dp),
            )
            Spacer(Modifier.width(6.dp))
            Text(if (enabled) "关闭表情辅助" else "开启表情辅助")
        }
        Text(
            "CNN 识别的是可观察到的面部表情，不代表心理状态或医学判断。",
            color = Muted,
            fontSize = 10.sp,
        )
    }
}

private fun expressionTitle(
    enabled: Boolean,
    status: ExpressionServiceStatus,
    result: ExpressionResult,
): String = when {
    !enabled -> "表情辅助已关闭"
    status is ExpressionServiceStatus.Error -> "本机识别暂不可用"
    status == ExpressionServiceStatus.Initializing -> "正在加载本机模型"
    status == ExpressionServiceStatus.NoFace || result.label == ExpressionLabel.NO_FACE ->
        "画面中暂未检测到人脸"
    status == ExpressionServiceStatus.LowConfidence || result.label == ExpressionLabel.UNKNOWN ->
        "暂时无法稳定判断当前表情"
    !result.isStable -> "正在观察连续画面"
    else -> "当前表情可能偏${result.label.displayName()}"
}

private fun ExpressionLabel.displayName(): String = when (this) {
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

@Composable
private fun CounselorHeader(mockMode: Boolean) {
    Row(Modifier.fillMaxWidth(), Arrangement.SpaceBetween, Alignment.CenterVertically) {
        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text("AI 导员", fontSize = 26.sp, fontWeight = FontWeight.ExtraBold)
            Text("校园问题，随时来聊一聊", color = Muted, fontSize = 13.sp)
        }
        ModeBadge(mockMode)
    }
}

@Composable
private fun CounselorHero(reduceMotion: Boolean) {
    Box(
        Modifier.fillMaxWidth().height(140.dp).clip(RoundedCornerShape(24.dp))
            .background(Surface).border(1.dp, Line, RoundedCornerShape(24.dp))
            .enterAnimation(enabled = !reduceMotion),
    ) {
        Row(
            Modifier.fillMaxSize().padding(20.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(15.dp),
        ) {
            Box(
                Modifier.size(56.dp).clip(RoundedCornerShape(18.dp)).background(PrimarySoft),
                contentAlignment = Alignment.Center,
            ) { Icon(Icons.Default.SupportAgent, null, tint = Primary, modifier = Modifier.size(30.dp)) }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("校园事务助手", color = TextPrimary, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                    MockBadge()
                }
                Text("帮你整理办事流程、材料和下一步", color = Muted, fontSize = 12.sp)
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                    Box(Modifier.size(7.dp).clip(CircleShape).background(Success))
                    Text("Mock 知识库在线 · 结果仅供演示", color = Muted, fontSize = 10.sp)
                }
            }
        }
        Box(
            Modifier.align(Alignment.BottomStart).padding(start = 20.dp)
                .width(52.dp).height(3.dp).clip(CircleShape).background(Accent),
        )
    }
}

@Composable
private fun ChatBubble(message: ChatMessage, reduceMotion: Boolean) {
    val isUser = message.role == "user"
    Row(
        Modifier.fillMaxWidth().slideInAnimation(fromLeft = !isUser, enabled = !reduceMotion),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
        verticalAlignment = Alignment.Bottom,
    ) {
        if (!isUser) {
            Box(
                Modifier.size(30.dp).clip(RoundedCornerShape(10.dp)).background(RobotAvatarBg),
                contentAlignment = Alignment.Center,
            ) { Icon(Icons.Default.SmartToy, null, tint = Primary, modifier = Modifier.size(17.dp)) }
            Spacer(Modifier.width(7.dp))
        }
        Column(
            Modifier.widthIn(max = 292.dp).clip(
                if (isUser) RoundedCornerShape(19.dp, 19.dp, 5.dp, 19.dp)
                else RoundedCornerShape(19.dp, 19.dp, 19.dp, 5.dp),
            ).background(if (isUser) Primary else Surface)
                .then(if (isUser) Modifier else Modifier.border(1.dp, Line, RoundedCornerShape(19.dp)))
                .padding(horizontal = 14.dp, vertical = 12.dp),
        ) {
            Text(
                message.text,
                color = if (isUser) Color.White else TextPrimary,
                fontSize = 13.sp,
                lineHeight = 20.sp,
            )
            if (!isUser) {
                Spacer(Modifier.height(7.dp))
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    Icon(Icons.Default.MenuBook, null, tint = Muted, modifier = Modifier.size(12.dp))
                    Text("Mock 校园知识库", color = Muted, fontSize = 9.sp)
                }
            }
        }
    }
}

@Composable
private fun TypingBubble(reduceMotion: Boolean) {
    Row(verticalAlignment = Alignment.Bottom) {
        Box(
            Modifier.size(30.dp).clip(RoundedCornerShape(10.dp)).background(RobotAvatarBg),
            contentAlignment = Alignment.Center,
        ) { Icon(Icons.Default.SmartToy, null, tint = Primary, modifier = Modifier.size(17.dp)) }
        Spacer(Modifier.width(7.dp))
        Row(
            Modifier.clip(RoundedCornerShape(19.dp, 19.dp, 19.dp, 5.dp)).background(Surface)
                .border(1.dp, Line, RoundedCornerShape(19.dp)).padding(horizontal = 14.dp, vertical = 13.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            TypingIndicator(dotColor = Primary, enabled = !reduceMotion)
            Text("正在查找校园知识库", color = Muted, fontSize = 12.sp)
        }
    }
}

@Composable
private fun ChatComposer(
    value: String,
    sending: Boolean,
    onValueChange: (String) -> Unit,
    onSend: () -> Unit,
) {
    Column(
        Modifier.fillMaxWidth().background(Surface).border(1.dp, Line)
            .navigationBarsPadding().imePadding().padding(12.dp, 10.dp),
        verticalArrangement = Arrangement.spacedBy(7.dp),
    ) {
        Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(9.dp)) {
            OutlinedTextField(
                value = value,
                onValueChange = onValueChange,
                modifier = Modifier.weight(1f),
                placeholder = { Text("输入你的校园事务问题…", fontSize = 13.sp) },
                maxLines = 4,
                shape = RoundedCornerShape(16.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Primary,
                    unfocusedBorderColor = InputBorder,
                ),
            )
            FilledIconButton(
                onClick = onSend,
                enabled = value.isNotBlank() && !sending,
                modifier = Modifier.size(50.dp),
                shape = RoundedCornerShape(16.dp),
                colors = IconButtonDefaults.filledIconButtonColors(
                    containerColor = Primary,
                    contentColor = Color.White,
                ),
            ) { Icon(if (sending) Icons.Default.HourglassTop else Icons.Default.Send, "发送") }
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
            Icon(Icons.Default.Shield, null, tint = Success, modifier = Modifier.size(13.dp))
            Text("仅提供校园事务辅助，不替代学校正式通知或专业咨询", color = Muted, fontSize = 9.sp)
        }
    }
}

package com.example.campusai.ui.screens.counselor

import com.example.campusai.ui.components.GlassButton as Button
import com.example.campusai.ui.components.GlassTextButton as TextButton

import android.Manifest
import android.app.ActivityManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.Image
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.VolumeOff
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.core.content.ContextCompat
import com.example.campusai.BuildConfig
import com.example.campusai.R
import com.example.campusai.data.expression.CounselorExpressionPolicy
import com.example.campusai.data.expression.ExpressionServiceStatus
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.AgentRuntimeRepository
import com.example.campusai.ui.screens.shell.floatingDockContentBottomPadding
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.yield
import kotlinx.coroutines.launch

private val CpmBlue = Color(0xFF385AF6)
private val CpmViolet = Color(0xFF8152F6)
private val CpmLine = Color(0xFFDDE3FA)

@Composable
fun CounselorScreen(
    repository: AppRepository,
    initialPrompt: String? = null,
    courseId: String? = null,
    courseName: String? = null,
    agentRuntimeRepository: AgentRuntimeRepository? = null,
    onOpenCourseDeepLink: (String) -> Unit = {},
) {
    val initialCourse = remember(courseId, courseName) {
        if (courseId.isNullOrBlank()) null else CpmCourseContext(courseId = courseId, courseName = courseName.orEmpty())
    }
    val factory = remember(repository, initialCourse, agentRuntimeRepository) {
        CounselorViewModelFactory(repository, initialCourse, agentRuntimeRepository)
    }
    val viewModel: CounselorViewModel = viewModel(factory = factory)
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    val accessToken by repository.accessToken.collectAsStateWithLifecycle()
    val session by repository.session.collectAsStateWithLifecycle()
    val mockMode by repository.mockMode.collectAsStateWithLifecycle()
    val assistanceEnabled by repository.learningAssistanceEnabled.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()
    val expressionManager = repository.expressionSessionManager
    val expressionResult by expressionManager.result.collectAsStateWithLifecycle()
    val observationActive by expressionManager.observationActive.collectAsStateWithLifecycle()
    val expressionStatus by expressionManager.status.collectAsStateWithLifecycle()
    var consentDismissed by rememberSaveable { mutableStateOf(false) }
    var permissionRequested by rememberSaveable { mutableStateOf(false) }
    var cameraPermissionGranted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED,
        )
    }
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        cameraPermissionGranted = granted
    }
    LaunchedEffect(initialPrompt) {
        if (!viewModel.uiState.value.chatActive) initialPrompt?.takeIf(String::isNotBlank)?.let(viewModel::send)
    }
    // 身份变化（登录 / 换账号 / 登出）时，课堂任务的恢复记录必须立即作废：
    // 否则新账号会恢复出上一个账号的 job 与深链。
    val classroomIdentity = session?.accountId?.takeIf(String::isNotBlank)
        ?: session?.studentId?.takeIf(String::isNotBlank)
        ?: ""
    LaunchedEffect(accessToken, classroomIdentity) {
        if (accessToken.isNullOrBlank()) viewModel.onClassroomSessionEnded()
        else viewModel.onClassroomIdentityChanged(classroomIdentity)
    }
    DisposableEffect(viewModel) {
        viewModel.resumeClassroomObservation()
        onDispose { viewModel.stopClassroomObservation() }
    }
    LaunchedEffect(expressionResult, observationActive) {
        viewModel.updateExpression(
            expressionResult?.takeIf { observationActive }?.let(CounselorExpressionPolicy::usableOrNull),
        )
    }
    DisposableEffect(lifecycleOwner) {
        expressionManager.attachLifecycle(lifecycleOwner)
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> scope.launch {
                    expressionManager.updateCounselorEligibility(foreground = true)
                }
                Lifecycle.Event.ON_PAUSE -> scope.launch {
                    expressionManager.updateCounselorEligibility(foreground = false)
                }
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            scope.launch {
                expressionManager.updateCounselorEligibility(visible = false, foreground = false)
                expressionManager.detachLifecycle()
            }
        }
    }
    LaunchedEffect(assistanceEnabled, cameraPermissionGranted) {
        if (assistanceEnabled && !cameraPermissionGranted && !permissionRequested) {
            permissionRequested = true
            permissionLauncher.launch(Manifest.permission.CAMERA)
        }
        expressionManager.updateCounselorEligibility(
            enabled = assistanceEnabled,
            permissionGranted = cameraPermissionGranted,
            visible = true,
            foreground = true,
        )
    }
    CpmCounselorContent(
        state = state,
        reduceMotion = reduceMotion,
        accessToken = accessToken.orEmpty(),
        mockMode = mockMode,
        expressionEnabled = assistanceEnabled,
        expressionPermissionGranted = cameraPermissionGranted,
        expressionStatus = expressionStatus,
        hasUsableExpression = observationActive && CounselorExpressionPolicy.isUsable(expressionResult),
        courseContext = state.courseContext,
        classroomProposal = state.classroomProposal,
        classroomJob = state.classroomJob,
        onInputChange = viewModel::updateInput,
        onSend = viewModel::send,
        onAsk = viewModel::send,
        onShuffle = viewModel::shuffleRecommendations,
        onRetry = viewModel::retryLast,
        onPlayback = viewModel::sendPlaybackCommand,
        onConfirmClassroom = viewModel::confirmClassroomProposal,
        onApproveClassroom = viewModel::approveClassroomProposal,
        onRejectClassroom = viewModel::rejectClassroomProposal,
        onOpenCourseDeepLink = { deepLink -> onOpenCourseDeepLink(deepLink) },
    )
    if (!assistanceEnabled && !consentDismissed) {
        AlertDialog(
            onDismissRequest = { consentDismissed = true },
            title = { Text("启用情绪陪伴") },
            text = { Text("CPM 可在本机使用前置摄像头识别可见表情，用于调整问候和回答语气。画面不上传、不保存，退出本页即停止。") },
            confirmButton = {
                TextButton(onClick = { scope.launch { repository.setLearningAssistanceEnabled(true) } }) {
                    Text("同意并启用")
                }
            },
            dismissButton = {
                TextButton(onClick = { consentDismissed = true }) { Text("暂不启用") }
            },
        )
    }
}

@Composable
private fun CpmCounselorContent(
    state: CpmCounselorUiState,
    reduceMotion: Boolean,
    accessToken: String,
    mockMode: Boolean,
    expressionEnabled: Boolean,
    expressionPermissionGranted: Boolean,
    expressionStatus: ExpressionServiceStatus,
    hasUsableExpression: Boolean,
    courseContext: CpmCourseContext?,
    classroomProposal: com.example.campusai.data.remote.agent.InteractiveClassroomProposalDto?,
    classroomJob: com.example.campusai.data.classroom.ClassroomJobState,
    onInputChange: (String) -> Unit,
    onSend: () -> Unit,
    onAsk: (String) -> Unit,
    onShuffle: () -> Unit,
    onRetry: () -> Unit,
    onPlayback: (DigitalHumanCommand) -> Unit,
    onConfirmClassroom: () -> Unit,
    onApproveClassroom: () -> Unit,
    onRejectClassroom: () -> Unit,
    onOpenCourseDeepLink: (String) -> Unit,
) {
    val listState = rememberLazyListState()
    LaunchedEffect(state.messages.size, state.messages.lastOrNull()?.content?.length) {
        if (state.chatActive) {
            yield()
            val last = listState.layoutInfo.totalItemsCount - 1
            if (last >= 0) {
                if (reduceMotion) listState.scrollToItem(last) else listState.animateScrollToItem(last)
            }
        }
    }

    Box(
        Modifier.fillMaxSize()
            .padding(bottom = floatingDockContentBottomPadding(
                WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding(),
            )),
    ) {
        Image(
            painter = painterResource(R.drawable.cpm_campus_dreamscape_v1),
            contentDescription = null,
            modifier = Modifier.matchParentSize(),
            contentScale = ContentScale.Crop,
            alpha = 0.74f,
        )
        Box(
            Modifier.matchParentSize().background(
                Brush.verticalGradient(
                    listOf(Color(0x26FFFFFF), Color(0x66FFFFFF), Color(0xCCF7FAFF)),
                ),
            ),
        )
        Column(Modifier.align(Alignment.TopCenter).fillMaxSize().widthIn(max = 760.dp)) {
            LazyColumn(
                modifier = Modifier.weight(1f),
                state = listState,
                contentPadding = PaddingValues(18.dp, 20.dp, 18.dp, 16.dp),
                verticalArrangement = Arrangement.spacedBy(18.dp),
            ) {
                item("brand") {
                    AnimatedVisibility(
                        visible = !state.chatActive,
                        enter = fadeIn(),
                        exit = fadeOut(tween(if (reduceMotion) 0 else 180)) + shrinkVertically(),
                    ) { CpmHeader(mockMode) }
                }
                if (courseContext != null) {
                    item("course-context") {
                        CpmCourseContextTag(courseName = courseContext.courseName.ifBlank { courseContext.courseId })
                    }
                    classroomProposal?.let { proposal ->
                        item("classroom-proposal") {
                            CpmInteractiveClassroomProposalCard(
                                proposal = proposal,
                                job = classroomJob,
                                onConfirm = onConfirmClassroom,
                                onApprove = onApproveClassroom,
                                onReject = onRejectClassroom,
                                onOpenDeepLink = onOpenCourseDeepLink,
                            )
                        }
                    }
                }
                item("expression-status") {
                    ExpressionPrivacyStatus(
                        enabled = expressionEnabled,
                        permissionGranted = expressionPermissionGranted,
                        status = expressionStatus,
                        hasUsableSignal = hasUsableExpression,
                    )
                }
                item("digital-human") {
                    CpmDigitalHumanCard(
                        sending = state.sending,
                        speechText = state.speechText,
                        speechRequestId = state.speechRequestId,
                        playbackCommand = state.playbackCommand,
                        playbackCommandId = state.playbackCommandId,
                        accessToken = accessToken,
                        reduceMotion = reduceMotion,
                        onPlayback = onPlayback,
                    )
                }
                item("recommendations") {
                    AnimatedVisibility(
                        visible = !state.chatActive,
                        enter = fadeIn() + slideInVertically { it / 4 },
                        exit = fadeOut(tween(if (reduceMotion) 0 else 190)) + slideOutVertically { -it / 5 } + shrinkVertically(),
                    ) { CpmRecommendations(state.recommendations, onAsk, onShuffle) }
                }
                items(state.messages, key = CpmChatMessage::id) { message ->
                    CpmMessageBubble(message, state.sending, onRetry)
                }
                item("tail") { Spacer(Modifier.height(2.dp)) }
            }
            CpmComposer(state.input, state.sending, onInputChange, onSend)
        }
    }
}

@Composable
private fun CpmCourseContextTag(courseName: String) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Color(0xCCFFFFFF))
            .border(1.dp, CpmLine, RoundedCornerShape(16.dp)).padding(horizontal = 13.dp, vertical = 9.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Default.AutoAwesome, null, tint = CpmViolet, modifier = Modifier.size(16.dp))
        Text("  正在围绕《$courseName》为你解答", color = TextPrimary, fontSize = 12.sp)
    }
}

@Composable
private fun CpmInteractiveClassroomProposalCard(
    proposal: com.example.campusai.data.remote.agent.InteractiveClassroomProposalDto,
    job: com.example.campusai.data.classroom.ClassroomJobState,
    onConfirm: () -> Unit,
    onApprove: () -> Unit,
    onReject: () -> Unit,
    onOpenDeepLink: (String) -> Unit,
) {
    val phase = job.phase
    Column(
        Modifier.fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(Color(0xF2FFF8F0))
            .border(1.dp, Color(0xFFF2D9B8), RoundedCornerShape(16.dp))
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(7.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.School, null, tint = Color(0xFFE28A3C), modifier = Modifier.size(18.dp))
            Text("CPM 推荐一节互动课堂", Modifier.padding(start = 8.dp), fontWeight = FontWeight.Bold, color = TextPrimary)
        }
        Text("${proposal.courseName.ifBlank { proposal.courseId }} · ${proposal.modeLabel.ifBlank { proposal.mode }}", color = Muted, fontSize = 11.sp)
        if (proposal.intentNote.isNotBlank()) Text(proposal.intentNote, color = Muted, fontSize = 11.sp, lineHeight = 16.sp)
        if (!proposal.available) {
            Text("互动课堂当前不可用${proposal.reason?.let { "：$it" }.orEmpty()}。你仍可以继续文字提问。", color = Color(0xFFB26A1F), fontSize = 11.sp)
        }
        when (phase) {
            com.example.campusai.data.classroom.JobPhase.CREATING_JOB -> Text("正在提交生成请求…", color = CpmBlue, fontSize = 11.sp)
            com.example.campusai.data.classroom.JobPhase.QUEUED -> Text("已排队，正在准备这节课。", color = CpmBlue, fontSize = 11.sp)
            com.example.campusai.data.classroom.JobPhase.RUNNING -> Text("正在生成课堂内容…", color = CpmBlue, fontSize = 11.sp)
            com.example.campusai.data.classroom.JobPhase.AWAITING_APPROVAL -> Text("已准备好，需要你确认后才会调用生成服务。", color = Color(0xFFB26A1F), fontSize = 11.sp)
            com.example.campusai.data.classroom.JobPhase.APPROVING -> Text("正在确认…", color = CpmBlue, fontSize = 11.sp)
            com.example.campusai.data.classroom.JobPhase.SUCCEEDED -> {
                if (job.deepLink.isNullOrBlank()) Text("课堂已生成，正在获取课程详情入口…", color = CpmBlue, fontSize = 11.sp)
                else Text("课堂已生成。", color = Color(0xFF247A52), fontSize = 11.sp)
            }
            com.example.campusai.data.classroom.JobPhase.FAILED -> Text("生成失败${job.error.takeIf { it.isNotBlank() }?.let { "：$it" }.orEmpty()}", color = Color(0xFFC63D4F), fontSize = 11.sp)
            com.example.campusai.data.classroom.JobPhase.REJECTED -> Text("已拒绝，本次不会生成课堂。", color = Muted, fontSize = 11.sp)
            com.example.campusai.data.classroom.JobPhase.EXPIRED -> Text("确认已过期，请重新发起。", color = Color(0xFFC63D4F), fontSize = 11.sp)
            com.example.campusai.data.classroom.JobPhase.IDLE -> Unit
        }
        if (job.error.isNotBlank() && phase != com.example.campusai.data.classroom.JobPhase.FAILED) {
            Text(job.error, color = Color(0xFFC63D4F), fontSize = 11.sp)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            if (job.canConfirm) {
                Button(
                    onClick = onConfirm,
                    enabled = proposal.available,
                    colors = ButtonDefaults.buttonColors(containerColor = CpmBlue),
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 7.dp),
                ) { Text(if (phase == com.example.campusai.data.classroom.JobPhase.FAILED) "重新发起" else "确认生成", fontSize = 12.sp) }
            }
            if (job.canApprove) {
                Button(onClick = onApprove, colors = ButtonDefaults.buttonColors(containerColor = CpmBlue), contentPadding = PaddingValues(horizontal = 12.dp, vertical = 7.dp)) { Text("批准并开始生成", fontSize = 12.sp) }
                TextButton(onClick = onReject, contentPadding = PaddingValues(horizontal = 8.dp)) { Text("不用了", color = Muted, fontSize = 12.sp) }
            }
            if (!job.deepLink.isNullOrBlank() && phase == com.example.campusai.data.classroom.JobPhase.SUCCEEDED) {
                TextButton(onClick = { onOpenDeepLink(job.deepLink) }, contentPadding = PaddingValues(horizontal = 8.dp)) { Text("去课程详情", color = CpmBlue, fontSize = 12.sp) }
            }
        }
    }
}

@Composable
private fun ExpressionPrivacyStatus(
    enabled: Boolean,
    permissionGranted: Boolean,
    status: ExpressionServiceStatus,
    hasUsableSignal: Boolean,
) {
    val (text, color) = when {
        !enabled -> "情绪陪伴未启用" to Muted
        !permissionGranted -> "等待摄像头权限" to Color(0xFFC63D4F)
        hasUsableSignal -> "表情信号稳定 · 仅本机处理" to Color(0xFF247A52)
        status is ExpressionServiceStatus.Error -> "表情识别暂不可用" to Color(0xFFC63D4F)
        else -> "正在本机观察表情 · 画面不上传" to CpmBlue
    }
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Color(0xCCFFFFFF))
            .border(1.dp, Color.White, RoundedCornerShape(18.dp)).padding(horizontal = 13.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Default.Visibility, null, tint = color, modifier = Modifier.size(16.dp))
        Text("  $text", color = color, fontSize = 12.sp)
    }
}

@Composable
private fun CpmHeader(mockMode: Boolean) = Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.Top) {
        Row(verticalAlignment = Alignment.Top) {
            Text("CPM", color = TextPrimary, fontSize = 36.sp, fontWeight = FontWeight.Black)
            Text("✦", color = CpmBlue, fontSize = 23.sp, modifier = Modifier.padding(start = 7.dp, top = 1.dp))
        }
        Row(
            Modifier.padding(top = 8.dp).clip(RoundedCornerShape(20.dp)).background(Color(0xD9FFFFFF))
                .border(1.dp, Color.White, RoundedCornerShape(20.dp)).padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                Modifier.size(8.dp).clip(CircleShape)
                    .background(if (mockMode) CpmViolet else Color(0xFF36B879)),
            )
            Text(
                if (mockMode) "演示模式" else "真实后端在线",
                color = TextPrimary,
                fontSize = 12.sp,
                modifier = Modifier.padding(start = 7.dp),
            )
        }
    }
    Text("校园问题，随时来聊一聊", color = Color(0xFF5D7092), fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
}

@Composable
private fun CpmDigitalHumanCard(
    sending: Boolean,
    speechText: String,
    speechRequestId: Int,
    playbackCommand: DigitalHumanCommand,
    playbackCommandId: Int,
    accessToken: String,
    reduceMotion: Boolean,
    onPlayback: (DigitalHumanCommand) -> Unit,
) {
    // Keep the live character visible while chatting. The recommendations may
    // leave, but the avatar and all three playback controls remain full-size.
    val compact = false
    val duration = if (reduceMotion) 0 else 280
    BoxWithConstraints(
        Modifier.fillMaxWidth(),
    ) {
        val metrics = cpmHeroMetrics(maxWidth.value.toInt())
        val cardHeight by animateDpAsState(if (compact) 78.dp else metrics.cardHeightDp.dp, tween(duration), label = "cardHeight")
        val avatarSize by animateDpAsState(if (compact) 58.dp else metrics.avatarSizeDp.dp, tween(duration), label = "avatarSize")
        val cardRadius by animateDpAsState(if (compact) 24.dp else 28.dp, tween(duration), label = "cardRadius")
        val avatarOverflow = avatarSize * ((metrics.avatarContainerScale - 1f) / 2f)
        Row(
            Modifier.fillMaxWidth().height(cardHeight)
                .shadow(20.dp, RoundedCornerShape(cardRadius), ambientColor = Color(0x1A4B5DAC), spotColor = Color(0x144B5DAC))
                .clip(RoundedCornerShape(cardRadius))
                .background(Color(0xD9FFFFFF))
                .border(1.dp, Color.White, RoundedCornerShape(cardRadius))
                .padding(if (compact) 10.dp else metrics.contentPaddingDp.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(if (compact) 12.dp else metrics.itemGapDp.dp),
        ) {
            Box(
                Modifier.size(avatarSize),
            ) {
                Box(
                    Modifier.fillMaxSize()
                        .background(Brush.radialGradient(listOf(Color.White, Color(0xFFE3E7FF))))
                        .border(2.dp, Color.White, CircleShape),
                ) {
                    key(reduceMotion) {
                        DigitalHumanStage(
                            apiBaseUrl = BuildConfig.API_BASE_URL,
                            accessToken = accessToken,
                            speechText = speechText,
                            speechRequestId = speechRequestId,
                            command = playbackCommand,
                            commandRequestId = playbackCommandId,
                            reduceMotion = reduceMotion,
                        )
                    }
                }
                Box(
                    Modifier.align(Alignment.BottomStart).offset(x = -avatarOverflow - 2.dp, y = 2.dp)
                        .size(metrics.sparkleBadgeSizeDp.dp).shadow(8.dp, CircleShape)
                        .clip(CircleShape).background(Color.White).border(1.dp, Color(0xFFF1F3FF), CircleShape),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        Icons.Default.AutoAwesome,
                        contentDescription = null,
                        tint = CpmBlue,
                        modifier = Modifier.size(20.dp),
                    )
                }
            }
            if (compact) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text("你好，我是CPM", color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.ExtraBold)
                    Text(if (sending) "正在生成回答…" else "尽管提问！", color = if (sending) CpmBlue else Muted, fontSize = 12.sp)
                }
                CpmMiniControl(Icons.AutoMirrored.Filled.VolumeOff, "静音") { onPlayback(DigitalHumanCommand.TOGGLE_MUTE) }
                CpmMiniControl(Icons.Default.PauseCircleOutline, "暂停") { onPlayback(DigitalHumanCommand.TOGGLE_PAUSE) }
            } else {
                Column(Modifier.weight(1f).fillMaxHeight(), verticalArrangement = Arrangement.Center) {
                    Text(
                        "你好，我是 CPM",
                        style = TextStyle(
                            brush = Brush.horizontalGradient(listOf(CpmBlue, CpmViolet)),
                            fontSize = 21.sp,
                            fontWeight = FontWeight.Black,
                        ),
                        maxLines = 1,
                    )
                    Text("你的校园 AI 助手", color = Color(0xFF63779B), fontSize = 16.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 5.dp))
                    Text("无论是学习、生活还是未来规划\n我都在这里，随时为你解答！", color = Color(0xFF627493), fontSize = 13.sp, lineHeight = 19.sp, modifier = Modifier.padding(top = 5.dp, bottom = 10.dp))
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        CpmControl(Icons.AutoMirrored.Filled.VolumeOff, "静音", Modifier.weight(1f), metrics.controlHeightDp) { onPlayback(DigitalHumanCommand.TOGGLE_MUTE) }
                        CpmControl(Icons.Default.PauseCircleOutline, "暂停", Modifier.weight(1f), metrics.controlHeightDp) { onPlayback(DigitalHumanCommand.TOGGLE_PAUSE) }
                        CpmControl(Icons.Default.Replay, "重播", Modifier.weight(1f), metrics.controlHeightDp) { onPlayback(DigitalHumanCommand.REPLAY) }
                    }
                }
            }
        }
    }
}

@Composable
private fun CpmControl(icon: ImageVector, label: String, modifier: Modifier, heightDp: Int, onClick: () -> Unit) {
    Column(
        modifier.height(heightDp.dp).clip(RoundedCornerShape(19.dp)).background(Color(0xEFFFFFFF))
            .border(1.dp, Color.White, RoundedCornerShape(19.dp)).clickable(onClick = onClick),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(icon, label, tint = CpmBlue, modifier = Modifier.size(23.dp))
        Text(label, color = Color(0xFF596785), fontSize = 11.sp, modifier = Modifier.padding(top = 4.dp))
    }
}

@Composable
private fun CpmMiniControl(icon: ImageVector, label: String, onClick: () -> Unit) = FilledIconButton(
    onClick = onClick,
    modifier = Modifier.size(38.dp),
    colors = IconButtonDefaults.filledIconButtonColors(containerColor = Color.White, contentColor = CpmBlue),
) { Icon(icon, label, Modifier.size(20.dp)) }

@Composable
private fun CpmRecommendations(questions: List<CpmPrompt>, onAsk: (String) -> Unit, onShuffle: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("你可以这样问", color = TextPrimary, fontSize = 24.sp, fontWeight = FontWeight.Black)
            Text("✦", color = CpmViolet, fontSize = 16.sp, modifier = Modifier.padding(start = 5.dp, bottom = 7.dp))
            Spacer(Modifier.weight(1f))
            Row(
                Modifier.clip(RoundedCornerShape(20.dp)).background(Color(0xD9FFFFFF)).border(1.dp, Color.White, RoundedCornerShape(20.dp)).clickable(onClick = onShuffle)
                    .padding(horizontal = 10.dp, vertical = 7.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("换一批", color = Muted, fontSize = 13.sp)
                Icon(Icons.Default.Refresh, null, tint = Muted, modifier = Modifier.padding(start = 4.dp).size(17.dp))
            }
        }
        questions.chunked(2).forEach { row ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                row.forEach { question ->
                    Row(
                        Modifier.weight(1f).height(CPM_RECOMMENDATION_CARD_HEIGHT_DP.dp)
                            .shadow(10.dp, RoundedCornerShape(22.dp), ambientColor = Color(0x0F41518C), spotColor = Color(0x0F41518C))
                            .clip(RoundedCornerShape(24.dp)).background(Color(0xEFFFFFFF))
                            .border(1.dp, Color.White, RoundedCornerShape(24.dp)).clickable { onAsk(question.prompt) }.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Box(Modifier.size(44.dp).clip(CircleShape).background(PrimarySoft), contentAlignment = Alignment.Center) {
                            Icon(question.icon, null, tint = CpmBlue, modifier = Modifier.size(23.dp))
                        }
                        Column(Modifier.padding(start = 10.dp).weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(question.label, color = TextPrimary, fontSize = 15.sp, lineHeight = 20.sp, fontWeight = FontWeight.Bold)
                            Text(cpmPromptSupportingCopy(question.id), color = Color(0xFF7183A3), fontSize = 11.sp, lineHeight = 15.sp, maxLines = 2)
                        }
                        Icon(Icons.Default.ChevronRight, null, tint = Muted, modifier = Modifier.size(18.dp))
                    }
                }
            }
        }
    }
}

private fun cpmPromptSupportingCopy(id: String): String = when (id) {
    "freshman" -> "专业选择、学习方法、\n大学生活路线"
    "graduate" -> "结合专业、兴趣和\n未来发展帮你分析"
    "club" -> "找到适合自己的社团，\n丰富大学生活"
    "balance" -> "时间管理、压力调节，\n做更好的自己"
    "internship" -> "从能力准备到简历投递，\n提前梳理节奏"
    "direction" -> "一起拆解迷茫，\n找到下一步方向"
    "friendship" -> "建立舒服且健康的\n同学关系"
    else -> "规划可持续的节奏，\n让学习更有掌控感"
}

@Composable
private fun CpmMessageBubble(message: CpmChatMessage, sending: Boolean, onRetry: () -> Unit) {
    val assistant = message.role == "assistant"
    val clipboard = LocalClipboardManager.current
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (assistant) Arrangement.Start else Arrangement.End, verticalAlignment = Alignment.Bottom) {
        if (assistant) CpmAvatarBadge()
        Column(
            Modifier.widthIn(max = 330.dp).then(
                if (assistant) Modifier.shadow(9.dp, RoundedCornerShape(22.dp), ambientColor = Color(0x12404E7D), spotColor = Color(0x10404E7D))
                    .background(Color(0xF8FFFFFF), RoundedCornerShape(22.dp, 22.dp, 22.dp, 6.dp))
                    .border(1.dp, CpmLine, RoundedCornerShape(22.dp, 22.dp, 22.dp, 6.dp))
                else Modifier.background(Brush.linearGradient(listOf(CpmBlue, CpmViolet)), RoundedCornerShape(22.dp, 22.dp, 6.dp, 22.dp))
            ).padding(horizontal = 15.dp, vertical = 13.dp),
        ) {
            if (assistant && message.status == CpmMessageStatus.GENERATING && message.content.isEmpty()) CpmThinkingText()
            else {
                MarkdownMessage(message.content, if (assistant) TextPrimary else Color.White)
                if (assistant && message.status == CpmMessageStatus.GENERATING) CpmStreamingCursor()
            }
            if (assistant && message.status == CpmMessageStatus.ERROR) {
                Text(message.errorMessage ?: "生成中断", color = AlertErrorText, fontSize = 11.sp, modifier = Modifier.padding(top = 8.dp))
                TextButton(onClick = onRetry, contentPadding = PaddingValues(0.dp)) { Text("重新生成", color = CpmBlue, fontSize = 12.sp) }
            }
            if (assistant && message.status == CpmMessageStatus.COMPLETED && message.content.isNotBlank()) {
                Row(Modifier.padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    TextButton(onClick = { clipboard.setText(AnnotatedString(message.content)) }, contentPadding = PaddingValues(horizontal = 4.dp)) {
                        Icon(Icons.Default.ContentCopy, null, tint = Muted, modifier = Modifier.size(14.dp)); Text(" 复制", color = Muted, fontSize = 11.sp)
                    }
                    TextButton(onClick = onRetry, contentPadding = PaddingValues(horizontal = 4.dp), enabled = !sending) {
                        Icon(Icons.Default.Refresh, null, tint = Muted, modifier = Modifier.size(14.dp)); Text(" 重新生成", color = Muted, fontSize = 11.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun CpmAvatarBadge() = Box(
    Modifier.padding(end = 7.dp).size(32.dp).clip(CircleShape).background(PrimarySoft).border(1.dp, Color.White, CircleShape),
    contentAlignment = Alignment.Center,
) { Text("CPM", color = CpmBlue, fontSize = 8.sp, fontWeight = FontWeight.Black) }

@Composable
private fun CpmThinkingText() {
    val transition = rememberInfiniteTransition(label = "thinking")
    val phase by transition.animateFloat(0f, 1f, infiniteRepeatable(tween(900), RepeatMode.Restart), label = "thinkingPhase")
    Text("正在思考" + when { phase < .33f -> "."; phase < .66f -> ".."; else -> "..." }, color = Muted, fontSize = 13.sp)
}

@Composable
private fun CpmStreamingCursor() {
    val transition = rememberInfiniteTransition(label = "cursor")
    val alpha by transition.animateFloat(.2f, 1f, infiniteRepeatable(tween(520), RepeatMode.Reverse), label = "cursorAlpha")
    Box(Modifier.padding(top = 5.dp).width(2.dp).height(16.dp).background(CpmBlue.copy(alpha = alpha)))
}

@Composable
private fun CpmComposer(value: String, sending: Boolean, onValueChange: (String) -> Unit, onSend: () -> Unit) {
    Column(
        Modifier.fillMaxWidth().imePadding().padding(horizontal = 18.dp, vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(
            Modifier.fillMaxWidth().heightIn(min = CPM_COMPOSER_MIN_HEIGHT_DP.dp)
                .shadow(12.dp, RoundedCornerShape(34.dp), ambientColor = Color(0x10415A9A), spotColor = Color(0x10415A9A))
                .clip(RoundedCornerShape(34.dp)).background(Color(0xF8FFFFFF))
                .border(1.dp, CpmLine, RoundedCornerShape(34.dp)).padding(horizontal = 10.dp, vertical = 7.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                Modifier.size(38.dp).clip(CircleShape).background(Color(0xFFF8F9FF))
                    .border(1.dp, CpmLine, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Icon(Icons.Default.AutoAwesome, null, tint = CpmViolet, modifier = Modifier.size(20.dp))
            }
            BasicTextField(
                value = value,
                onValueChange = onValueChange,
                modifier = Modifier.weight(1f).padding(horizontal = 14.dp),
                textStyle = TextStyle(color = TextPrimary, fontSize = 14.sp, lineHeight = 20.sp),
                cursorBrush = SolidColor(CpmBlue),
                maxLines = 3,
                decorationBox = { innerTextField ->
                    Box(contentAlignment = Alignment.CenterStart) {
                        if (value.isEmpty()) Text("输入你的校园事务问题…", color = Muted, fontSize = 14.sp)
                        innerTextField()
                    }
                },
            )
            FilledIconButton(
                onClick = onSend, enabled = value.isNotBlank() && !sending, modifier = Modifier.size(44.dp), shape = CircleShape,
                colors = IconButtonDefaults.filledIconButtonColors(
                    containerColor = CpmBlue,
                    contentColor = Color.White,
                    disabledContainerColor = CpmBlue,
                    disabledContentColor = Color.White,
                ),
            ) { Icon(Icons.Default.NearMe, "发送", Modifier.size(23.dp)) }
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.Shield, null, tint = Muted, modifier = Modifier.size(13.dp))
            Text(" 仅提供校园事务辅助，不替代学校正式通知或专业咨询", color = Muted, fontSize = 10.sp, maxLines = 1)
        }
    }
}

@Composable
private fun MarkdownMessage(markdown: String, color: Color) = Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
    markdown.replace("\r\n", "\n").lines().forEach { rawLine ->
        val line = rawLine.trimEnd()
        when {
            line.startsWith("### ") || line.startsWith("## ") || line.startsWith("# ") -> MarkdownText(line.substringAfter(' ').trim(), color, 16.sp, 22.sp, FontWeight.Bold)
            line.startsWith("- ") || line.startsWith("* ") -> Row(verticalAlignment = Alignment.Top) {
                Text("•", color = if (color == Color.White) Color.White else Primary, fontSize = 14.sp, modifier = Modifier.padding(end = 6.dp))
                MarkdownText(line.drop(2), color, 14.sp, 21.sp, FontWeight.Normal, Modifier.weight(1f))
            }
            else -> MarkdownText(line, color, 14.sp, 21.sp, FontWeight.Normal)
        }
    }
}

@Composable
private fun MarkdownText(text: String, color: Color, fontSize: TextUnit, lineHeight: TextUnit, fontWeight: FontWeight, modifier: Modifier = Modifier) {
    val annotated = buildAnnotatedString {
        var cursor = 0
        while (cursor < text.length) {
            val start = text.indexOf("**", cursor)
            if (start < 0) { append(text.substring(cursor)); break }
            append(text.substring(cursor, start))
            val end = text.indexOf("**", start + 2)
            if (end < 0) { append(text.substring(start)); break }
            withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(text.substring(start + 2, end)) }
            cursor = end + 2
        }
    }
    Text(annotated, modifier = modifier, color = color, fontSize = fontSize, lineHeight = lineHeight, fontWeight = fontWeight)
}

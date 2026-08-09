package com.example.campusai.ui.screens.notifications

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.*
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.border
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.ExtractResult
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.NotificationInboxRepository
import com.example.campusai.data.notification.NotificationSource
import com.example.campusai.ui.components.ModeBadge
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import java.util.concurrent.TimeUnit

@Composable
fun NotificationsScreen(
    repository: AppRepository,
    inboxRepository: NotificationInboxRepository,
) {
    val mockMode by repository.mockMode.collectAsState()
    val reduceMotion by repository.reduceMotion.collectAsState()
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val inbox by inboxRepository.observeRecentNotifications().collectAsState(initial = emptyList())
    val sourceSettings by inboxRepository.observeSourceSettings().collectAsState(initial = null)
    var notificationAccessGranted by remember { mutableStateOf(inboxRepository.isNotificationAccessGranted()) }
    var showClearConfirmation by remember { mutableStateOf(false) }

    // 进入页面时尝试从后端拉取最新通知
    LaunchedEffect(Unit) { repository.refreshNotices() }

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                notificationAccessGranted = inboxRepository.isNotificationAccessGranted()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    var noticeText by remember {
        mutableStateOf("【教务处通知】请各班同学于本周五17:00前完成2026年秋季学期选课确认，登录教务系统核对课程信息。如有冲突请联系学院教务办公室。")
    }
    var extracting by remember { mutableStateOf(false) }
    var extracted by remember { mutableStateOf<ExtractResult?>(null) }

    val animatedAlpha by animateFloatAsState(
        targetValue = 1f,
        animationSpec = tween(400, easing = CubicBezierEasing(0.2f, 0.8f, 0.2f, 1f))
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
                Text("通知整理", style = MaterialTheme.typography.headlineMedium)
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
                .padding(22.dp)
                .enterAnimation(delayMs = 30, enabled = !reduceMotion),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("自动收集校园通知", style = MaterialTheme.typography.titleMedium)
            Text(
                "仅处理 Android 系统实际展示给 CampusMate 的通知，不会读取聊天历史。",
                color = Muted,
                fontSize = 12.sp,
            )

            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    if (notificationAccessGranted) Icons.Default.CheckCircle else Icons.Default.Info,
                    contentDescription = null,
                    tint = if (notificationAccessGranted) Primary else Muted,
                    modifier = Modifier.size(18.dp),
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    "通知使用权：${if (notificationAccessGranted) "已授权" else "未授权"}",
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 14.sp,
                )
            }

            if (!notificationAccessGranted) {
                Text(
                    "需要你在系统设置中主动授权。授权后，已开启来源的通知会仅保存在本机。",
                    color = Muted,
                    fontSize = 12.sp,
                )
                OutlinedButton(
                    onClick = { context.startActivity(inboxRepository.createNotificationAccessSettingsIntent()) },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Default.Settings, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("去系统设置授权")
                }
            }

            HorizontalDivider(color = Line)
            Text("来源", fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
            NotificationSource.entries.forEach { source ->
                val enabled = sourceSettings?.isEnabled(source) ?: false
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(source.displayName, fontSize = 14.sp)
                        Text(if (enabled) "已开启" else "已关闭", color = Muted, fontSize = 12.sp)
                    }
                    Switch(
                        checked = enabled,
                        onCheckedChange = { value ->
                            scope.launch { inboxRepository.setNotificationSourceEnabled(source, value) }
                        },
                        enabled = sourceSettings != null,
                    )
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("最近自动收集", fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                if (inbox.isNotEmpty()) {
                    TextButton(onClick = { showClearConfirmation = true }) {
                        Text("清空记录")
                    }
                }
            }

            if (inbox.isEmpty()) {
                Text("尚未收集到校园通知", fontWeight = FontWeight.Medium, fontSize = 14.sp)
                Text("收到已开启来源的系统通知后，会在这里显示。", color = Muted, fontSize = 12.sp)
            } else {
                inbox.forEach { notification ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(
                                listOfNotNull(notification.source.displayName, notification.conversationTitle ?: notification.title)
                                    .joinToString(" · "),
                                fontWeight = FontWeight.Medium,
                                fontSize = 13.sp,
                            )
                            Text(
                                notification.bigText ?: notification.text ?: "通知内容不可用",
                                color = TextPrimary,
                                fontSize = 13.sp,
                                maxLines = 2,
                            )
                            Text(relativeCaptureTime(notification.capturedAt), color = Muted, fontSize = 11.sp)
                        }
                        IconButton(onClick = { scope.launch { inboxRepository.deleteNotification(notification.id) } }) {
                            Icon(Icons.Default.Delete, contentDescription = "删除自动收集通知", tint = Muted)
                        }
                    }
                    HorizontalDivider(color = Line)
                }
            }
        }

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .background(Surface)
                .border(1.dp, Line, RoundedCornerShape(10.dp))
                .padding(22.dp)
                .enterAnimation(delayMs = 60, enabled = !reduceMotion),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text("粘贴校园通知", style = MaterialTheme.typography.titleMedium)
            Text(
                "系统会尝试提取标题、来源、截止时间与待办。结果需要你确认后保存。",
                color = Muted, fontSize = 12.sp
            )
            OutlinedTextField(
                value = noticeText,
                onValueChange = { noticeText = it },
                modifier = Modifier.fillMaxWidth().height(180.dp),
                shape = RoundedCornerShape(8.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Primary,
                    unfocusedBorderColor = InputBorder
                )
            )
            Button(
                onClick = {
                    scope.launch {
                        extracting = true
                        try { extracted = repository.extractNotice(noticeText) }
                        catch (e: Exception) { extracted = ExtractResult(error = "提取服务暂时不可用，请稍后重试。") }
                        finally { extracting = false }
                    }
                },
                enabled = !extracting && noticeText.isNotBlank(),
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(8.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Primary)
            ) {
                if (extracting) {
                    CircularProgressIndicator(modifier = Modifier.size(18.dp), color = Surface, strokeWidth = 2.dp)
                    Spacer(Modifier.width(8.dp))
                    Text("正在智能提取…", fontWeight = FontWeight.SemiBold)
                } else {
                    Text("开始提取", fontWeight = FontWeight.SemiBold)
                    Icon(Icons.Default.AutoAwesome, null, modifier = Modifier.size(18.dp))
    }

    if (showClearConfirmation) {
        AlertDialog(
            onDismissRequest = { showClearConfirmation = false },
            title = { Text("清空自动收集记录？") },
            text = { Text("此操作只会删除本机的自动收集通知，无法恢复。") },
            confirmButton = {
                TextButton(onClick = {
                    scope.launch { inboxRepository.clearInbox() }
                    showClearConfirmation = false
                }) { Text("清空") }
            },
            dismissButton = { TextButton(onClick = { showClearConfirmation = false }) { Text("取消") } },
        )
    }
}

        }

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .background(Surface)
                .border(1.dp, Line, RoundedCornerShape(10.dp))
                .padding(22.dp)
                .enterAnimation(enabled = !reduceMotion),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            Text("提取结果", style = MaterialTheme.typography.titleMedium)

            val result = extracted
            if (result == null) {
                Column(
                    modifier = Modifier.fillMaxWidth().height(120.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    Icon(Icons.Default.ContentPaste, null, tint = Muted, modifier = Modifier.size(42.dp))
                    Spacer(Modifier.height(10.dp))
                    Text("提取结果会显示在这里", color = Muted, fontSize = 12.sp)
                }
            }
            AnimatedVisibility(
                visible = result != null,
                enter = expandVertically(animationSpec = tween(400)) + fadeIn(animationSpec = tween(300)),
                exit = shrinkVertically(animationSpec = tween(300)) + fadeOut(animationSpec = tween(200)),
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    if (result?.error != null) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(8.dp))
                                .background(AlertErrorBg)
                                .padding(10.dp, 12.dp),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Default.Warning, null, tint = AlertErrorText, modifier = Modifier.size(16.dp))
                            Text(result.error, color = AlertErrorText, fontSize = 13.sp)
                        }
                    } else if (result != null) {
                        var editTitle by remember(result) { mutableStateOf(result.title) }
                        var editSource by remember(result) { mutableStateOf(result.source) }
                        var editDeadline by remember(result) { mutableStateOf(result.deadline) }

                        OutlinedTextField(value = editTitle, onValueChange = { editTitle = it }, label = { Text("标题") }, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(8.dp), colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Primary, unfocusedBorderColor = InputBorder))
                        OutlinedTextField(value = editSource, onValueChange = { editSource = it }, label = { Text("来源") }, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(8.dp), colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Primary, unfocusedBorderColor = InputBorder))
                        OutlinedTextField(value = editDeadline, onValueChange = { editDeadline = it }, label = { Text("截止时间") }, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(8.dp), colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Primary, unfocusedBorderColor = InputBorder))

                        if (result.tasks.isNotEmpty()) {
                            Text("识别出的事项", fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                            result.tasks.forEach { task ->
                                Text("• $task", fontSize = 13.sp, color = TextPrimary)
                            }
                        }

                        Text(
                            "置信度 ${Math.round(result.confidence * 100)}%，结果仅供确认。",
                            color = Muted, fontSize = 12.sp
                        )

                        Button(
                            onClick = {
                                scope.launch {
                                    repository.addTask(editTitle, editDeadline)
                                    extracted = result.copy(saved = true)
                                }
                            },
                            enabled = !result.saved,
                            modifier = Modifier.fillMaxWidth().height(48.dp),
                            shape = RoundedCornerShape(8.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = Primary)
                        ) {
                            Text(if (result.saved) "已保存到待办" else "确认并保存", fontWeight = FontWeight.SemiBold)
                        }
                    }
                }
            }
        }
}
}

private fun relativeCaptureTime(capturedAt: Long, now: Long = System.currentTimeMillis()): String {
    val minutes = TimeUnit.MILLISECONDS.toMinutes((now - capturedAt).coerceAtLeast(0L))
    return when {
        minutes == 0L -> "刚刚"
        minutes < 60L -> "$minutes 分钟前"
        minutes < 24 * 60 -> "${minutes / 60} 小时前"
        else -> "${minutes / (24 * 60)} 天前"
    }
}


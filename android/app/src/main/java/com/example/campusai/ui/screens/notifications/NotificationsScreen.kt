package com.example.campusai.ui.screens.notifications

import com.example.campusai.ui.components.GlassButton as Button
import com.example.campusai.ui.components.GlassIconButton as IconButton
import com.example.campusai.ui.components.GlassOutlinedButton as OutlinedButton
import com.example.campusai.ui.components.GlassTextButton as TextButton

import androidx.lifecycle.compose.collectAsStateWithLifecycle

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
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.vector.ImageVector
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
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import java.util.concurrent.TimeUnit

@Composable
fun NotificationsScreen(
    repository: AppRepository,
    inboxRepository: NotificationInboxRepository,
    onNavigateToWechat: () -> Unit,
    onNavigateToChaoxing: () -> Unit,
) {
    val mockMode by repository.mockMode.collectAsStateWithLifecycle()
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val inbox by inboxRepository.observeRecentNotifications().collectAsStateWithLifecycle(initialValue = emptyList())
    val sourceSettings by inboxRepository.observeSourceSettings().collectAsStateWithLifecycle(initialValue = null)
    var notificationAccessGranted by remember { mutableStateOf(inboxRepository.isNotificationAccessGranted()) }
    var showClearConfirmation by remember { mutableStateOf(false) }

    var chaoxingStatus by remember { mutableStateOf<String?>(null) }
    var chaoxingLastSync by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        repository.refreshNotices()
        val status = repository.getChaoxingStatus()
        chaoxingStatus = status?.status
        chaoxingLastSync = status?.last_synced_at
    }

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                notificationAccessGranted = inboxRepository.isNotificationAccessGranted()
                scope.launch {
                    val status = repository.getChaoxingStatus()
                    chaoxingStatus = status?.status
                    chaoxingLastSync = status?.last_synced_at
                }
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
        NotificationSectionCard(
            title = "通知来源",
            modifier = Modifier.enterAnimation(delayMs = 30, enabled = !reduceMotion),
        ) {
            val wechatEnabled = sourceSettings?.isEnabled(NotificationSource.WECHAT) ?: false
            val wechatStatusText: String
            val wechatStatusColor: androidx.compose.ui.graphics.Color
            when {
                !notificationAccessGranted -> {
                    wechatStatusText = "需授权"
                    wechatStatusColor = DangerText
                }
                wechatEnabled -> {
                    wechatStatusText = "已开启"
                    wechatStatusColor = Primary
                }
                else -> {
                    wechatStatusText = "未开启"
                    wechatStatusColor = Muted
                }
            }
            SourceRow(
                icon = Icons.Default.Chat,
                title = "微信通知",
                subtitle = "监听系统通知，整理校园事务",
                statusText = wechatStatusText,
                statusColor = wechatStatusColor,
                onClick = onNavigateToWechat,
            )
            SectionDivider()
            val wecomEnabled = sourceSettings?.isEnabled(NotificationSource.WECOM) ?: false
            val wecomStatusText: String
            val wecomStatusColor: androidx.compose.ui.graphics.Color
            when {
                !notificationAccessGranted -> {
                    wecomStatusText = "需授权"
                    wecomStatusColor = DangerText
                }
                wecomEnabled -> {
                    wecomStatusText = "已开启"
                    wecomStatusColor = Primary
                }
                else -> {
                    wecomStatusText = "未开启"
                    wecomStatusColor = Muted
                }
            }
            SourceRow(
                icon = Icons.Default.Business,
                title = "企业微信",
                subtitle = "监听工作/学习群通知",
                statusText = wecomStatusText,
                statusColor = wecomStatusColor,
                onClick = onNavigateToWechat,
            )
            SectionDivider()
            val qqEnabled = sourceSettings?.isEnabled(NotificationSource.QQ) ?: false
            val qqStatusText: String
            val qqStatusColor: androidx.compose.ui.graphics.Color
            when {
                !notificationAccessGranted -> {
                    qqStatusText = "需授权"
                    qqStatusColor = DangerText
                }
                qqEnabled -> {
                    qqStatusText = "已开启"
                    qqStatusColor = Primary
                }
                else -> {
                    qqStatusText = "未开启"
                    qqStatusColor = Muted
                }
            }
            SourceRow(
                icon = Icons.Default.Forum,
                title = "QQ",
                subtitle = "监听 QQ 群通知",
                statusText = qqStatusText,
                statusColor = qqStatusColor,
                onClick = onNavigateToWechat,
            )
            SectionDivider()
            val chaoxingStatusText: String
            val chaoxingStatusColor: androidx.compose.ui.graphics.Color
            when (chaoxingStatus) {
                "online" -> {
                    chaoxingStatusText = "已连接"
                    chaoxingStatusColor = Primary
                }
                "expired" -> {
                    chaoxingStatusText = "需重新登录"
                    chaoxingStatusColor = DangerText
                }
                else -> {
                    chaoxingStatusText = "未连接"
                    chaoxingStatusColor = Muted
                }
            }
            val chaoxingSubtitle = if (chaoxingStatus == "online" && chaoxingLastSync != null) {
                "课程 · 作业 · 通知同步 · 上次 $chaoxingLastSync"
            } else {
                "同步课程、作业与课程通知"
            }
            SourceRow(
                icon = Icons.Default.School,
                title = "学习通",
                subtitle = chaoxingSubtitle,
                statusText = chaoxingStatusText,
                statusColor = chaoxingStatusColor,
                onClick = onNavigateToChaoxing,
            )
        }

        NotificationSectionCard(
            title = "系统通知监听",
            modifier = Modifier.enterAnimation(delayMs = 60, enabled = !reduceMotion),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                SourceIcon(Icons.Default.NotificationsActive)
                Column(modifier = Modifier.padding(start = 12.dp).weight(1f)) {
                    Text("通知访问权限", fontSize = 14.sp, fontWeight = FontWeight.Medium, color = TextPrimary)
                    Text(
                        if (notificationAccessGranted) "已授权" else "未授权",
                        color = Muted,
                        fontSize = 11.sp,
                    )
                }
                if (!notificationAccessGranted) {
                    OutlinedButton(
                        onClick = { context.startActivity(inboxRepository.createNotificationAccessSettingsIntent()) },
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
                    ) {
                        Text("去授权", fontSize = 12.sp)
                    }
                } else {
                    Text("已授权", color = Primary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
                }
            }
            SectionDivider()
            SourceSwitchRow(
                icon = Icons.Default.School,
                title = "学习通辅助通知监听",
                subtitle = "作为补充来源",
                checked = sourceSettings?.isEnabled(NotificationSource.XUEXITONG) ?: false,
                enabled = sourceSettings != null,
            ) { value ->
                scope.launch { inboxRepository.setNotificationSourceEnabled(NotificationSource.XUEXITONG, value) }
            }
            SectionDivider()
            SourceSwitchRow(

                icon = Icons.Default.Apps,
                title = "其他应用",
                subtitle = "未识别来源的系统通知",
                checked = sourceSettings?.isEnabled(NotificationSource.OTHER) ?: false,
                enabled = sourceSettings != null,
            ) { value ->
                scope.launch { inboxRepository.setNotificationSourceEnabled(NotificationSource.OTHER, value) }
            }
        }

        NotificationSectionCard(
            title = "最近收集",
            modifier = Modifier.enterAnimation(delayMs = 90, enabled = !reduceMotion),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (inbox.isEmpty()) {
                    Text("暂无自动收集的校园通知", fontWeight = FontWeight.Medium, fontSize = 14.sp, color = TextPrimary)
                } else {
                    Text("${inbox.size} 条记录", fontWeight = FontWeight.Medium, fontSize = 14.sp, color = TextPrimary)
                }
                if (inbox.isNotEmpty()) {
                    TextButton(onClick = { showClearConfirmation = true }) {
                        Text("清空记录", color = Muted, fontSize = 12.sp)
                    }
                }
            }
            if (inbox.isEmpty()) {
                Text("收到符合条件的系统通知后，会显示在这里。", color = Muted, fontSize = 12.sp)
            } else {
                inbox.forEachIndexed { index, notification ->
                    if (index > 0) HorizontalDivider(color = Line)
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
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
                }
            }
        }

        NotificationSectionCard(
            title = "手动整理",
            modifier = Modifier.enterAnimation(delayMs = 120, enabled = !reduceMotion),
        ) {
            Text(
                "粘贴微信、学习通等校园通知，自动提取时间和待办。",
                color = Muted, fontSize = 12.sp
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = noticeText,
                onValueChange = { noticeText = it },
                modifier = Modifier.fillMaxWidth().height(140.dp),
                shape = RoundedCornerShape(10.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Primary,
                    unfocusedBorderColor = InputBorder
                )
            )
            Spacer(Modifier.height(10.dp))
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
                modifier = Modifier.fillMaxWidth().height(46.dp),
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Primary)
            ) {
                if (extracting) {
                    CircularProgressIndicator(modifier = Modifier.size(16.dp), color = Surface, strokeWidth = 2.dp)
                    Spacer(Modifier.width(8.dp))
                    Text("正在提取…", fontWeight = FontWeight.SemiBold)
                } else {
                    Text("开始整理", fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.width(6.dp))
                    Icon(Icons.Default.AutoAwesome, null, modifier = Modifier.size(16.dp))
                }
            }
        }

        NotificationSectionCard(
            title = "提取结果",
            modifier = Modifier.enterAnimation(delayMs = 150, enabled = !reduceMotion),
        ) {
            val result = extracted
            if (result == null) {
                Text("整理后会显示在这里", color = Muted, fontSize = 12.sp)
            }
            AnimatedVisibility(
                visible = result != null,
                enter = expandVertically(animationSpec = tween(400)) + fadeIn(animationSpec = tween(300)),
                exit = shrinkVertically(animationSpec = tween(300)) + fadeOut(animationSpec = tween(200)),
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
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

        Spacer(Modifier.height(BottomDockReservedHeight + 20.dp))
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

@Composable
private fun NotificationSectionCard(
    title: String,
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(modifier.fillMaxWidth()) {
        Text(
            title,
            color = TextPrimary,
            fontSize = 14.sp,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(start = 2.dp, bottom = 8.dp),
        )
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(14.dp))
                .background(Surface)
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(2.dp),
            content = content,
        )
    }
}

@Composable
private fun SourceRow(
    icon: ImageVector,
    title: String,
    subtitle: String,
    statusText: String,
    statusColor: androidx.compose.ui.graphics.Color,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .campusClickable(onClick = onClick)
            .padding(vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        SourceIcon(icon)
        Column(modifier = Modifier.padding(start = 12.dp).weight(1f)) {
            Text(title, fontSize = 14.sp, fontWeight = FontWeight.Medium, color = TextPrimary)
            Spacer(Modifier.height(2.dp))
            Text(subtitle, color = Muted, fontSize = 11.sp, maxLines = 1)
        }
        Text(statusText, color = statusColor, fontSize = 12.sp, fontWeight = FontWeight.Medium)
        Spacer(Modifier.width(4.dp))
        Icon(Icons.Default.ChevronRight, contentDescription = "打开", tint = Muted, modifier = Modifier.size(18.dp))
    }
}

@Composable
private fun SourceSwitchRow(
    icon: ImageVector,
    title: String,
    subtitle: String,
    checked: Boolean,
    enabled: Boolean,
    onCheckedChange: (Boolean) -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        SourceIcon(icon)
        Column(modifier = Modifier.padding(start = 12.dp).weight(1f)) {
            Text(title, fontSize = 14.sp, fontWeight = FontWeight.Medium, color = TextPrimary)
            Spacer(Modifier.height(2.dp))
            Text(subtitle, color = Muted, fontSize = 11.sp)
        }
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            enabled = enabled,
        )
    }
}

@Composable
private fun SourceIcon(icon: ImageVector) {
    Box(
        Modifier.size(38.dp).clip(RoundedCornerShape(12.dp)).background(PrimarySoft),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, null, tint = Primary, modifier = Modifier.size(20.dp))
    }
}

@Composable
private fun SectionDivider() {
    HorizontalDivider(color = Line, modifier = Modifier.padding(start = 50.dp))
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

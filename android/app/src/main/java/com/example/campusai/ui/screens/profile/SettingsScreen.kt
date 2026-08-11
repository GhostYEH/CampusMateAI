package com.example.campusai.ui.screens.profile

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.BuildConfig
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(
    repository: AppRepository,
    onOpenContribution: () -> Unit,

) {
    val darkMode by repository.darkMode.collectAsState()
    val reduceMotion by repository.reduceMotion.collectAsState()
    val reminders by repository.remindersEnabled.collectAsState()
    val mockMode by repository.mockMode.collectAsState()
    val modelStatus by repository.expressionSessionManager.status.collectAsState()
    val modelResult by repository.expressionSessionManager.result.collectAsState()
    val scope = rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }
    var backendLabel by remember { mutableStateOf("正在检查") }
    LaunchedEffect(mockMode) {
        val status = repository.refreshBackendStatus()
        backendLabel = if (status.online) "已连接（${status.mode}）" else "未连接（${status.mode}）"
    }
    ReferenceSystemBars(darkMode)

    Box(Modifier.fillMaxSize().background(ReferencePageBackground)) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(bottom = BottomDockReservedHeight + 20.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            item {
                SettingsGroup(
                    title = "显示与动效",
                    modifier = Modifier.enterAnimation(enabled = !reduceMotion),
                ) {
                    SettingsSwitchRow(
                        icon = if (darkMode) Icons.Default.DarkMode else Icons.Default.LightMode,
                        title = "深色模式",
                        subtitle = if (darkMode) "已使用夜间配色，减少暗处眩光" else "切换为更适合夜间的深色界面",
                        checked = darkMode,
                    ) { scope.launch { repository.setDarkMode(it) } }
                    SettingsDivider()
                    SettingsSwitchRow(
                        icon = Icons.Default.MotionPhotosOff,
                        title = "减少动态效果",
                        subtitle = "减少页面进入与状态切换动画",
                        checked = reduceMotion,
                    ) { scope.launch { repository.setReduceMotion(it) } }
                }
            }
            if (BuildConfig.DEBUG) {
                item {
                    SettingsGroup(
                        title = "调试演示",
                        modifier = Modifier.enterAnimation(delayMs = 175, enabled = !reduceMotion),
                    ) {
                        SettingsSwitchRow(
                            icon = Icons.Default.BugReport,
                            title = "使用 Mock 表情模型",
                            subtitle = if (mockMode) "当前为 Mock；关闭后将使用本机 LiteRT" else "当前为本机 LiteRT；可切换 Mock 演示",
                            checked = mockMode,
                        ) { enabled -> scope.launch { repository.setMockMode(enabled) } }
                        SettingsDivider()
                        SettingsInfoRow(Icons.Default.Memory, "模型版本", modelResult.modelVersion)
                        SettingsDivider()
                        SettingsInfoRow(Icons.Default.Downloading, "模型加载结果", modelStatus.toString())
                        SettingsDivider()
                        SettingsInfoRow(Icons.Default.Cloud, "后端连接", backendLabel)

                    }
                }
            }
            item {
                SettingsGroup(
                    title = "提醒与陪伴",
                    modifier = Modifier.enterAnimation(delayMs = 70, enabled = !reduceMotion),
                ) {
                    SettingsSwitchRow(
                        icon = Icons.Default.NotificationsActive,
                        title = "截止提醒",
                        subtitle = "待办临近截止时发送系统通知",
                        checked = reminders,
                    ) {
                        scope.launch {
                            repository.setRemindersEnabled(it)
                            snackbar.showSnackbar(if (it) "截止提醒已开启" else "截止提醒已关闭")
                        }
                    }
                }
            }
            item {
                SettingsGroup(
                    title = "数据与服务",
                    modifier = Modifier.enterAnimation(delayMs = 140, enabled = !reduceMotion),
                ) {
                    SettingsInfoRow(Icons.Default.Storage, "本地数据", "账号偏好仅保存在本机")
                    SettingsDivider()
                    SettingsInfoRow(Icons.Default.Security, "隐私说明", "识别结果仅供辅助参考")

                }
            }
            item {
                SettingsGroup(
                    title = "AI 与模型共建",
                    modifier = Modifier.enterAnimation(delayMs = 210, enabled = !reduceMotion),
                ) {
                    SettingsActionRow(
                        icon = Icons.Default.Face,
                        title = "CNN 模型共建",
                        subtitle = "主动拍摄、打标并上传表情样本",
                        onClick = onOpenContribution,
                    )
                }
            }
            item {
                AnimatedContent(
                    targetState = darkMode,
                    transitionSpec = {
                        (fadeIn(tween(220)) + slideInVertically(tween(220)) { it / 5 }) togetherWith
                            (fadeOut(tween(150)) + slideOutVertically(tween(150)) { -it / 8 })
                    },
                    label = "theme-tip",
                    modifier = Modifier.padding(horizontal = 20.dp),
                ) { isDark ->
                    Text(
                        if (isDark) "深色模式已应用到校园事务页面。"
                        else "设置会自动保存在本机。",
                        color = ReferenceMuted,
                        fontSize = 11.sp,
                    )
                }
            }
        }
        SnackbarHost(snackbar, Modifier.align(Alignment.BottomCenter).padding(16.dp))
    }
}

@Composable
private fun SettingsGroup(
    title: String,
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(modifier.padding(horizontal = 16.dp)) {
        Text(
            title,
            color = ReferenceText,
            fontSize = 15.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(start = 4.dp, bottom = 10.dp),
        )
        Column(
            Modifier.fillMaxWidth()
                .shadow(
                    elevation = 12.dp,
                    shape = RoundedCornerShape(22.dp),
                    ambientColor = ReferencePrimary.copy(alpha = .07f),
                    spotColor = ReferencePrimary.copy(alpha = .1f),
                )
                .clip(RoundedCornerShape(22.dp))
                .background(ReferenceSurface)
                .padding(horizontal = 16.dp),
            content = content,
        )
    }
}

@Composable
private fun SettingsSwitchRow(
    icon: ImageVector,
    title: String,
    subtitle: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
) {
    val isDark = MaterialTheme.colorScheme.background.luminance() < .5f
    Row(
        Modifier.fillMaxWidth().padding(vertical = 13.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        SettingsIcon(icon)
        Column(Modifier.padding(start = 12.dp).weight(1f)) {
            Text(title, color = ReferenceText, fontSize = 14.sp, fontWeight = FontWeight.Medium)
            Spacer(Modifier.height(3.dp))
            Text(subtitle, color = ReferenceMuted, fontSize = 10.5.sp)
        }
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            colors = SwitchDefaults.colors(
                checkedThumbColor = if (isDark) ReferenceText else Color.White,
                checkedTrackColor = ReferencePrimary,
                uncheckedThumbColor = if (isDark) ReferenceText else Color.White,
                uncheckedTrackColor = if (isDark) ReferenceDivider else Color(0xFFE4E6F0),
                uncheckedBorderColor = Color.Transparent,
            ),
        )
    }
}

@Composable
private fun SettingsInfoRow(icon: ImageVector, title: String, value: String) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 15.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        SettingsIcon(icon)
        Text(
            title,
            color = ReferenceText,
            fontSize = 14.sp,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.padding(start = 12.dp).weight(1f),
        )
        Text(value, color = ReferenceMuted, fontSize = 11.sp)
    }
}

@Composable
private fun SettingsActionRow(
    icon: ImageVector,
    title: String,
    subtitle: String,
    onClick: () -> Unit,
) {
    Row(
        Modifier.fillMaxWidth()
            .campusClickable(onClick = onClick)
            .padding(vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        SettingsIcon(icon)
        Column(Modifier.padding(start = 12.dp).weight(1f)) {
            Text(title, color = ReferenceText, fontSize = 14.sp, fontWeight = FontWeight.Medium)
            Spacer(Modifier.height(3.dp))
            Text(subtitle, color = ReferenceMuted, fontSize = 10.5.sp)
        }
        Icon(Icons.Default.ChevronRight, contentDescription = "打开", tint = ReferenceMuted)
    }
}

@Composable
private fun SettingsIcon(icon: ImageVector) {
    Box(
        Modifier.size(40.dp).clip(RoundedCornerShape(13.dp)).background(ReferencePrimarySoft),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, null, tint = ReferencePrimary, modifier = Modifier.size(22.dp))
    }
}

@Composable
private fun SettingsDivider() {
    HorizontalDivider(color = ReferenceDivider, modifier = Modifier.padding(start = 52.dp))
}

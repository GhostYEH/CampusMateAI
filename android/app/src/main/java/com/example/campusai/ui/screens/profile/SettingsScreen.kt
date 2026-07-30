package com.example.campusai.ui.screens.profile

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.enterAnimation
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(
    repository: AppRepository,
    onBack: () -> Unit,
) {
    val darkMode by repository.darkMode.collectAsState()
    val reduceMotion by repository.reduceMotion.collectAsState()
    val reminders by repository.remindersEnabled.collectAsState()
    val demoMode by repository.demoMode.collectAsState()
    val mockMode by repository.mockMode.collectAsState()
    val scope = rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }
    ReferenceSystemBars(darkMode)

    Box(Modifier.fillMaxSize().background(ReferencePageBackground)) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            item {
                ReferenceSubpageHeader(
                    title = "系统设置",
                    subtitle = "个性化你的校园助手",
                    onBack = onBack,
                )
            }
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
                    SettingsDivider()
                    SettingsSwitchRow(
                        icon = Icons.Default.Science,
                        title = "比赛演示模式",
                        subtitle = "使用完整、自然的校园 Mock 数据链路",
                        checked = demoMode,
                    ) { scope.launch { repository.setDemoMode(it) } }
                }
            }
            item {
                SettingsGroup(
                    title = "数据与服务",
                    modifier = Modifier.enterAnimation(delayMs = 140, enabled = !reduceMotion),
                ) {
                    SettingsInfoRow(Icons.Default.Dns, "当前数据模式", if (mockMode) "Mock 演示" else "真实后端")
                    SettingsDivider()
                    SettingsInfoRow(Icons.Default.Storage, "本地数据", "账号偏好仅保存在本机")
                    SettingsDivider()
                    SettingsInfoRow(Icons.Default.Security, "隐私说明", "识别结果仅供辅助参考")
                }
            }
            item {
                AnimatedContent(
                    targetState = darkMode,
                    transitionSpec = { fadeIn() togetherWith fadeOut() },
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
internal fun ReferenceSubpageHeader(
    title: String,
    subtitle: String,
    onBack: () -> Unit,
) {
    Box(
        Modifier.fillMaxWidth().height(174.dp)
            .clip(RoundedCornerShape(bottomStart = 28.dp, bottomEnd = 28.dp))
            .background(
                Brush.linearGradient(
                    colors = listOf(Color(0xFF5E69F5), ReferencePrimary, Color(0xFF8883FA)),
                    start = Offset.Zero,
                    end = Offset(1000f, 600f),
                )
            ),
    ) {
        Box(
            Modifier.size(150.dp).align(Alignment.TopEnd).offset(x = 48.dp, y = (-52).dp)
                .clip(CircleShape).background(Color.White.copy(alpha = .07f))
        )
        Row(
            Modifier.fillMaxWidth().statusBarsPadding()
                .padding(start = 14.dp, top = 22.dp, end = 20.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(
                onClick = onBack,
                modifier = Modifier.size(44.dp).clip(CircleShape)
                    .background(Color.White.copy(alpha = .14f)),
            ) {
                Icon(Icons.Default.ArrowBack, "返回", tint = Color.White)
            }
            Column(Modifier.padding(start = 14.dp)) {
                Text(title, color = Color.White, fontSize = 25.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(5.dp))
                Text(subtitle, color = Color.White.copy(alpha = .84f), fontSize = 13.sp)
            }
        }
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
                    ambientColor = Color(0x12666AF6),
                    spotColor = Color(0x18666AF6),
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
                checkedThumbColor = Color.White,
                checkedTrackColor = ReferencePrimary,
                uncheckedThumbColor = Color.White,
                uncheckedTrackColor = Color(0xFFE4E6F0),
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

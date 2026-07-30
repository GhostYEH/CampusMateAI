package com.example.campusai.ui.screens.profile

import androidx.compose.animation.core.*
import androidx.compose.foundation.border
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.Avatar
import com.example.campusai.ui.components.ModeBadge
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch

@Composable
fun ProfileScreen(repository: AppRepository) {
    val session by repository.session.collectAsState()
    val mockMode by repository.mockMode.collectAsState()
    val backendOnline by repository.backendOnline.collectAsState()
    val reduceMotion by repository.reduceMotion.collectAsState()
    val scope = rememberCoroutineScope()

    var demoMode by remember { mutableStateOf(true) }
    var reminderEnabled by remember { mutableStateOf(true) }

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
                Text("个人中心", style = MaterialTheme.typography.headlineMedium)
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
                .padding(22.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Avatar(session?.name ?: "", size = 64.dp)
            Text(session?.name ?: "", fontWeight = FontWeight.SemiBold, fontSize = 18.sp)
            Text(session?.detail ?: "", color = Muted, fontSize = 13.sp)

            Spacer(Modifier.height(8.dp))

            ProfileInfoRow("账号角色", session?.role ?: "student")
            ProfileInfoRow("数据模式", if (mockMode) "Mock 演示" else "真实后端")
            ProfileInfoRow("服务状态", if (backendOnline) "已连接" else "离线可用")
        }

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .background(Surface)
                .border(1.dp, Line, RoundedCornerShape(10.dp))
                .padding(22.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Text("偏好设置", style = MaterialTheme.typography.titleMedium)

            SwitchRow(
                title = "减少动态效果",
                subtitle = "减少页面切换与卡片进入动画",
                checked = reduceMotion,
                onCheckedChange = { scope.launch { repository.setReduceMotion(it) } }
            )
            SwitchRow(
                title = "比赛演示模式",
                subtitle = "使用完整自然的校园 Mock 数据链路",
                checked = demoMode,
                onCheckedChange = { demoMode = it }
            )
            SwitchRow(
                title = "截止提醒",
                subtitle = "Android 端使用系统通知提醒",
                checked = reminderEnabled,
                onCheckedChange = { reminderEnabled = it }
            )
        }
    }
}

@Composable
private fun ProfileInfoRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(label, color = Muted, fontSize = 13.sp)
        Text(value, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
    }
}

@Composable
private fun SwitchRow(
    title: String,
    subtitle: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(title, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
            Text(subtitle, color = Muted, fontSize = 11.sp)
        }
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            colors = SwitchDefaults.colors(checkedTrackColor = Primary)
        )
    }
}


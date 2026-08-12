package com.example.campusai.ui.screens.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.LinkOff
import androidx.compose.material.icons.filled.School
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.theme.AlertErrorBg
import com.example.campusai.ui.theme.AlertErrorText
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import com.example.campusai.workers.ChaoxingSyncScheduler

/** The single entry point for Chaoxing connection and synchronization. */
@Composable
fun ChaoxingScreen(viewModel: ChaoxingViewModel = viewModel()) {
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(Unit) { viewModel.checkStatus() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(horizontal = 20.dp)
            .padding(top = 12.dp, bottom = BottomDockReservedHeight + 24.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        StatusCard(uiState)

        when (uiState.status) {
            "online" -> ConnectedActions(uiState, viewModel)
            "expired" -> {
                ChaoxingLoginForm(
                    viewModel = viewModel,
                    headline = "学习通登录已失效",
                    helperText = "重新登录后将继续同步课程、作业与课程通知。",
                )
                SecondaryActionButton("解除连接", Icons.Default.LinkOff, !uiState.isDisconnecting, viewModel::disconnect)
            }
            "offline" -> ChaoxingLoginForm(viewModel = viewModel)
            else -> CheckingStatus()
        }

        uiState.syncResult?.let { message ->
            val isSuccess = message.contains("成功") || message.contains("解除")
            Row(
                modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp))
                    .background(if (isSuccess) PrimarySoft else AlertErrorBg)
                    .padding(horizontal = 12.dp, vertical = 10.dp),
            ) {
                Text(message, color = if (isSuccess) Primary else AlertErrorText, fontSize = 12.sp)
            }
        }
    }
}

@Composable
private fun ConnectedActions(uiState: ChaoxingUiState, viewModel: ChaoxingViewModel) {
    PrimaryActionButton(
        text = if (uiState.isSyncing) "同步中…" else "立即同步",
        icon = Icons.Default.Sync,
        enabled = !uiState.isSyncing,
        loading = uiState.isSyncing,
        onClick = { viewModel.syncNow(onRefreshNeeded = {}) },
    )
    SecondaryActionButton("解除连接", Icons.Default.LinkOff, !uiState.isDisconnecting, viewModel::disconnect)
}

@Composable
private fun StatusCard(uiState: ChaoxingUiState) {
    Column(
        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(Surface)
            .padding(horizontal = 16.dp, vertical = 14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.size(34.dp).clip(RoundedCornerShape(10.dp)).background(PrimarySoft),
                contentAlignment = Alignment.Center,
            ) { Icon(Icons.Default.School, null, tint = Primary, modifier = Modifier.size(18.dp)) }
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text("学习通", fontSize = 14.sp, fontWeight = FontWeight.SemiBold, color = TextPrimary)
                Spacer(Modifier.height(2.dp))
                val text = when (uiState.status) {
                    "online" -> if (uiState.isCheckingStatus) "已连接 · 正在验证" else "已连接"
                    "offline" -> "未连接"
                    "expired" -> "登录已失效"
                    else -> "正在检查连接状态"
                }
                val color = when (uiState.status) {
                    "online" -> Primary
                    "expired" -> AlertErrorText
                    else -> Muted
                }
                Text(text, color = color, fontSize = 12.sp, fontWeight = FontWeight.Medium)
            }
            if (uiState.status == "expired") {
                Icon(Icons.Default.CloudOff, null, tint = AlertErrorText, modifier = Modifier.size(18.dp))
            } else if (uiState.isCheckingStatus) {
                CircularProgressIndicator(Modifier.size(16.dp), color = Primary, strokeWidth = 2.dp)
            }
        }

        when (uiState.status) {
            "online" -> {
                HorizontalDivider(color = Line)
                uiState.lastSyncedAt?.let { InfoLine("上次同步", it) }
                InfoLine("自动同步", "每 ${ChaoxingSyncScheduler.SYNC_INTERVAL_HOURS} 小时")
                InfoLine("同步范围", "课程 / 作业 / 课程通知")
                uiState.statusMessage?.let { Text(it, color = Muted, fontSize = 12.sp) }
            }
            "expired" -> { HorizontalDivider(color = Line); Text("学习通会话已过期，请重新登录后继续同步。", color = AlertErrorText, fontSize = 12.sp) }
            "offline" -> {
                Text("连接后可同步课程、作业与课程通知。", color = Muted, fontSize = 12.sp)
                uiState.statusMessage?.let { Text(it, color = Muted, fontSize = 12.sp) }
            }
            else -> Text("正在确认学习通连接，请稍候。", color = Muted, fontSize = 12.sp)
        }
    }
}

@Composable
private fun CheckingStatus() {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
        CircularProgressIndicator(Modifier.size(18.dp), color = Primary, strokeWidth = 2.dp)
        Spacer(Modifier.width(8.dp))
        Text("正在检查学习通连接", color = Muted, fontSize = 13.sp)
    }
}

@Composable
private fun InfoLine(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = Muted, fontSize = 12.sp)
        Text(value, color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun PrimaryActionButton(text: String, icon: ImageVector, enabled: Boolean = true, loading: Boolean = false, onClick: () -> Unit) {
    Button(onClick, Modifier.fillMaxWidth().height(46.dp), enabled, RoundedCornerShape(10.dp), ButtonDefaults.buttonColors(containerColor = Primary)) {
        if (loading) CircularProgressIndicator(Modifier.size(16.dp), color = Surface, strokeWidth = 2.dp) else Icon(icon, null, Modifier.size(16.dp))
        Spacer(Modifier.width(8.dp)); Text(text, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun SecondaryActionButton(text: String, icon: ImageVector, enabled: Boolean = true, onClick: () -> Unit) {
    TextButton(onClick, Modifier.fillMaxWidth().height(40.dp), enabled, RoundedCornerShape(10.dp)) {
        Icon(icon, null, Modifier.size(14.dp), tint = Muted); Spacer(Modifier.width(6.dp)); Text(text, color = Muted, fontSize = 13.sp)
    }
}

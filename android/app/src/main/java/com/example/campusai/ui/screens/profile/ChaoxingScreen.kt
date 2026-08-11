package com.example.campusai.ui.screens.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.LinkOff
import androidx.compose.material.icons.filled.School
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
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

@Composable
fun ChaoxingScreen(
    onBack: () -> Unit,
    onNavigateToLogin: () -> Unit,
    viewModel: ChaoxingViewModel = viewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.checkStatus()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(horizontal = 20.dp)
            .padding(top = 12.dp, bottom = BottomDockReservedHeight + 24.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
            StatusCard(uiState)

            when (uiState.status) {
                "online" -> {
                    PrimaryActionButton(
                        text = if (uiState.isSyncing) "同步中…" else "立即同步",
                        icon = Icons.Default.Sync,
                        enabled = !uiState.isSyncing,
                        loading = uiState.isSyncing,
                        onClick = { viewModel.syncNow(onRefreshNeeded = { /* handled in VM */ }) },
                    )
                    SecondaryActionButton(
                        text = "解除连接",
                        icon = Icons.Default.LinkOff,
                        enabled = !uiState.isDisconnecting,
                        onClick = { viewModel.disconnect() },
                    )
                }
                "expired" -> {
                    PrimaryActionButton(
                        text = "重新登录",
                        icon = Icons.Default.School,
                        onClick = onNavigateToLogin,
                    )
                    SecondaryActionButton(
                        text = "解除连接",
                        icon = Icons.Default.LinkOff,
                        enabled = !uiState.isDisconnecting,
                        onClick = { viewModel.disconnect() },
                    )
                }
                else -> {
                    PrimaryActionButton(
                        text = "连接学习通",
                        icon = Icons.Default.School,
                        onClick = onNavigateToLogin,
                    )
                }
            }

            uiState.syncResult?.let { resultMsg ->
                val isSuccess = resultMsg.contains("成功") || resultMsg.contains("解除")
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(10.dp))
                        .background(if (isSuccess) PrimarySoft else AlertErrorBg)
                        .padding(horizontal = 12.dp, vertical = 10.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        resultMsg,
                        color = if (isSuccess) Primary else AlertErrorText,
                        fontSize = 12.sp,
                    )
                }
            }
    }
}

@Composable
private fun StatusCard(uiState: ChaoxingUiState) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(Surface)
            .padding(horizontal = 16.dp, vertical = 14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.size(34.dp).clip(RoundedCornerShape(10.dp)).background(PrimarySoft),
                contentAlignment = Alignment.Center,
            ) {
                Icon(Icons.Default.School, null, tint = Primary, modifier = Modifier.size(18.dp))
            }
            Spacer(Modifier.width(10.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text("学习通", fontSize = 14.sp, fontWeight = FontWeight.SemiBold, color = TextPrimary)
                Spacer(Modifier.height(2.dp))
                val statusText = when (uiState.status) {
                    "online" -> "已连接"
                    "offline" -> "未连接"
                    "expired" -> "登录已失效"
                    else -> "未知状态"
                }
                val statusColor = when (uiState.status) {
                    "online" -> Primary
                    "expired" -> AlertErrorText
                    else -> Muted
                }
                Text(statusText, color = statusColor, fontSize = 12.sp, fontWeight = FontWeight.Medium)
            }
            if (uiState.status == "expired") {
                Icon(Icons.Default.CloudOff, null, tint = AlertErrorText, modifier = Modifier.size(18.dp))
            }
        }

        when (uiState.status) {
            "online" -> {
                HorizontalDivider(color = Line)
                if (uiState.lastSyncedAt != null) {
                    InfoLine("上次同步", uiState.lastSyncedAt)
                }
                InfoLine("自动同步", "每 ${ChaoxingSyncScheduler.SYNC_INTERVAL_HOURS} 小时")
                InfoLine("同步范围", "课程 / 作业 / 课程通知")
            }
            "expired" -> {
                HorizontalDivider(color = Line)
                Text(
                    "学习通会话已过期，请重新登录后继续同步。",
                    color = AlertErrorText,
                    fontSize = 12.sp,
                )
            }
            "offline" -> {
                Text(
                    "连接后可同步课程、作业与课程通知。",
                    color = Muted,
                    fontSize = 12.sp,
                )
            }
            else -> {}
        }
    }
}

@Composable
private fun InfoLine(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = Muted, fontSize = 12.sp)
        Text(value, color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun PrimaryActionButton(
    text: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    enabled: Boolean = true,
    loading: Boolean = false,
    onClick: () -> Unit,
) {
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = Modifier.fillMaxWidth().height(46.dp),
        shape = RoundedCornerShape(10.dp),
        colors = ButtonDefaults.buttonColors(containerColor = Primary),
    ) {
        if (loading) {
            CircularProgressIndicator(modifier = Modifier.size(16.dp), color = Surface, strokeWidth = 2.dp)
            Spacer(Modifier.width(8.dp))
            Text(text, fontWeight = FontWeight.SemiBold)
        } else {
            Icon(icon, null, modifier = Modifier.size(16.dp))
            Spacer(Modifier.width(6.dp))
            Text(text, fontWeight = FontWeight.SemiBold)
        }
    }
}

@Composable
private fun SecondaryActionButton(
    text: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    TextButton(
        onClick = onClick,
        enabled = enabled,
        modifier = Modifier.fillMaxWidth().height(40.dp),
        shape = RoundedCornerShape(10.dp),
    ) {
        Icon(icon, null, modifier = Modifier.size(14.dp), tint = Muted)
        Spacer(Modifier.width(6.dp))
        Text(text, color = Muted, fontSize = 13.sp)
    }
}

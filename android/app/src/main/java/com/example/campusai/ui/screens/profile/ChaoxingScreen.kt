package com.example.campusai.ui.screens.profile

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel

@OptIn(ExperimentalMaterial3Api::class)
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

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("学习通同步") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "返回")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            val statusText = when (uiState.status) {
                "online" -> "已连接"
                "offline" -> "未连接"
                "expired" -> "登录已失效"
                else -> "未知状态"
            }

            Text(
                text = "状态: $statusText",
                style = MaterialTheme.typography.titleLarge
            )

            if (uiState.status == "online" || uiState.status == "expired") {
                if (uiState.lastSyncedAt != null) {
                    Text(
                        text = "上次同步时间: ${uiState.lastSyncedAt}",
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }

            if (uiState.status == "offline" || uiState.status == "expired") {
                Button(
                    onClick = onNavigateToLogin,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(if (uiState.status == "expired") "重新登录" else "连接学习通")
                }
            }

            if (uiState.status == "online" || uiState.status == "expired") {
                Button(
                    onClick = { viewModel.syncNow(onRefreshNeeded = { /* handled in VM */ }) },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !uiState.isSyncing
                ) {
                    Text(if (uiState.isSyncing) "同步中..." else "立即同步")
                }

                OutlinedButton(
                    onClick = { viewModel.disconnect() },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !uiState.isDisconnecting
                ) {
                    Text("解除连接")
                }
            }

            if (uiState.isSyncing) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.CenterHorizontally))
            }

            uiState.syncResult?.let { resultMsg ->
                Text(
                    text = resultMsg,
                    color = if (resultMsg.contains("成功") || resultMsg.contains("解除")) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyLarge,
                    modifier = Modifier.align(Alignment.CenterHorizontally)
                )
            }
        }
    }
}

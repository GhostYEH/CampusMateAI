package com.example.campusai.ui.screens.agent

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.campusai.data.remote.agent.AgentRiskLevel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NoticeWorkflowScreen(
    viewModel: NoticeWorkflowViewModel = viewModel(),
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.loadSources() }

    Scaffold(topBar = { AgentTopBar("通知事务", onBack) }) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item { Text("粘贴通知", style = MaterialTheme.typography.titleMedium) }
            item {
                OutlinedTextField(
                    value = state.pastedText,
                    onValueChange = { viewModel.updatePastedText(it) },
                    label = { Text("通知内容") },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 3,
                )
            }
            item {
                Button(
                    onClick = { viewModel.createWorkflowFromText(state.pastedText) },
                    enabled = state.pastedText.isNotBlank() && !state.loading,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("创建工作流") }
            }
            state.activeWorkflow?.let { workflow ->
                item { Text("工作流 ${workflow.workflowId.takeLast(8)}", style = MaterialTheme.typography.titleMedium) }
                item {
                    Card {
                        Column(Modifier.padding(16.dp)) {
                            Text(workflow.summary, style = MaterialTheme.typography.bodyMedium)
                            Text("状态 ${workflow.workflowStatus()}", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
                if (workflow.actions.isNotEmpty()) {
                    item { Text("动作", style = MaterialTheme.typography.titleSmall) }
                    items(workflow.actions) { action ->
                        Card {
                            Column(Modifier.padding(16.dp)) {
                                Text(action.summary, style = MaterialTheme.typography.bodyMedium)
                                Text("风险 ${action.risk()}", style = MaterialTheme.typography.bodySmall)
                                Text("置信度 ${(action.confidence * 100).toInt()}%", style = MaterialTheme.typography.bodySmall)
                                if (action.evidence.isNotBlank()) {
                                    Text("依据 ${action.evidence}", style = MaterialTheme.typography.bodySmall)
                                }
                                Text("状态 ${action.actionStatus()}", style = MaterialTheme.typography.bodySmall)
                                action.externalUrl?.let { Text("外部链接 $it", style = MaterialTheme.typography.bodySmall) }
                                Spacer(Modifier.height(8.dp))
                                ActionButtons(action, viewModel)
                            }
                        }
                    }
                }
            }
            if (state.sources.isNotEmpty()) {
                item { Text("通知来源", style = MaterialTheme.typography.titleSmall) }
                items(state.sources) { source ->
                    ListItem(
                        headlineContent = { Text(source.name) },
                        supportingContent = { Text(source.code) },
                        trailingContent = { Text(if (source.enabled) "已启用" else "已禁用") },
                    )
                }
            }
            state.error?.let { err ->
                item {
                    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
                        Text(err, Modifier.padding(16.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun ActionButtons(
    action: com.example.campusai.data.remote.agent.NoticeWorkflowActionDto,
    viewModel: NoticeWorkflowViewModel,
) {
    when (action.risk()) {
        AgentRiskLevel.AUTO_SAFE -> {
            if (action.actionStatus() == com.example.campusai.data.remote.agent.NoticeActionStatus.PROPOSED) {
                Button(onClick = { viewModel.approveAction(action.actionId) }) { Text("确认") }
            }
        }
        AgentRiskLevel.CONFIRM_REQUIRED -> {
            if (action.actionStatus() == com.example.campusai.data.remote.agent.NoticeActionStatus.PROPOSED) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { viewModel.approveAction(action.actionId) }) { Text("批准") }
                    OutlinedButton(onClick = { viewModel.rejectAction(action.actionId) }) { Text("拒绝") }
                }
            }
            if (action.actionStatus() == com.example.campusai.data.remote.agent.NoticeActionStatus.APPROVED) {
                Button(onClick = { viewModel.executeAction(action.actionId) }) { Text("执行") }
            }
        }
        AgentRiskLevel.MANUAL_ONLY -> {
            Text("需手动完成", style = MaterialTheme.typography.bodySmall)
            if (action.actionStatus() == com.example.campusai.data.remote.agent.NoticeActionStatus.PROPOSED) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { viewModel.approveAction(action.actionId) }) { Text("已手动完成") }
                    OutlinedButton(onClick = { viewModel.rejectAction(action.actionId) }) { Text("忽略") }
                }
            }
        }
        AgentRiskLevel.UNKNOWN -> {
            Text("未知风险，请谨慎", style = MaterialTheme.typography.bodySmall)
        }
    }
}
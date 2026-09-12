package com.example.campusai.ui.screens.agent

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.campusai.data.remote.agent.AcademicPolicy
import com.example.campusai.data.remote.agent.AgentRunStatus
import com.example.campusai.data.remote.agent.AssistanceMode
import com.example.campusai.data.remote.agent.CourseResearchRunCreateRequest
import com.example.campusai.data.remote.agent.SourcePolicyDto

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CourseResearchScreen(
    viewModel: CourseResearchViewModel = viewModel(),
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.loadRuns() }

    var question by remember { mutableStateOf("") }
    var mode by remember { mutableStateOf("EXPLAIN") }
    var academicPolicy by remember { mutableStateOf("LIMITED") }
    var allowWeb by remember { mutableStateOf(true) }

    Scaffold(topBar = { AgentTopBar("课程研究", onBack) }) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item { Text("提出研究问题", style = MaterialTheme.typography.titleMedium) }
            item {
                OutlinedTextField(
                    value = question,
                    onValueChange = { question = it },
                    label = { Text("问题") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            item {
                Row(Modifier.fillMaxWidth(), Arrangement.spacedBy(8.dp)) {
                    AssistModeDropdown(mode) { mode = it }
                    AcademicPolicyDropdown(academicPolicy) { academicPolicy = it }
                }
            }
            item {
                Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    Switch(checked = allowWeb, onCheckedChange = { allowWeb = it })
                    Spacer(Modifier.width(8.dp))
                    Text("允许网络来源")
                }
            }
            item {
                Button(
                    onClick = {
                        viewModel.submitResearch(
                            CourseResearchRunCreateRequest(
                                question = question,
                                mode = mode,
                                academicPolicy = academicPolicy,
                                sourcePolicy = SourcePolicyDto(allowWeb = allowWeb),
                            ),
                        )
                    },
                    enabled = question.isNotBlank() && !state.loading,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("提交研究") }
            }
            state.activeRun?.let { run ->
                item {
                    Card {
                        Column(Modifier.padding(16.dp)) {
                            Text("运行 ${run.runId.takeLast(8)}", style = MaterialTheme.typography.titleSmall)
                            Text("状态 ${run.runStatus()}", style = MaterialTheme.typography.bodySmall)
                            Text("策略 ${run.policy()}", style = MaterialTheme.typography.bodySmall)
                            Text("模式 ${run.assistance()}", style = MaterialTheme.typography.bodySmall)
                            if (run.runStatus() == AgentRunStatus.RUNNING || run.runStatus() == AgentRunStatus.AWAITING_APPROVAL) {
                                Spacer(Modifier.height(8.dp))
                                OutlinedButton(onClick = { viewModel.cancelRun(run.runId) }) { Text("取消") }
                            }
                        }
                    }
                }
                if (state.roleProgress.isNotEmpty()) {
                    item { Text("角色进度", style = MaterialTheme.typography.titleSmall) }
                    items(state.roleProgress) { role ->
                        ListItem(
                            headlineContent = { Text(role.role) },
                            supportingContent = { Text("${role.summary} • ${role.status}") },
                        )
                    }
                }
                if (state.citations.isNotEmpty()) {
                    item { Text("引用", style = MaterialTheme.typography.titleSmall) }
                    items(state.citations) { citation ->
                        ListItem(
                            headlineContent = { Text(citation.source) },
                            supportingContent = { Text("验证 ${citation.citationStatus()}") },
                        )
                    }
                }
                if (state.artifacts.isNotEmpty()) {
                    item { Text("产物", style = MaterialTheme.typography.titleSmall) }
                    items(state.artifacts) { artifact ->
                        ListItem(
                            headlineContent = { Text(artifact.type().name) },
                            supportingContent = { Text("v${artifact.version} • ${artifact.mimeType}") },
                        )
                    }
                }
            }
            if (state.runs.isNotEmpty()) {
                item { Text("历史研究", style = MaterialTheme.typography.titleSmall) }
                items(state.runs) { run ->
                    Card(onClick = { viewModel.openRun(run.runId) }) {
                        Column(Modifier.padding(12.dp)) {
                            Text(run.question, style = MaterialTheme.typography.bodyMedium, maxLines = 2)
                            Text("${run.runStatus()} • ${run.policy()}", style = MaterialTheme.typography.bodySmall)
                        }
                    }
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AssistModeDropdown(selected: String, onSelect: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = selected,
            onValueChange = {},
            readOnly = true,
            label = { Text("辅助模式") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier.menuAnchor(),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            AssistanceMode.entries.filter { it != AssistanceMode.UNKNOWN }.forEach { mode ->
                DropdownMenuItem(text = { Text(mode.name) }, onClick = { onSelect(mode.name); expanded = false })
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AcademicPolicyDropdown(selected: String, onSelect: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = selected,
            onValueChange = {},
            readOnly = true,
            label = { Text("学术策略") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier.menuAnchor(),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            AcademicPolicy.entries.filter { it != AcademicPolicy.UNKNOWN }.forEach { policy ->
                DropdownMenuItem(text = { Text(policy.name) }, onClick = { onSelect(policy.name); expanded = false })
            }
        }
    }
}
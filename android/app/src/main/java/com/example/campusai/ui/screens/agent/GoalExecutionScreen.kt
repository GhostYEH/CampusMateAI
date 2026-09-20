package com.example.campusai.ui.screens.agent

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.campusai.data.remote.agent.AgentJobDto
import com.example.campusai.data.remote.agent.AgentRunStatus
import com.example.campusai.data.repository.AgentRuntimeRepository
import com.example.campusai.ui.components.GlassButton as Button
import com.example.campusai.ui.components.GlassCard as Card
import com.example.campusai.ui.components.GlassOutlinedButton as OutlinedButton

@Composable
fun GoalExecutionScreen(
    repository: AgentRuntimeRepository,
    onBack: () -> Unit,
) {
    val vm: GoalExecutionViewModel = viewModel(factory = remember(repository) {
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T = GoalExecutionViewModel(repository) as T
        }
    })
    val state by vm.state.collectAsStateWithLifecycle()
    LaunchedEffect(Unit) { vm.load(); vm.loadWorldModel() }
    var newGoalName by remember { mutableStateOf("") }
    var minutes by remember { mutableStateOf("60") }

    androidx.compose.material3.Scaffold(topBar = { AgentTopBar("AI目标执行中心", onBack) }) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Card {
                    Column(Modifier.padding(16.dp)) {
                        Text("提出一个学习目标")
                        Spacer(Modifier.height(8.dp))
                        OutlinedTextField(
                            value = newGoalName,
                            onValueChange = { newGoalName = it },
                            label = { Text("例如：完成数据库期末复习") },
                            modifier = Modifier.fillMaxWidth(),
                        )
                        Spacer(Modifier.height(8.dp))
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedTextField(
                                value = minutes,
                                onValueChange = { minutes = it.filter(Char::isDigit).take(4) },
                                label = { Text("每日分钟") },
                                modifier = Modifier.weight(1f),
                            )
                            Button(
                                onClick = { vm.createGoal(newGoalName.trim()); newGoalName = "" },
                                enabled = newGoalName.isNotBlank() && !state.loading,
                                modifier = Modifier.padding(top = 8.dp),
                            ) { Text("创建目标") }
                        }
                    }
                }
            }
            item { Text("我的学习目标") }
            items(state.goals) { goal ->
                Card {
                    Column(Modifier.padding(16.dp)) {
                        Text(goal.name)
                        Text("进度 ${goal.progressPercent.toInt()}%${goal.targetDate?.let { " · 截止 $it" } ?: ""}")
                        Spacer(Modifier.height(8.dp))
                        Button(
                            onClick = { vm.generate(goal.goalId, minutes.toIntOrNull()?.coerceIn(1, 1440) ?: 60) },
                            enabled = !state.loading,
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text("生成计划草案") }
                    }
                }
            }
            state.summary?.let { summary ->
                item {
                    Card {
                        Column(Modifier.padding(16.dp)) {
                            Text(summary.headline)
                            Text("完成度 ${summary.completionPercent}% · ${summary.executedItemCount}/${summary.plannedItemCount} 项")
                            Text("下一步：${summary.nextAction}")
                            if (summary.warningCodes.isNotEmpty()) {
                                Text("数据质量警告：${summary.warningCodes.joinToString("、")}")
                            }
                            Spacer(Modifier.height(8.dp))
                            CandidateAnnotationRow(summary.candidateAnnotation)
                            Spacer(Modifier.height(8.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                if (summary.stage == "AWAITING_CONFIRMATION") Button(onClick = { vm.confirmPlan() }, enabled = !state.loading) { Text("确认计划") }
                                if (summary.stage == "READY_TO_EXECUTE") Button(onClick = { vm.executePlan() }, enabled = !state.loading) { Text("创建个人待办") }
                                if (summary.stage == "IN_PROGRESS") OutlinedButton(onClick = { vm.replan() }, enabled = !state.loading) { Text("重新规划") }
                            }
                        }
                    }
                }
            }
            item {
                WorldModelSection(
                    state = state.worldModel,
                    onToggleSource = { sourceKey, status -> vm.setDataSourceStatus(sourceKey, status) },
                    enabled = !state.loading,
                )
            }
            item { Text("执行记录") }
            items(state.jobs.filter { it.kind().name == "learning_goal" }) { job ->
                JobRow(job = job, onControl = { action -> vm.control(job, action) }, enabled = !state.loading)
            }
            state.error?.let { error ->
                item { Text(error, color = androidx.compose.material3.MaterialTheme.colorScheme.error) }
            }
        }
    }
}

@Composable
private fun JobRow(job: AgentJobDto, onControl: (String) -> Unit, enabled: Boolean) {
    Card {
        Column(Modifier.padding(16.dp)) {
            Text("目标计划 · ${job.runStatus().name}")
            job.inputRef["plan_id"]?.toString()?.let { Text("计划 $it") }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                when (job.runStatus()) {
                    AgentRunStatus.RUNNING, AgentRunStatus.QUEUED -> OutlinedButton(onClick = { onControl("pause") }, enabled = enabled) { Text("暂停") }
                    AgentRunStatus.PAUSED -> Button(onClick = { onControl("resume") }, enabled = enabled) { Text("恢复") }
                    AgentRunStatus.FAILED, AgentRunStatus.PARTIAL, AgentRunStatus.CANCELLED -> Button(onClick = { onControl("retry") }, enabled = enabled) { Text("重试") }
                    else -> Unit
                }
            }
        }
    }
}

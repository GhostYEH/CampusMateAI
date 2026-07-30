package com.example.campusai.ui.screens.tasks

import androidx.compose.animation.core.*
import androidx.compose.foundation.border
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.Task
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.ModeBadge
import com.example.campusai.ui.components.SectionHead
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TasksScreen(repository: AppRepository) {
    val tasks by repository.tasks.collectAsState()
    val pendingCount by repository.pendingCount.collectAsState()
    val mockMode by repository.mockMode.collectAsState()
    val scope = rememberCoroutineScope()

    var newTaskTitle by remember { mutableStateOf("") }
    var newTaskDue by remember { mutableStateOf("") }
    var showAddSheet by remember { mutableStateOf(false) }

    val animatedAlpha by animateFloatAsState(
        targetValue = 1f,
        animationSpec = tween(400, easing = CubicBezierEasing(0.2f, 0.8f, 0.2f, 1f))
    )

    Scaffold(
        floatingActionButton = {
            FloatingActionButton(
                onClick = { showAddSheet = true },
                containerColor = Primary,
                shape = RoundedCornerShape(12.dp)
            ) {
                Icon(Icons.Default.Add, "新建待办", tint = Surface)
            }
        },
        containerColor = Background
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 20.dp, vertical = 16.dp)
                .graphicsLayer { alpha = animatedAlpha },
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text("待办事项", style = MaterialTheme.typography.headlineMedium)
                        Text("集中处理与当前模块相关的校园事务。", color = Muted, fontSize = 13.sp)
                    }
                    ModeBadge(mockMode)
                }
            }

            item {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(10.dp))
                        .background(Surface)
                        .border(1.dp, Line, RoundedCornerShape(10.dp))
                        .padding(14.dp)
                ) {
                    SectionHead("我的待办", badge = pendingCount)
                    Spacer(Modifier.height(8.dp))
                }
            }

            items(tasks, key = { it.id }) { task ->
                TaskCard(task, repository)
            }

            if (tasks.isEmpty()) {
                item {
                    Column(
                        modifier = Modifier.fillMaxWidth().padding(vertical = 40.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Icon(Icons.Default.CheckCircle, null, tint = Muted, modifier = Modifier.size(36.dp))
                        Spacer(Modifier.height(10.dp))
                        Text("暂时没有待办，去给今天安排一个小目标吧。", color = Muted, fontSize = 12.sp)
                    }
                }
            }
        }
    }

    if (showAddSheet) {
        ModalBottomSheet(
            onDismissRequest = { showAddSheet = false },
            containerColor = Surface,
            shape = RoundedCornerShape(topStart = 14.dp, topEnd = 14.dp)
        ) {
            Column(
                modifier = Modifier.padding(22.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                Text("新建待办", style = MaterialTheme.typography.titleLarge)
                OutlinedTextField(
                    value = newTaskTitle,
                    onValueChange = { newTaskTitle = it },
                    label = { Text("任务名称") },
                    placeholder = { Text("例如：完成数据结构实验报告") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(8.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Primary,
                        unfocusedBorderColor = InputBorder
                    )
                )
                OutlinedTextField(
                    value = newTaskDue,
                    onValueChange = { newTaskDue = it },
                    label = { Text("截止时间") },
                    placeholder = { Text("例如：今天 23:59") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(8.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Primary,
                        unfocusedBorderColor = InputBorder
                    )
                )
                Button(
                    onClick = {
                        if (newTaskTitle.isNotBlank()) {
                            scope.launch {
                                repository.addTask(newTaskTitle.trim(), newTaskDue.ifBlank { "待设置" })
                                newTaskTitle = ""
                                newTaskDue = ""
                                showAddSheet = false
                            }
                        }
                    },
                    enabled = newTaskTitle.isNotBlank(),
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Primary)
                ) {
                    Text("添加任务", fontWeight = FontWeight.SemiBold)
                }
                Spacer(Modifier.height(16.dp))
            }
        }
    }
}

@Composable
private fun TaskCard(task: Task, repository: AppRepository) {
    val scope = rememberCoroutineScope()
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(Surface)
            .border(1.dp, Line, RoundedCornerShape(10.dp))
            .padding(horizontal = 14.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(9.dp)
    ) {
        Checkbox(
            checked = task.done,
            onCheckedChange = { scope.launch { repository.toggleTask(task.id) } },
            colors = CheckboxDefaults.colors(checkedColor = Success, uncheckedColor = Muted)
        )
        Column(modifier = Modifier.weight(1f)) {
            Text(
                task.title,
                fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                color = if (task.done) Muted else TextPrimary
            )
            Text(
                "${task.due} · ${task.course}",
                fontSize = 11.sp,
                color = Muted
            )
        }
        IconButton(onClick = { scope.launch { repository.deleteTask(task.id) } }) {
            Icon(Icons.Default.Delete, "删除", tint = Muted, modifier = Modifier.size(18.dp))
        }
    }
}


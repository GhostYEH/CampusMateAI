package com.example.campusai.ui.screens.tasks

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.Task
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.ModeBadge
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch

private val TaskBlue = Color(0xFF5368E8)
private val TaskBlueDeep = Color(0xFF3449C7)
private val TaskOrange = Color(0xFFFFA43A)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TasksScreen(repository: AppRepository) {
    val tasks by repository.tasks.collectAsState()
    val pendingCount by repository.pendingCount.collectAsState()
    val mockMode by repository.mockMode.collectAsState()
    val reduceMotion by repository.reduceMotion.collectAsState()
    val scope = rememberCoroutineScope()
    var filter by remember { mutableStateOf("待完成") }
    var showAddSheet by remember { mutableStateOf(false) }
    var deletingTask by remember { mutableStateOf<Task?>(null) }
    val filtered = tasks.filter {
        when (filter) {
            "已完成" -> it.done
            "全部" -> true
            else -> !it.done
        }
    }

    Scaffold(
        containerColor = Background,
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { showAddSheet = true },
                icon = { Icon(Icons.Default.Add, null) },
                text = { Text("新建待办", fontWeight = FontWeight.Bold) },
                containerColor = TaskBlue,
                contentColor = Color.White,
                shape = RoundedCornerShape(16.dp),
            )
        },
    ) { inner ->
        LazyColumn(
            Modifier.fillMaxSize().padding(inner).background(Background),
            contentPadding = PaddingValues(16.dp, 12.dp, 16.dp, 100.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item { TaskHeader(mockMode) }
            item { TaskHero(tasks, pendingCount, reduceMotion) }
            item {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(listOf("待完成", "已完成", "全部")) { item ->
                        FilterChip(
                            selected = filter == item,
                            onClick = { filter = item },
                            label = { Text(item) },
                            leadingIcon = if (filter == item) {
                                { Icon(Icons.Default.Check, null, Modifier.size(16.dp)) }
                            } else null,
                            shape = RoundedCornerShape(12.dp),
                            colors = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = PrimarySoft,
                                selectedLabelColor = Primary,
                            ),
                            border = FilterChipDefaults.filterChipBorder(
                                enabled = true,
                                selected = filter == item,
                                borderColor = Line,
                                selectedBorderColor = Primary.copy(alpha = .24f),
                            ),
                        )
                    }
                }
            }
            item {
                Row(Modifier.fillMaxWidth(), Arrangement.SpaceBetween, Alignment.CenterVertically) {
                    Text(filter, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                    Text("${filtered.size} 项", color = Muted, fontSize = 12.sp)
                }
            }
            if (filtered.isEmpty()) {
                item { TaskEmpty(filter) }
            } else {
                items(filtered, key = { it.id }) { task ->
                    TaskCard(
                        task = task,
                        reduceMotion = reduceMotion,
                        onToggle = { scope.launch { repository.toggleTask(task.id) } },
                        onDelete = { deletingTask = task },
                    )
                }
            }
        }
    }

    if (showAddSheet) {
        AddTaskSheet(
            onDismiss = { showAddSheet = false },
            onAdd = { title, due ->
                scope.launch {
                    repository.addTask(title, due)
                    showAddSheet = false
                }
            },
        )
    }
    deletingTask?.let { task ->
        AlertDialog(
            onDismissRequest = { deletingTask = null },
            icon = { Icon(Icons.Default.DeleteOutline, null, tint = Danger) },
            title = { Text("删除这项待办？") },
            text = { Text(task.title, color = Muted) },
            confirmButton = {
                TextButton(onClick = {
                    scope.launch { repository.deleteTask(task.id) }
                    deletingTask = null
                }) { Text("删除", color = Danger) }
            },
            dismissButton = { TextButton(onClick = { deletingTask = null }) { Text("取消") } },
            containerColor = Surface,
        )
    }
}

@Composable
private fun TaskHeader(mockMode: Boolean) {
    Row(Modifier.fillMaxWidth(), Arrangement.SpaceBetween, Alignment.CenterVertically) {
        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text("待办", fontSize = 26.sp, fontWeight = FontWeight.ExtraBold)
            Text("今天先完成最重要的一小步", color = Muted, fontSize = 13.sp)
        }
        ModeBadge(mockMode)
    }
}

@Composable
private fun TaskHero(tasks: List<Task>, pending: Int, reduceMotion: Boolean) {
    val progress = if (tasks.isEmpty()) 0f else tasks.count { it.done }.toFloat() / tasks.size
    Box(
        Modifier.fillMaxWidth().height(166.dp).clip(RoundedCornerShape(26.dp))
            .background(Brush.linearGradient(listOf(TaskBlue, TaskBlueDeep)))
            .enterAnimation(enabled = !reduceMotion),
    ) {
        Box(
            Modifier.size(160.dp).offset(x = 248.dp, y = (-62).dp).clip(CircleShape)
                .background(Color.White.copy(alpha = .08f)),
        )
        Row(
            Modifier.fillMaxSize().padding(20.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(7.dp)) {
                Text("今日进度", color = Color.White.copy(alpha = .75f), fontSize = 12.sp)
                Text(
                    if (pending == 0) "都完成啦" else "还有 $pending 项",
                    color = Color.White,
                    fontSize = 25.sp,
                    fontWeight = FontWeight.ExtraBold,
                )
                Text("专注当下，不必一次做完所有事", color = Color.White.copy(alpha = .78f), fontSize = 11.sp)
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Bolt, null, tint = TaskOrange, modifier = Modifier.size(16.dp))
                    Text("优先处理临近截止任务", color = Color.White, fontSize = 11.sp)
                }
            }
            Box(contentAlignment = Alignment.Center) {
                CircularProgressIndicator(
                    progress = { progress },
                    modifier = Modifier.size(72.dp),
                    color = TaskOrange,
                    trackColor = Color.White.copy(alpha = .18f),
                    strokeWidth = 7.dp,
                )
                Text("${(progress * 100).toInt()}%", color = Color.White, fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
private fun TaskCard(
    task: Task,
    reduceMotion: Boolean,
    onToggle: () -> Unit,
    onDelete: () -> Unit,
) {
    val container by animateColorAsState(
        if (task.done) Success.copy(alpha = .06f) else Surface,
        tween(if (reduceMotion) 0 else 240),
        label = "task-color",
    )
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(container)
            .border(1.dp, if (task.done) Success.copy(alpha = .18f) else Line, RoundedCornerShape(20.dp))
            .campusClickable(onClick = onToggle)
            .padding(start = 12.dp, top = 12.dp, end = 6.dp, bottom = 12.dp)
            .enterAnimation(enabled = !reduceMotion),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Checkbox(
            checked = task.done,
            onCheckedChange = { onToggle() },
            colors = CheckboxDefaults.colors(checkedColor = Success, uncheckedColor = Primary),
        )
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text(
                task.title,
                fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                color = if (task.done) Muted else TextPrimary,
                textDecoration = if (task.done) TextDecoration.LineThrough else null,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(7.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Schedule, null, tint = if (task.done) Muted else TaskOrange, modifier = Modifier.size(14.dp))
                Text(task.due, color = Muted, fontSize = 11.sp)
                Text("·", color = Muted)
                Text(task.course, color = Muted, fontSize = 11.sp)
            }
        }
        IconButton(onClick = onDelete) {
            Icon(Icons.Default.DeleteOutline, "删除待办", tint = Muted, modifier = Modifier.size(20.dp))
        }
    }
}

@Composable
private fun TaskEmpty(filter: String) {
    Column(
        Modifier.fillMaxWidth().padding(vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Icon(Icons.Default.CheckCircle, null, tint = Success, modifier = Modifier.size(38.dp))
        Text(if (filter == "待完成") "待办已清空，做得不错" else "这里暂时没有内容", fontWeight = FontWeight.Bold)
        Text("给自己留一点休息时间吧", color = Muted, fontSize = 12.sp)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AddTaskSheet(onDismiss: () -> Unit, onAdd: (String, String) -> Unit) {
    var title by remember { mutableStateOf("") }
    var due by remember { mutableStateOf("") }
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor = Surface,
        shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp),
    ) {
        Column(
            Modifier.fillMaxWidth().padding(start = 22.dp, end = 22.dp, bottom = 34.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Text("新建待办", fontSize = 22.sp, fontWeight = FontWeight.ExtraBold)
            Text("把任务写清楚，开始会更轻松", color = Muted, fontSize = 12.sp)
            OutlinedTextField(
                value = title,
                onValueChange = { title = it },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("任务名称") },
                placeholder = { Text("例如：完成数据结构实验报告") },
                singleLine = true,
                shape = RoundedCornerShape(14.dp),
                leadingIcon = { Icon(Icons.Default.EditNote, null) },
            )
            OutlinedTextField(
                value = due,
                onValueChange = { due = it },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("截止时间") },
                placeholder = { Text("例如：今天 23:59") },
                singleLine = true,
                shape = RoundedCornerShape(14.dp),
                leadingIcon = { Icon(Icons.Default.CalendarMonth, null) },
            )
            Button(
                onClick = { onAdd(title.trim(), due.ifBlank { "待设置" }) },
                enabled = title.isNotBlank(),
                modifier = Modifier.fillMaxWidth().height(50.dp),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(containerColor = TaskBlue),
            ) { Text("添加任务", fontWeight = FontWeight.Bold) }
        }
    }
}

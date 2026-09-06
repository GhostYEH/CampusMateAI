package com.example.campusai.ui.screens.tasks

import com.example.campusai.ui.components.GlassButton as Button
import com.example.campusai.ui.components.GlassExtendedFloatingActionButton as ExtendedFloatingActionButton
import com.example.campusai.ui.components.GlassIconButton as IconButton
import com.example.campusai.ui.components.GlassTextButton as TextButton

import androidx.lifecycle.compose.collectAsStateWithLifecycle

import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.Task
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.screens.shell.floatingDockContentBottomPadding
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.DateTimeFormatter

private val ScreenLavender: Color @Composable get() = Background
private val TaskOrange: Color @Composable get() = Accent
private val TaskGreen: Color @Composable get() = Success
private val TaskBlue: Color @Composable get() = Primary

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TasksScreen(repository: AppRepository, onNavigate: (String) -> Unit = {}) {
    val tasks by repository.tasks.collectAsStateWithLifecycle()
    val backendOnline by repository.backendOnline.collectAsStateWithLifecycle()
    val taskError by repository.taskError.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    var filter by remember { mutableStateOf("全部") }
    var search by remember { mutableStateOf("") }
    var showAddSheet by remember { mutableStateOf(false) }
    var showImportDialog by remember { mutableStateOf(false) }
    var deletingTask by remember { mutableStateOf<Task?>(null) }
    val importSnackbar = remember { SnackbarHostState() }

    LaunchedEffect(Unit) { repository.refreshTasks() }
    val pending = remember(tasks) { tasks.filterNot(Task::done) }
    val today = remember(pending) { pending.filter { it.due.contains("今天") || it.due.contains(LocalDate.now().toString()) } }
    val nearDeadline = remember(pending) { pending.filter { task ->
        task.due.contains("今天") || task.due.contains("明天") || task.due.contains("截止")
    } }
    val courses = remember(tasks) { tasks.map(Task::course).filter { it.isNotBlank() }.distinct() }
    val visibleTasks = remember(tasks, filter, search) {
        tasks.filter { task ->
            val matchesFilter = when (filter) {
                "今日" -> task in today
                "课程" -> task.course.isNotBlank()
                "个人事务" -> task.course.contains("个人")
                "已完成" -> task.done
                else -> true
            }
            matchesFilter && (search.isBlank() || task.title.contains(search, true) || task.course.contains(search, true))
        }
    }
    val progress = if (tasks.isEmpty()) 0f else tasks.count(Task::done).toFloat() / tasks.size

    Box(Modifier.fillMaxSize().background(ScreenLavender)) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(
                start = 16.dp,
                top = 0.dp,
                end = 16.dp,
                bottom = floatingDockContentBottomPadding(
                    WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding(),
                ) + 86.dp,
            ),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.Top) {
                    Column {
                        Text("待办", color = TextPrimary, fontWeight = FontWeight.ExtraBold, fontSize = 32.sp)
                        Spacer(Modifier.height(4.dp))
                        Text("把重要事情安排得更清楚", color = Muted, fontSize = 15.sp)
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        IconButton(onClick = { showImportDialog = true }) { Icon(Icons.Default.UploadFile, "导入学习材料", tint = Primary) }
                        Surface(shape = RoundedCornerShape(12.dp), color = Surface, shadowElevation = 2.dp) {
                        Row(Modifier.padding(horizontal = 12.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                            Box(Modifier.size(9.dp).clip(CircleShape).background(if (backendOnline) TaskGreen else TaskOrange))
                            Spacer(Modifier.width(7.dp))
                            Text(if (backendOnline) "真实后端" else "等待后端", fontSize = 12.sp, color = TextPrimary)
                        }
                        }
                    }
                }
            }
            taskError?.let { message ->
                item {
                    Surface(shape = RoundedCornerShape(15.dp), color = AlertErrorBg) {
                        Row(Modifier.padding(horizontal = 13.dp, vertical = 9.dp), verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.CloudOff, null, tint = TaskOrange, modifier = Modifier.size(17.dp))
                            Spacer(Modifier.width(7.dp))
                            Text(message, Modifier.weight(1f), color = AlertErrorText, fontSize = 12.sp)
                            TextButton(onClick = { scope.launch { repository.refreshTasks() } }) { Text("重试", color = TaskBlue) }
                        }
                    }
                }
            }
            item { TaskOverview(today.size, nearDeadline.size, tasks.count(Task::done), tasks.size, progress) }
            item { TaskDateStrip(onCalendar = { onNavigate("task_calendar") }) }
            item {
                Column(
                    Modifier.clip(RoundedCornerShape(24.dp)).background(Surface).padding(14.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    OutlinedTextField(
                        value = search,
                        onValueChange = { search = it },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        placeholder = { Text("搜索任务 / 课程 / 关键词", color = Muted) },
                        leadingIcon = { Icon(Icons.Default.Search, null, tint = Muted) },
                        shape = RoundedCornerShape(16.dp),
                        colors = OutlinedTextFieldDefaults.colors(unfocusedBorderColor = Line, focusedBorderColor = Primary),
                    )
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                        items(listOf("全部", "今日", "课程", "个人事务", "已完成")) { label ->
                            FilterChip(
                                selected = filter == label,
                                onClick = { filter = label },
                                label = { Text(label, fontSize = 13.sp) },
                                shape = RoundedCornerShape(18.dp),
                                colors = FilterChipDefaults.filterChipColors(selectedContainerColor = TaskBlue, selectedLabelColor = Color.White),
                                border = FilterChipDefaults.filterChipBorder(borderColor = Line, selectedBorderColor = TaskBlue, enabled = true, selected = filter == label),
                            )
                        }
                    }
                }
            }
            item {
                SmartFocusCard(
                    task = visibleTasks.firstOrNull { !it.done },
                    onFocus = { task -> onNavigate("focus?taskId=${Uri.encode(task.id)}") },
                )
            }
            item {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text(if (filter == "全部") "今日重点" else filter, fontWeight = FontWeight.ExtraBold, fontSize = 19.sp, color = TextPrimary)
                    Text("${visibleTasks.size} 项", color = Muted, fontSize = 13.sp)
                }
            }
            if (visibleTasks.isEmpty()) {
                item { EmptyTasks(backendOnline, onRetry = { scope.launch { repository.refreshTasks() } }) }
            } else {
                itemsIndexed(
                    items = visibleTasks,
                    key = { index, task -> task.listKey(index) },
                ) { _, task ->
                    DashboardTaskRow(
                        task = task,
                        onOpen = { onNavigate("task_detail/${Uri.encode(task.id)}") },
                        onToggle = { scope.launch { repository.toggleTask(task.id) } },
                        onDelete = { deletingTask = task },
                    )
                }
            }
            if (courses.isNotEmpty()) {
                item {
                    Column(Modifier.clip(RoundedCornerShape(24.dp)).background(Surface).padding(16.dp)) {
                        Text("任务来源课程", fontWeight = FontWeight.Bold, color = TextPrimary, fontSize = 17.sp)
                        Spacer(Modifier.height(12.dp))
                        LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            items(courses) { course ->
                                Surface(color = PrimarySoft, shape = RoundedCornerShape(14.dp)) {
                                    Text(course, Modifier.padding(horizontal = 14.dp, vertical = 10.dp), color = Primary, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                                }
                            }
                        }
                    }
                }
            }
        }

        ExtendedFloatingActionButton(
            onClick = { showAddSheet = true },
            icon = { Icon(Icons.Default.Add, null) },
            text = { Text("新建待办", fontWeight = FontWeight.Bold) },
            containerColor = TaskBlue,
            contentColor = Color.White,
            shape = RoundedCornerShape(18.dp),
            modifier = Modifier.align(Alignment.BottomEnd).padding(
                end = 20.dp,
                bottom = floatingDockContentBottomPadding(
                    WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding(),
                ) + 14.dp,
            ),
        )
        SnackbarHost(
            importSnackbar,
            Modifier.align(Alignment.BottomCenter).padding(
                start = 16.dp,
                end = 16.dp,
                bottom = floatingDockContentBottomPadding(
                    WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding(),
                ) + 76.dp,
            ),
        )
    }

    if (showAddSheet) AddTaskSheet(
        onDismiss = { showAddSheet = false },
        onAdd = { title, due -> scope.launch { repository.addTask(title, due); showAddSheet = false } },
    )
    if (showImportDialog) TaskImportDialog(
        repository = repository,
        onDismiss = { showImportDialog = false },
        onImported = { createdCount, skippedExistingCount ->
            showImportDialog = false
            val message = buildString {
                append("已创建 $createdCount 项")
                if (skippedExistingCount > 0) append("，保留已有 $skippedExistingCount 项")
            }
            scope.launch { importSnackbar.showSnackbar(message) }
        },
    )
    deletingTask?.let { task ->
        AlertDialog(
            onDismissRequest = { deletingTask = null },
            title = { Text("删除这项待办？", fontWeight = FontWeight.Bold) },
            text = { Text("删除后会同步写入后端数据库。", color = Muted) },
            confirmButton = { TextButton(onClick = { scope.launch { repository.deleteTask(task.id) }; deletingTask = null }) { Text("删除", color = Danger) } },
            dismissButton = { TextButton(onClick = { deletingTask = null }) { Text("取消") } },
        )
    }
}

private fun Task.listKey(index: Int): String =
    "task|${id.ifBlank { "$title|$due|$course" }}|$index"

@Composable
private fun TaskOverview(today: Int, near: Int, done: Int, all: Int, progress: Float) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).background(Surface).padding(16.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        listOf("今日待办" to today, "临近截止" to near, "已完成" to done, "全部任务" to all).forEachIndexed { index, (label, value) ->
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(label, color = Muted, fontSize = 11.sp)
                Spacer(Modifier.height(7.dp))
                Text(value.toString(), color = when (index) { 1 -> TaskOrange; 2 -> TaskGreen; else -> TextPrimary }, fontWeight = FontWeight.ExtraBold, fontSize = 27.sp)
                Box(Modifier.padding(top = 5.dp).width(16.dp).height(3.dp).clip(CircleShape).background(if (index == 1) TaskOrange else TaskBlue))
            }
        }
        Box(contentAlignment = Alignment.Center) {
            CircularProgressIndicator(progress = { progress }, modifier = Modifier.size(62.dp), color = TaskBlue, trackColor = PrimarySoft, strokeWidth = 6.dp)
            Text("${(progress * 100).toInt()}%", color = TaskBlue, fontSize = 13.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun TaskDateStrip(onCalendar: () -> Unit) {
    val now = LocalDate.now()
    val formatter = DateTimeFormatter.ofPattern("d")
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(Modifier.weight(1f).clip(RoundedCornerShape(22.dp)).background(Surface).padding(horizontal = 12.dp, vertical = 11.dp), horizontalArrangement = Arrangement.SpaceAround) {
            (-3..3).forEach { offset ->
                val date = now.plusDays(offset.toLong())
                val selected = offset == 0
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(listOf("一", "二", "三", "四", "五", "六", "日")[date.dayOfWeek.value - 1], color = Muted, fontSize = 11.sp)
                    Spacer(Modifier.height(5.dp))
                    Box(Modifier.size(35.dp).clip(CircleShape).background(if (selected) TaskBlue else Color.Transparent), contentAlignment = Alignment.Center) {
                        Text(date.format(formatter), color = if (selected) Color.White else TextPrimary, fontWeight = FontWeight.Bold)
                    }
                    Box(Modifier.padding(top = 5.dp).size(6.dp).clip(CircleShape).background(if (selected) TaskOrange else Primary.copy(alpha = .55f)))
                }
            }
        }
        Surface(onClick = onCalendar, shape = RoundedCornerShape(22.dp), color = Surface) {
            Column(Modifier.padding(horizontal = 14.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(Icons.Default.CalendarMonth, null, tint = Primary)
                Text("日历视图", color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
private fun SmartFocusCard(task: Task?, onFocus: (Task) -> Unit) {
    val shape = RoundedCornerShape(24.dp)
    Box(Modifier.fillMaxWidth().clip(shape).background(Brush.linearGradient(listOf(PrimarySoft, Surface))).border(1.dp, Primary.copy(alpha = .22f), shape).padding(18.dp)) {
        Column(Modifier.padding(end = 108.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) { Icon(Icons.Default.AutoAwesome, null, tint = Primary, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(7.dp)); Text("智能聚焦", color = Primary, fontWeight = FontWeight.Bold) }
            Text(task?.title ?: "暂时没有需要聚焦的待办", color = TextPrimary, fontWeight = FontWeight.ExtraBold, fontSize = 18.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Text(task?.let { "${it.due} · ${it.course}" } ?: "完成新建待办后，可以从这里直接开始专注。", color = Muted, fontSize = 12.sp)
        }
        if (task != null) Button(onClick = { onFocus(task) }, modifier = Modifier.align(Alignment.CenterEnd), shape = RoundedCornerShape(22.dp), colors = ButtonDefaults.buttonColors(containerColor = Color.Transparent, contentColor = Primary)) {
            Text("去专注", fontWeight = FontWeight.Bold)
        }
    }
}

private fun importanceLabel(importance: String): String = when (importance) {
    "urgent" -> "紧急"; "high" -> "学业关键"; "important" -> "较重要"
    "normal" -> "普通"; "low" -> "次要"; else -> "待评"
}
private fun importanceBgColor(importance: String): Color = when (importance) {
    "urgent" -> Color(0xFFFFE0E3); "high" -> Color(0xFFFFEBED); "important" -> Color(0xFFFFF4DD)
    "normal" -> Color(0xFFEEF1F6); "low" -> Color(0xFFE8F7F0); else -> Color(0xFFEEF1F6)
}
private fun importanceFgColor(importance: String): Color = when (importance) {
    "urgent" -> Color(0xFFD6394B); "high" -> Color(0xFFDD6570); "important" -> Color(0xFFDA9739)
    "normal" -> Color(0xFF6B7280); "low" -> Color(0xFF3E9E7F); else -> Color(0xFF9CA3AF)
}

@Composable
private fun DashboardTaskRow(task: Task, onOpen: () -> Unit, onToggle: () -> Unit, onDelete: () -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(Surface).clickable(onClick = onOpen).padding(horizontal = 14.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
        Checkbox(checked = task.done, onCheckedChange = { onToggle() }, colors = CheckboxDefaults.colors(checkedColor = TaskGreen, uncheckedColor = TaskBlue))
        Spacer(Modifier.width(8.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text(task.title, color = if (task.done) Muted else TextPrimary, fontWeight = FontWeight.SemiBold, fontSize = 15.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Schedule, null, tint = Muted, modifier = Modifier.size(14.dp))
                Spacer(Modifier.width(4.dp)); Text(task.due, color = Muted, fontSize = 12.sp)
                if (task.course.isNotBlank()) { Spacer(Modifier.width(8.dp)); Surface(color = PrimarySoft, shape = RoundedCornerShape(6.dp)) { Text(task.course, Modifier.padding(horizontal = 6.dp, vertical = 2.dp), color = Primary, fontSize = 10.sp) } }
                if (task.importance.isNotBlank() && task.importance != "unknown") { Spacer(Modifier.width(8.dp)); Surface(color = importanceBgColor(task.importance), shape = RoundedCornerShape(6.dp)) { Text(importanceLabel(task.importance), Modifier.padding(horizontal = 6.dp, vertical = 2.dp), color = importanceFgColor(task.importance), fontSize = 10.sp) } }
            }
        }
        IconButton(onClick = onDelete) { Icon(Icons.Default.MoreVert, null, tint = Muted) }
    }
}

@Composable
private fun EmptyTasks(online: Boolean, onRetry: () -> Unit) {
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(Surface).padding(vertical = 38.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Icon(if (online) Icons.Default.TaskAlt else Icons.Default.CloudOff, null, tint = Primary, modifier = Modifier.size(36.dp))
        Text(if (online) "还没有待办" else "暂时无法获取后端数据", color = TextPrimary, fontWeight = FontWeight.Bold)
        Text(if (online) "点击右下角新建第一项待办" else "请检查网络或稍后重试", color = Muted, fontSize = 12.sp)
        if (!online) TextButton(onClick = onRetry) { Text("重新获取", color = Primary) }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AddTaskSheet(onDismiss: () -> Unit, onAdd: (String, String) -> Unit) {
    var title by remember { mutableStateOf("") }
    var due by remember { mutableStateOf("") }
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = Surface, shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp)) {
        Column(Modifier.fillMaxWidth().padding(start = 22.dp, end = 22.dp, bottom = 34.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Text("新建待办", fontSize = 23.sp, fontWeight = FontWeight.ExtraBold)
            Text("保存后会直接写入你的后端任务库。", color = Muted, fontSize = 13.sp)
            OutlinedTextField(value = title, onValueChange = { title = it }, modifier = Modifier.fillMaxWidth(), label = { Text("任务名称") }, leadingIcon = { Icon(Icons.Default.EditNote, null) }, singleLine = true, shape = RoundedCornerShape(14.dp))
            OutlinedTextField(value = due, onValueChange = { due = it }, modifier = Modifier.fillMaxWidth(), label = { Text("截止时间") }, placeholder = { Text("例如：今天 23:59") }, leadingIcon = { Icon(Icons.Default.CalendarMonth, null) }, singleLine = true, shape = RoundedCornerShape(14.dp))
            Button(onClick = { onAdd(title.trim(), due.ifBlank { "待设置" }) }, enabled = title.isNotBlank(), modifier = Modifier.fillMaxWidth().height(52.dp), shape = RoundedCornerShape(16.dp), colors = ButtonDefaults.buttonColors(containerColor = TaskBlue)) { Text("保存到待办", fontWeight = FontWeight.Bold) }
        }
    }
}

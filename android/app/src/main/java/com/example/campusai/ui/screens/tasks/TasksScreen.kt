package com.example.campusai.ui.screens.tasks

import com.example.campusai.ui.components.GlassButton as Button
import com.example.campusai.ui.components.GlassExtendedFloatingActionButton as ExtendedFloatingActionButton
import com.example.campusai.ui.components.GlassIconButton as IconButton
import com.example.campusai.ui.components.GlassTextButton as TextButton

import androidx.lifecycle.compose.collectAsStateWithLifecycle

import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.Image
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
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import com.example.campusai.R
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.Task
import com.example.campusai.data.model.Course
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.courseDateInstant
import com.example.campusai.data.repository.courseDeadlineInstant
import com.example.campusai.data.repository.isCurrentSemesterAt
import com.example.campusai.ui.screens.shell.floatingDockContentBottomPadding
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.Instant
import java.time.format.DateTimeFormatter

private val ScreenLavender: Color @Composable get() = Background
private val TaskOrange: Color @Composable get() = Accent
private val TaskGreen: Color @Composable get() = Success
private val TaskBlue: Color @Composable get() = Primary

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TasksScreen(repository: AppRepository, onNavigate: (String) -> Unit = {}) {
    val tasks by repository.tasks.collectAsStateWithLifecycle()
    val courseCatalog by repository.courses.collectAsStateWithLifecycle()
    val backendOnline by repository.backendOnline.collectAsStateWithLifecycle()
    val taskError by repository.taskError.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    var filter by remember { mutableStateOf("全部") }
    var selectedCourse by remember { mutableStateOf<String?>(null) }
    var search by remember { mutableStateOf("") }
    var showAddSheet by remember { mutableStateOf(false) }
    var showImportDialog by remember { mutableStateOf(false) }
    var deletingTask by remember { mutableStateOf<Task?>(null) }
    val importSnackbar = remember { SnackbarHostState() }

    LaunchedEffect(Unit) { repository.refreshCourses(); repository.refreshTasks() }
    val now = Instant.now()
    val currentAssignments = remember(tasks, courseCatalog, now.epochSecond / 60) {
        tasks.filter { it.isCurrentSemesterAssignment(courseCatalog, now) }
    }
    val completedAssignments = remember(tasks, courseCatalog, now.epochSecond / 60) {
        tasks.filter { it.done && it.isCurrentSemesterCourseTask(courseCatalog, now) }
    }
    val personalTasks = remember(tasks) { tasks.filterNot(Task::isCourseAssignment) }
    val pending = remember(currentAssignments, personalTasks) {
        currentAssignments.filterNot(Task::done) + personalTasks.filterNot(Task::done)
    }
    val allTasks = remember(currentAssignments, completedAssignments, personalTasks) {
        (currentAssignments + completedAssignments + personalTasks).distinctBy(Task::id)
    }
    val courseFilters = remember(currentAssignments, completedAssignments) {
        (currentAssignments + completedAssignments).map(Task::course).filter(String::isNotBlank).distinct().sorted()
    }
    val visibleTasks = remember(tasks, courseCatalog, filter, selectedCourse, search, now.epochSecond / 60) {
        val relevant = when (filter) {
            "全部" -> allTasks
            "个人事务" -> personalTasks
            "已完成" -> allTasks.filter(Task::done)
            else -> pending
        }
        relevant.filter { task ->
            val matchesFilter = when (filter) {
                "快截止" -> task.dueInstant()?.isBefore(now.plusSeconds(48 * 3600)) == true
                else -> true
            }
            matchesFilter && (filter == "个人事务" || selectedCourse == null || task.course == selectedCourse) &&
                (search.isBlank() || task.title.contains(search, true) || task.course.contains(search, true))
        }.sortedWith(compareBy<Task> { filter == "全部" && it.done }.thenBy { it.dueInstant() ?: Instant.MAX })
    }
    val dueSoon = if (filter == "待完成") visibleTasks.filter {
        it.dueInstant()?.isBefore(now.plusSeconds(48 * 3600)) == true
    } else emptyList()
    val groupedTasks = visibleTasks.filterNot { it in dueSoon }
        .groupBy { it.course.ifBlank { "个人事务" } }
    Box(Modifier.fillMaxSize().background(Color(0xFF172747))) {
        Image(painterResource(R.drawable.campus_twilight_original), contentDescription = null,
            modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
        Box(Modifier.fillMaxSize().background(Color(0xB8172747)))
        LazyColumn(
            modifier = Modifier.fillMaxSize().statusBarsPadding(),
            contentPadding = PaddingValues(
                start = 16.dp,
                top = 0.dp,
                end = 16.dp,
                bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + 92.dp,
            ),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.Top) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        IconButton(onClick = { onNavigate("home") }) {
                            Icon(Icons.Default.ArrowBack, contentDescription = "返回校园", tint = Color.White)
                        }
                    Column {
                        Text("待办", color = Color.White, fontWeight = FontWeight.ExtraBold, fontSize = 28.sp)
                        Spacer(Modifier.height(4.dp))
                        Text("${pending.size} 项待完成 · 课程作业与个人事务", color = Color.White.copy(alpha = .86f), fontSize = 14.sp)
                    }
                    }
                    IconButton(onClick = { showImportDialog = true }) {
                        Icon(Icons.Default.UploadFile, "导入个人事项", tint = Color.White)
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
                        placeholder = { Text("搜索作业或课程", color = Muted) },
                        leadingIcon = { Icon(Icons.Default.Search, null, tint = Muted) },
                        shape = RoundedCornerShape(16.dp),
                        colors = OutlinedTextFieldDefaults.colors(unfocusedBorderColor = Line, focusedBorderColor = Primary),
                    )
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                        items(listOf("全部", "待完成", "已完成", "个人事务")) { label ->
                            FilterChip(
                                selected = filter == label,
                                onClick = { filter = label; selectedCourse = null },
                                label = { Text(label, fontSize = 13.sp) },
                                shape = RoundedCornerShape(18.dp),
                                colors = FilterChipDefaults.filterChipColors(selectedContainerColor = TaskBlue, selectedLabelColor = Color.White),
                                border = FilterChipDefaults.filterChipBorder(borderColor = Line, selectedBorderColor = TaskBlue, enabled = true, selected = filter == label),
                            )
                        }
                    }
                    if (courseFilters.isNotEmpty() && filter != "个人事务") {
                        LazyRow(horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                            item {
                                FilterChip(selected = selectedCourse == null, onClick = { selectedCourse = null },
                                    label = { Text("所有课程", fontSize = 12.sp) })
                            }
                            items(courseFilters) { courseName ->
                                FilterChip(selected = selectedCourse == courseName,
                                    onClick = { selectedCourse = courseName },
                                    label = { Text(courseName, fontSize = 12.sp, maxLines = 1) })
                            }
                        }
                    }
                }
            }
            item {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text(if (filter == "全部") "全部任务" else if (filter == "待完成") "按课程查看" else filter,
                        fontWeight = FontWeight.ExtraBold, fontSize = 19.sp, color = Color.White)
                    Text("${visibleTasks.size} 项", color = Color.White.copy(alpha = .8f), fontSize = 13.sp)
                }
            }
            if (visibleTasks.isEmpty()) {
                item { EmptyTasks(backendOnline, filter, onRetry = { scope.launch { repository.refreshTasks() } }) }
            } else {
                if (dueSoon.isNotEmpty()) {
                    item { Text("快截止", color = Color(0xFFFFECD0), fontSize = 16.sp,
                        fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 6.dp)) }
                    itemsIndexed(dueSoon, key = { index, task -> task.listKey(index) }) { _, task ->
                        DashboardTaskRow(task,
                            onOpen = { onNavigate("task_detail/${Uri.encode(task.id)}") },
                            onToggle = { scope.launch { repository.toggleTask(task.id) } },
                            onDelete = { deletingTask = task })
                    }
                }
                groupedTasks.forEach { (courseName, group) ->
                    item { Text(courseName, color = Color(0xFFFFECD0), fontSize = 16.sp,
                        fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 6.dp)) }
                    itemsIndexed(group, key = { index, task -> task.listKey(index) }) { _, task ->
                        DashboardTaskRow(
                            task = task,
                            onOpen = { onNavigate("task_detail/${Uri.encode(task.id)}") },
                            onToggle = { scope.launch { repository.toggleTask(task.id) } },
                            onDelete = { deletingTask = task },
                        )
                    }
                }
            }
        }

        ExtendedFloatingActionButton(
            onClick = { showAddSheet = true },
            icon = { Icon(Icons.Default.Add, null) },
            text = { Text("个人待办", fontWeight = FontWeight.Bold) },
            containerColor = TaskBlue,
            contentColor = Color.White,
            shape = RoundedCornerShape(18.dp),
            modifier = Modifier.align(Alignment.BottomEnd).padding(
                end = 20.dp,
                bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + 14.dp,
            ),
        )
        SnackbarHost(
            importSnackbar,
            Modifier.align(Alignment.BottomCenter).padding(
                start = 16.dp,
                end = 16.dp,
                bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + 76.dp,
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

private fun Task.dueInstant(): Instant? = due.takeIf { it != "待设置" }?.courseDeadlineInstant()

private fun Task.isCourseAssignment(): Boolean = source in setOf("chaoxing", "chaoxing_notice", "course_notice")

private fun Task.isCurrentSemesterCourseTask(courses: List<Course>, now: Instant): Boolean {
    if (!isCourseAssignment()) return false
    val course = courses.firstOrNull { it.id == courseId }
        ?: courses.firstOrNull { it.name == this.course }
        ?: return false
    return course.isCurrentSemesterAt(now)
}

/** Only verified current-course assignments are promoted into automatic pending tasks. */
internal fun Task.isCurrentSemesterAssignment(courses: List<Course>, now: Instant): Boolean {
    if (source !in setOf("chaoxing", "chaoxing_notice", "course_notice")) return false
    if (source == "chaoxing_notice" &&
        !listOf(title, description).any { text ->
            listOf("作业", "实验", "练习", "习题", "报告").any { keyword -> text.contains(keyword) }
        }) return false
    val course = courses.firstOrNull { it.id == courseId }
        ?: courses.firstOrNull { it.name == this.course }
        ?: return false
    if (!course.isCurrentSemesterAt(now)) return false
    val noticeStart = startAt?.courseDateInstant()
    if (noticeStart != null && now.isBefore(noticeStart)) return false
    val deadline = dueInstant() ?: return false
    return now.isBefore(deadline)
}

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
        if (task.source in setOf("chaoxing", "chaoxing_notice", "course_notice")) {
            Icon(Icons.Default.Assignment, contentDescription = "课程作业", tint = TaskBlue,
                modifier = Modifier.size(28.dp))
        } else {
            Checkbox(checked = task.done, onCheckedChange = { onToggle() }, colors = CheckboxDefaults.colors(checkedColor = TaskGreen, uncheckedColor = TaskBlue))
        }
        Spacer(Modifier.width(8.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text(task.title, color = if (task.done) Muted else TextPrimary, fontWeight = FontWeight.SemiBold, fontSize = 15.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Schedule, null, tint = Muted, modifier = Modifier.size(14.dp))
                Spacer(Modifier.width(4.dp))
                Text("截止 ${task.due.replace('T', ' ').take(16)}", color = Muted, fontSize = 12.sp)
            }
            if (task.done) {
                Text(if (task.submittedAt != null) "平台已提交"
                    else if (task.isCourseAssignment()) "已确认完成" else "已完成",
                    color = TaskGreen, fontSize = 11.sp)
            }
            if (!task.done && task.source in setOf("chaoxing_notice", "course_notice")) {
                Text("提交状态待确认 · 请进入课程核对", color = Color(0xFF94633C), fontSize = 11.sp)
            }
        }
        if (task.source !in setOf("chaoxing", "chaoxing_notice", "course_notice")) IconButton(onClick = onDelete) { Icon(Icons.Default.MoreVert, null, tint = Muted) }
    }
}

@Composable
private fun EmptyTasks(online: Boolean, filter: String, onRetry: () -> Unit) {
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(Surface).padding(vertical = 38.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Icon(if (online) Icons.Default.TaskAlt else Icons.Default.CloudOff, null, tint = Primary, modifier = Modifier.size(36.dp))
        Text(if (online) "这里还没有${if (filter == "全部") "任务" else filter + "任务"}" else "暂时无法获取后端数据",
            color = TextPrimary, fontWeight = FontWeight.Bold)
        Text(if (online) "本学期课程作业会自动同步，也可以自己添加事务" else "请检查网络或稍后重试", color = Muted, fontSize = 12.sp)
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

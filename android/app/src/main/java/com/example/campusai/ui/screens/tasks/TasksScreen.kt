package com.example.campusai.ui.screens.tasks

import com.example.campusai.ui.components.GlassButton as Button
import com.example.campusai.ui.components.GlassIconButton as IconButton
import com.example.campusai.ui.components.GlassTextButton as TextButton

import androidx.lifecycle.compose.collectAsStateWithLifecycle

import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
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
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
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
import kotlinx.coroutines.delay
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
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    var filter by remember { mutableStateOf("待完成") }
    var selectedCourse by remember { mutableStateOf<String?>(null) }
    var search by remember { mutableStateOf("") }
    var showTaskEditor by remember { mutableStateOf(false) }
    var showCourseFilter by remember { mutableStateOf(false) }
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
    val courseFilters = remember(currentAssignments, completedAssignments, filter) {
        (if (filter == "待完成") currentAssignments.filterNot(Task::done) else currentAssignments + completedAssignments)
            .map(Task::course).filter(String::isNotBlank).distinct().sorted()
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
    val upcoming = visibleTasks.filter { !it.done }
    val todayTasks = upcoming.filter { it.dueInstant()?.isBefore(now.plusSeconds(24 * 3600)) == true }
    val weekTasks = upcoming.filter { it !in todayTasks && it.dueInstant()?.isBefore(now.plusSeconds(7 * 24 * 3600)) == true }
    val laterTasks = upcoming.filter { it !in todayTasks && it !in weekTasks }
    Box(Modifier.fillMaxSize()) {
        JournalBackdrop(Modifier.fillMaxSize())
        LazyColumn(
            modifier = Modifier.fillMaxSize().statusBarsPadding(),
            contentPadding = PaddingValues(
                start = 16.dp,
                top = 0.dp,
                end = 16.dp,
                bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + 30.dp,
            ),
            verticalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            item {
                Row(Modifier.fillMaxWidth().heightIn(min = 84.dp), verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = { onNavigate("home") }, modifier = Modifier.size(44.dp)) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "返回校园", tint = Color(0xFFF9EEDC))
                    }
                    Spacer(Modifier.width(8.dp))
                    Column(Modifier.weight(1f)) {
                        Text("待办", color = Color(0xFFFFF5E6), fontWeight = FontWeight.ExtraBold, fontSize = 28.sp)
                        Text("${pending.size} 件待处理 · ${todayTasks.size} 件今天优先", color = Color(0xFFD8D5C7), fontSize = 12.sp)
                    }
                    PaperPlusButton(onClick = { showTaskEditor = true })
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
                JournalSheet(Modifier.fillMaxWidth()) {
                  Column(Modifier.padding(11.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    OutlinedTextField(
                        value = search,
                        onValueChange = { search = it },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        textStyle = androidx.compose.ui.text.TextStyle(fontSize = 13.sp),
                        placeholder = { Text("搜索作业或课程", color = Muted) },
                        leadingIcon = { Icon(Icons.Default.Search, null, tint = Muted) },
                        shape = RoundedCornerShape(13.dp),
                        colors = OutlinedTextFieldDefaults.colors(unfocusedBorderColor = Line, focusedBorderColor = Primary),
                    )
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        items(listOf("全部", "待完成", "已完成", "个人事务")) { label ->
                            FilterChip(
                                selected = filter == label,
                                onClick = { filter = label; selectedCourse = null },
                                label = { Text(label, fontSize = 12.sp) },
                                shape = RoundedCornerShape(18.dp),
                                colors = FilterChipDefaults.filterChipColors(selectedContainerColor = TaskBlue, selectedLabelColor = Color.White),
                                border = FilterChipDefaults.filterChipBorder(borderColor = Line, selectedBorderColor = TaskBlue, enabled = true, selected = filter == label),
                            )
                        }
                    }
                    if (courseFilters.isNotEmpty() && filter != "个人事务") {
                        TextButton(onClick = { showCourseFilter = true }) {
                            Icon(Icons.Default.Tune, null, modifier = Modifier.size(16.dp))
                            Spacer(Modifier.width(5.dp))
                            Text(selectedCourse ?: "按课程筛选", fontSize = 12.sp, maxLines = 1)
                        }
                    }
                  }
                }
            }
            item {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text(if (filter == "待完成") "接下来要做" else filter,
                        fontWeight = FontWeight.ExtraBold, fontSize = 17.sp, color = Color(0xFFF5E8D4))
                    Text("${visibleTasks.size} 项", color = Color.White.copy(alpha = .8f), fontSize = 13.sp)
                }
            }
            if (visibleTasks.isEmpty()) {
                item { EmptyTasks(backendOnline, filter, onRetry = { scope.launch { repository.refreshTasks() } }) }
            } else {
                val sections = if (filter == "已完成") listOf("已盖章" to visibleTasks)
                    else listOf("今天优先" to todayTasks, "本周待办" to weekTasks, "之后处理" to laterTasks) +
                        (if (filter == "全部" || filter == "个人事务") listOf("已完成" to visibleTasks.filter(Task::done)) else emptyList())
                sections.filter { it.second.isNotEmpty() }.forEach { (label, group) ->
                    item { Text("$label  /  ${group.size}", color = Color(0xFFE7C99C), fontSize = 12.sp,
                        fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 6.dp, bottom = 1.dp)) }
                    itemsIndexed(group, key = { index, task -> task.listKey(index) }) { _, task ->
                        DashboardTaskRow(task,
                            onOpen = { onNavigate("task_detail/${Uri.encode(task.id)}") },
                            onToggle = { scope.launch { repository.toggleTask(task.id) } },
                            reduceMotion = reduceMotion)
                    }
                }
            }
        }

        SnackbarHost(
            importSnackbar,
            Modifier.align(Alignment.BottomCenter).padding(
                start = 16.dp,
                end = 16.dp,
                bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + 76.dp,
            ),
        )
    }

    if (showTaskEditor) TaskImportDialog(
        repository = repository,
        onDismiss = { showTaskEditor = false },
        onImported = { createdCount, skippedExistingCount ->
            showTaskEditor = false
            val message = buildString {
                append("已创建 $createdCount 项")
                if (skippedExistingCount > 0) append("，保留已有 $skippedExistingCount 项")
            }
            scope.launch { importSnackbar.showSnackbar(message) }
        },
    )
    if (showCourseFilter) AlertDialog(
        onDismissRequest = { showCourseFilter = false },
        title = { Text("按课程筛选") },
        text = {
            Column(Modifier.heightIn(max = 380.dp).verticalScroll(rememberScrollState())) {
                (listOf<String?>(null) + courseFilters).forEach { course ->
                    TextButton(onClick = { selectedCourse = course; showCourseFilter = false }, modifier = Modifier.fillMaxWidth()) {
                        Text(course ?: "所有课程", modifier = Modifier.fillMaxWidth(), color = JournalInk)
                    }
                }
            }
        },
        confirmButton = {},
    )
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
private fun DashboardTaskRow(task: Task, onOpen: () -> Unit, onToggle: () -> Unit, reduceMotion: Boolean) {
    var stamping by remember(task.id) { mutableStateOf(false) }
    val stampScale by animateFloatAsState(if (stamping) 1f else 1.4f, animationSpec = tween(340), label = "task stamp scale")
    val stampAlpha by animateFloatAsState(if (stamping) 1f else 0f, animationSpec = tween(340), label = "task stamp alpha")
    LaunchedEffect(stamping) {
        if (stamping) {
            delay(if (reduceMotion) 1 else 560)
            onToggle()
            stamping = false
        }
    }
    JournalSheet(Modifier.fillMaxWidth().clickable(onClick = onOpen)) {
        Box {
            Row(Modifier.fillMaxWidth().heightIn(min = 76.dp).padding(start = 11.dp, end = 14.dp, top = 9.dp, bottom = 9.dp), verticalAlignment = Alignment.CenterVertically) {
                val accent = when {
                    task.done -> Color(0xFF839D85)
                    task.dueInstant()?.isBefore(Instant.now().plusSeconds(24 * 3600)) == true -> JournalAmber
                    task.isCourseAssignment() -> JournalInk
                    else -> Color(0xFF738F9D)
                }
                Box(Modifier.width(3.dp).height(42.dp).clip(RoundedCornerShape(3.dp)).background(accent))
                Spacer(Modifier.width(5.dp))
                if (task.isCourseAssignment()) {
                    Icon(Icons.Default.Assignment, contentDescription = "课程作业", tint = JournalInk, modifier = Modifier.size(25.dp))
                } else {
                    Checkbox(
                        checked = task.done || stamping,
                        onCheckedChange = { if (!stamping) { if (task.done || reduceMotion) onToggle() else stamping = true } },
                        colors = CheckboxDefaults.colors(checkedColor = JournalInk, uncheckedColor = JournalInk),
                        modifier = Modifier.size(40.dp),
                    )
                }
                Spacer(Modifier.width(8.dp))
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text(task.title, color = if (task.done) JournalMuted else JournalInk, fontWeight = FontWeight.Bold, fontSize = 14.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text("${task.course.ifBlank { "个人事务" }} · 截止 ${task.due.replace('T', ' ').take(16)}", color = JournalMuted, fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    if (!task.done && task.source in setOf("chaoxing_notice", "course_notice"))
                        Text("提交状态待确认", color = Color(0xFF966942), fontSize = 10.sp)
                }
                if (task.done) Text("已完成", color = JournalInk, fontSize = 10.sp, fontWeight = FontWeight.Bold,
                    modifier = Modifier.border(1.dp, JournalInk.copy(alpha = .6f), RoundedCornerShape(4.dp)).padding(horizontal = 5.dp, vertical = 3.dp))
            }
            if (stamping && !reduceMotion) Text("已完成", color = JournalInk, fontSize = 16.sp, fontWeight = FontWeight.Black,
                modifier = Modifier.align(Alignment.BottomEnd).padding(end = 10.dp, bottom = 5.dp)
                    .graphicsLayer { scaleX = stampScale; scaleY = stampScale; alpha = stampAlpha; rotationZ = -12f }
                    .border(2.dp, JournalInk, RoundedCornerShape(6.dp)).padding(horizontal = 8.dp, vertical = 4.dp))
        }
    }
}

@Composable
private fun EmptyTasks(online: Boolean, filter: String, onRetry: () -> Unit) {
    JournalSheet(Modifier.fillMaxWidth()) {
        Column(Modifier.fillMaxWidth().padding(vertical = 28.dp, horizontal = 20.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(7.dp)) {
            Icon(if (online) Icons.Default.TaskAlt else Icons.Default.CloudOff, null, tint = JournalAmber, modifier = Modifier.size(30.dp))
            Text(if (online) "这页手账暂时空着" else "暂时无法获取任务", color = JournalInk, fontWeight = FontWeight.Bold)
            Text(if (online) if (filter == "已完成") "完成一件事后，印章会留在这里" else "给今天留一点空间，也可以添加一件小事" else "请检查网络后重试", color = JournalMuted, fontSize = 12.sp)
            if (!online) TextButton(onClick = onRetry) { Text("重新获取", color = JournalInk) }
        }
    }
}


package com.example.campusai.ui.screens.courses

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowForward
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Class
import androidx.compose.material.icons.filled.EventAvailable
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.TaskAlt
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Notifications
import com.example.campusai.ui.components.GlassButton as Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.Course
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.remote.CourseContentItemDto
import com.example.campusai.data.remote.CourseContentSummaryDto
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import com.example.campusai.ui.components.ModeBadge
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.screens.shell.floatingDockContentBottomPadding
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Success
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.launch

private val CourseBlue = Color(0xFF5B70ED)
private val CourseBlueLight = Color(0xFF7E95F5)
private val CourseOrange = Color(0xFFF29A49)
private val CourseGreen = Color(0xFF37B89B)
private val CoursePurple = Color(0xFF9369E8)

@Composable
fun CoursesScreen(repository: AppRepository) {
    val courses by repository.courses.collectAsStateWithLifecycle()
    val mockMode by repository.mockMode.collectAsStateWithLifecycle()
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()
    var selectedType by remember { mutableStateOf("全部") }
    var selectedDay by remember { mutableIntStateOf(3) }
    var selectedCourse by remember { mutableStateOf<Course?>(null) }

    // 进入页面时尝试从后端拉取最新课程
    androidx.compose.runtime.LaunchedEffect(Unit) { repository.refreshCourses() }
    val types = listOf("全部", "今日课程", "专业课", "公共课", "实验课")
    val visibleCourses = courses.filter { course ->
        when (selectedType) {
            "专业课" -> course.type.contains("专业")
            "公共课" -> course.type.contains("公共")
            "实验课" -> course.name.contains("实验") || course.location.contains("实验")
            "今日课程" -> course.code in setOf("CS2103", "CS2201", "EN1404")
            else -> true
        }
    }
    val floatingDockScrollPadding =
        floatingDockContentBottomPadding(
            WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding(),
        )

    LazyColumn(
        state = listState,
        modifier = Modifier.fillMaxSize().background(Background),
        contentPadding = PaddingValues(
            start = 14.dp,
            top = 12.dp,
            end = 14.dp,
            bottom = floatingDockScrollPadding,
        ),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item { CoursesHeader(mockMode, reduceMotion) }
        item {
            CourseHero(
                course = courses.firstOrNull(),
                count = courses.size,
                reduceMotion = reduceMotion,
                onOpenDetail = { courses.firstOrNull()?.let { selectedCourse = it } },
                onOpenWeek = { scope.launch { listState.animateScrollToItem(index = 3) } },
            )
        }
        item {
            WeekStrip(selectedDay = selectedDay, onDaySelected = { selectedDay = it })
        }
        item { CourseMetrics(courseCount = courses.size, reduceMotion = reduceMotion) }
        item {
            CourseFilters(
                types = types,
                selectedType = selectedType,
                onTypeSelected = { selectedType = it },
                onMoreClick = { selectedType = "全部" },
            )
        }
        item {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 2.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(1.dp)) {
                    Text("本学期课程", fontSize = 16.sp, fontWeight = FontWeight.Bold)
                    Text("按课程卡片查看上课地点与资料", color = Muted, fontSize = 10.sp)
                }
                Text("${visibleCourses.size} 门", color = Muted, fontSize = 11.sp)
            }
        }
        if (visibleCourses.isEmpty()) {
            item { EmptyCourses() }
        } else {
            itemsIndexed(
                items = visibleCourses,
                // Course codes are optional in the API and are not guaranteed to be
                // unique. Include the position so Compose never receives duplicate
                // keys (duplicate/blank codes previously crashed this screen).
                key = { index, course -> course.listKey(index, "course") },
            ) { _, course ->
                CourseCard(
                    course = course,
                    reduceMotion = reduceMotion,
                    index = courses.indexOf(course),
                    onClick = { selectedCourse = course },
                )
            }
        }
        item { TodaySchedule(courses = courses, onCourseClick = { selectedCourse = it }) }
    }

    selectedCourse?.let { course ->
        CourseDetailSheet(course = course, repository = repository, onDismiss = { selectedCourse = null })
    }
}

@Composable
private fun CoursesHeader(mockMode: Boolean, reduceMotion: Boolean) {
    Row(
        modifier = Modifier.fillMaxWidth().enterAnimation(enabled = !reduceMotion),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.Top,
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(1.dp)) {
            Text("课程", fontSize = 26.sp, fontWeight = FontWeight.ExtraBold, color = TextPrimary)
            Text("把这周的学习节奏握在手里", color = Muted, fontSize = 12.sp)
        }
        ModeBadge(mockMode)
    }
}

@Composable
private fun CourseHero(
    course: Course?,
    count: Int,
    reduceMotion: Boolean,
    onOpenDetail: () -> Unit,
    onOpenWeek: () -> Unit,
) {
    val heroShape = RoundedCornerShape(18.dp)
    Row(
        modifier = Modifier.fillMaxWidth().height(164.dp).clip(heroShape)
            .background(Brush.linearGradient(listOf(CourseBlue, CourseBlueLight)))
            .enterAnimation(delayMs = 55, enabled = !reduceMotion)
            .padding(start = 14.dp, top = 13.dp, end = 10.dp, bottom = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(
            modifier = Modifier.fillMaxHeight().weight(1f),
            verticalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(6.dp).clip(CircleShape).background(Color(0xFFFFC35C)))
                    Spacer(Modifier.width(5.dp))
                    Text("下一节课 · 10:10", color = Color.White.copy(alpha = .82f), fontSize = 10.sp)
                }
                Text(course?.name ?: "今天没有课程", color = Color.White, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.LocationOn, null, tint = Color.White.copy(alpha = .78f), modifier = Modifier.size(13.dp))
                    Spacer(Modifier.width(3.dp))
                    Text(
                        text = course?.let { "${it.location} · ${it.teacher}" } ?: "去添加你的课程安排",
                        color = Color.White.copy(alpha = .78f),
                        fontSize = 10.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                HeroAction(Icons.Default.CalendarMonth, "课程表", onOpenWeek)
                HeroAction(Icons.Default.Info, "课程详情", onOpenDetail)
                HeroAction(Icons.Default.TaskAlt, "待办作业", onOpenDetail)
            }
        }
        Column(
            modifier = Modifier.fillMaxHeight().width(70.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.SpaceBetween,
        ) {
            Box(
                modifier = Modifier.size(43.dp).clip(RoundedCornerShape(14.dp))
                    .background(Color.White.copy(alpha = .18f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(Icons.Default.Class, null, tint = Color.White, modifier = Modifier.size(24.dp))
            }
            Row(
                modifier = Modifier.clip(RoundedCornerShape(20.dp)).background(Color.White.copy(alpha = .9f))
                    .campusClickable(onClick = onOpenDetail).padding(horizontal = 10.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("去查看", color = CourseBlue, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                Icon(Icons.Default.ArrowForward, null, tint = CourseBlue, modifier = Modifier.size(12.dp))
            }
        }
    }
}

@Composable
private fun HeroAction(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String, onClick: () -> Unit) {
    Row(
        modifier = Modifier.clip(RoundedCornerShape(7.dp)).campusClickable(onClick = onClick)
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Icon(icon, null, tint = Color.White.copy(alpha = .88f), modifier = Modifier.size(13.dp))
        Text(label, color = Color.White.copy(alpha = .9f), fontSize = 9.sp)
    }
}

@Composable
private fun WeekStrip(selectedDay: Int, onDaySelected: (Int) -> Unit) {
    val days = listOf("一", "二", "三", "四", "五", "六", "日")
    val dates = listOf("12", "13", "14", "15", "16", "17", "18")
    Row(
        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(Surface)
            .border(1.dp, Line.copy(alpha = .75f), RoundedCornerShape(14.dp)).padding(vertical = 8.dp),
        horizontalArrangement = Arrangement.SpaceEvenly,
    ) {
        days.forEachIndexed { index, day ->
            val selected = index == selectedDay
            val dayColor by animateColorAsState(
                targetValue = if (selected) Primary else Muted,
                animationSpec = tween(180),
                label = "week-day-color",
            )
            Column(
                modifier = Modifier.width(38.dp).clip(RoundedCornerShape(12.dp)).campusClickable {
                    onDaySelected(index)
                }.padding(vertical = 1.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(3.dp),
            ) {
                Text(day, color = if (selected) Primary else Muted, fontSize = 9.sp)
                Box(
                    modifier = Modifier.size(25.dp).clip(CircleShape)
                        .background(if (selected) Primary else Color.Transparent),
                    contentAlignment = Alignment.Center,
                ) { Text(dates[index], color = if (selected) Color.White else dayColor, fontSize = 10.sp, fontWeight = FontWeight.Bold) }
                Box(Modifier.size(4.dp).clip(CircleShape).background(if (index == 2 || index == 4) CourseOrange else Line))
            }
        }
    }
}

@Composable
private fun CourseMetrics(courseCount: Int, reduceMotion: Boolean) {
    val metrics = listOf(
        Triple(Icons.Default.MenuBook, "$courseCount", "门课程"),
        Triple(Icons.Default.Schedule, "18", "本周学时"),
        Triple(Icons.Default.TaskAlt, "26.5", "已修学分"),
        Triple(Icons.Default.EventAvailable, "96%", "出勤率"),
    )
    Row(
        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(Surface)
            .border(1.dp, Line.copy(alpha = .75f), RoundedCornerShape(14.dp))
            .enterAnimation(delayMs = 110, enabled = !reduceMotion).padding(vertical = 10.dp),
        horizontalArrangement = Arrangement.SpaceEvenly,
    ) {
        metrics.forEachIndexed { index, metric ->
            if (index > 0) Spacer(Modifier.width(1.dp).height(36.dp).background(Line))
            Column(
                modifier = Modifier.weight(1f),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    Icon(metric.first, null, tint = listOf(CourseBlue, CourseGreen, CourseOrange, CoursePurple)[index], modifier = Modifier.size(15.dp))
                    Text(metric.second, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                }
                Text(metric.third, color = Muted, fontSize = 9.sp)
            }
        }
    }
}

@Composable
private fun CourseFilters(
    types: List<String>,
    selectedType: String,
    onTypeSelected: (String) -> Unit,
    onMoreClick: () -> Unit,
) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        LazyRow(
            modifier = Modifier.weight(1f),
            horizontalArrangement = Arrangement.spacedBy(7.dp),
            contentPadding = PaddingValues(end = 5.dp),
        ) {
            itemsIndexed(types) { _, type ->
                val selected = selectedType == type
                Box(
                    modifier = Modifier.clip(RoundedCornerShape(20.dp))
                        .background(if (selected) Primary else Surface)
                        .border(1.dp, if (selected) Primary else Line, RoundedCornerShape(20.dp))
                        .campusClickable { onTypeSelected(type) }
                        .padding(horizontal = 11.dp, vertical = 7.dp),
                ) { Text(type, color = if (selected) Color.White else Muted, fontSize = 10.sp, fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal) }
            }
        }
        Box(
            modifier = Modifier.size(30.dp).clip(CircleShape).background(Surface)
                .border(1.dp, Line, CircleShape).campusClickable(onClick = onMoreClick),
            contentAlignment = Alignment.Center,
        ) { Icon(Icons.Default.MoreHoriz, "重置筛选", tint = Muted, modifier = Modifier.size(17.dp)) }
    }
}

@Composable
private fun CourseCard(course: Course, reduceMotion: Boolean, index: Int, onClick: () -> Unit) {
    val accent = when {
        course.type.contains("公共") -> CourseOrange
        course.type.contains("学科") -> CourseGreen
        course.type.contains("核心") -> CoursePurple
        else -> CourseBlue
    }
    val progress = when (index % 3) {
        0 -> .96f
        1 -> .92f
        else -> .94f
    }
    Row(
        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(Surface)
            .border(1.dp, Line.copy(alpha = .8f), RoundedCornerShape(14.dp))
            .campusClickable(onClick = onClick).padding(horizontal = 11.dp, vertical = 10.dp)
            .enterAnimation(delayMs = 140 + index * 45, enabled = !reduceMotion),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(9.dp),
    ) {
        Box(
            modifier = Modifier.size(40.dp).clip(RoundedCornerShape(10.dp)).background(accent.copy(alpha = .12f)),
            contentAlignment = Alignment.Center,
        ) { Text(course.code.take(2), color = accent, fontWeight = FontWeight.ExtraBold, fontSize = 13.sp) }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                Text(course.name, fontWeight = FontWeight.Bold, fontSize = 13.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(
                    course.type,
                    color = accent,
                    fontSize = 8.sp,
                    maxLines = 1,
                    modifier = Modifier.clip(RoundedCornerShape(5.dp)).background(accent.copy(alpha = .1f)).padding(horizontal = 5.dp, vertical = 2.dp),
                )
            }
            Text("${course.teacher} · ${course.location}", color = Muted, fontSize = 10.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("周${if (index % 2 == 0) "一" else "三"} 10:10", color = Muted, fontSize = 9.sp)
                Text(course.code, color = Muted.copy(alpha = .82f), fontSize = 9.sp)
            }
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(1.dp)) {
            Box(contentAlignment = Alignment.Center) {
                CircularProgressIndicator(progress = { 1f }, color = Line, strokeWidth = 2.dp, modifier = Modifier.size(28.dp))
                CircularProgressIndicator(progress = { progress }, color = accent, strokeWidth = 2.dp, modifier = Modifier.size(28.dp))
                Text("${(progress * 100).toInt()}%", fontSize = 7.sp, color = Muted)
            }
            Text("出勤率", color = Muted, fontSize = 7.sp)
        }
        Icon(Icons.Default.ChevronRight, "查看课程详情", tint = Muted, modifier = Modifier.size(17.dp))
    }
}

@Composable
private fun TodaySchedule(courses: List<Course>, onCourseClick: (Course) -> Unit) {
    if (courses.isEmpty()) return
    Column(verticalArrangement = Arrangement.spacedBy(7.dp)) {
        Row(Modifier.fillMaxWidth(), Arrangement.SpaceBetween, Alignment.CenterVertically) {
            Text("今日安排", fontSize = 14.sp, fontWeight = FontWeight.Bold)
            Text("还有 ${courses.size.coerceAtMost(3)} 节", color = Muted, fontSize = 10.sp)
        }
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            itemsIndexed(
                items = courses.take(3),
                key = { index, course -> course.listKey(index, "today") },
            ) { _, course ->
                Row(
                    modifier = Modifier.width(178.dp).clip(RoundedCornerShape(12.dp)).background(Surface)
                        .border(1.dp, Line.copy(alpha = .8f), RoundedCornerShape(12.dp))
                        .campusClickable { onCourseClick(course) }.padding(10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Box(Modifier.size(28.dp).clip(RoundedCornerShape(8.dp)).background(PrimarySoft), contentAlignment = Alignment.Center) {
                        Icon(Icons.Default.MenuBook, null, tint = Primary, modifier = Modifier.size(15.dp))
                    }
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text("10:10", color = CourseOrange, fontSize = 9.sp, fontWeight = FontWeight.Bold)
                        Text(course.name, fontSize = 10.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text(course.location, color = Muted, fontSize = 8.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                }
            }
        }
    }
}

private fun Course.listKey(index: Int, section: String): String {
    val identity = id.ifBlank {
        code.ifBlank { "$name|$teacher|$location" }
    }
    return "$section|$identity|$index"
}

@Composable
private fun EmptyCourses() {
    Column(
        modifier = Modifier.fillMaxWidth().padding(vertical = 44.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Icon(Icons.Default.EventAvailable, null, tint = Primary, modifier = Modifier.size(34.dp))
        Text("这个分类下暂时没有课程", fontWeight = FontWeight.SemiBold)
        Text("换个筛选条件看看吧", color = Muted, fontSize = 12.sp)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CourseDetailSheet(course: Course, repository: AppRepository, onDismiss: () -> Unit) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var summary by remember(course.id) { mutableStateOf<CourseContentSummaryDto?>(null) }
    var content by remember(course.id) { mutableStateOf<List<CourseContentItemDto>>(emptyList()) }
    var loading by remember(course.id) { mutableStateOf(true) }
    var syncing by remember(course.id) { mutableStateOf(false) }
    var error by remember(course.id) { mutableStateOf<String?>(null) }
    var filter by remember(course.id) { mutableStateOf("全部") }
    val filters = listOf("全部", "章节", "资料", "作业", "通知", "考试", "讨论")
    val kinds = mapOf(
        "章节" to setOf("chapter"),
        "资料" to setOf("document", "video", "audio", "image", "material", "link"),
        "作业" to setOf("assignment"), "通知" to setOf("notice"),
        "考试" to setOf("exam"), "讨论" to setOf("discussion"),
    )
    val visible = kinds[filter]?.let { accepted -> content.filter { it.kind in accepted } } ?: content

    androidx.compose.runtime.LaunchedEffect(course.id) {
        try {
            val loaded = repository.loadCourseContent(course.id)
            summary = loaded.first
            content = loaded.second
        } catch (_: Exception) { error = "课程内容加载失败，已保留现有信息" }
        finally { loading = false }
    }
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor = Surface,
        shape = RoundedCornerShape(topStart = 26.dp, topEnd = 26.dp),
    ) {
        LazyColumn(
            modifier = Modifier.fillMaxWidth().fillMaxHeight(0.86f),
            contentPadding = PaddingValues(start = 22.dp, end = 22.dp, bottom = 34.dp),
            verticalArrangement = Arrangement.spacedBy(15.dp),
        ) {
            item { Row(Modifier.fillMaxWidth(), Arrangement.SpaceBetween, Alignment.Top) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("课程详情", color = Primary, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                    Text(course.name, fontSize = 22.sp, fontWeight = FontWeight.ExtraBold)
                    Text("${course.code} · ${course.type}", color = Muted, fontSize = 12.sp)
                }
                Box(Modifier.size(42.dp).clip(RoundedCornerShape(12.dp)).background(PrimarySoft), contentAlignment = Alignment.Center) {
                    Icon(Icons.Default.MenuBook, null, tint = Primary)
                }
            } }
            item { DetailRow(Icons.Default.Person, "授课教师", summary?.teacher_name ?: course.teacher) }
            summary?.school_name?.let { school -> item { DetailRow(Icons.Default.LocationOn, "开课学校", school) } }
            summary?.class_name?.let { clazz -> item { DetailRow(Icons.Default.Class, "教学班", clazz) } }
            item {
                Button(
                onClick = {
                    syncing = true
                    error = null
                    scope.launch {
                        try {
                            val loaded = repository.syncCourseContent(course.id)
                            summary = loaded.first
                            content = loaded.second
                        } catch (_: Exception) { error = "同步失败，旧数据没有被清空" }
                        finally { syncing = false }
                    }
                },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Primary),
                enabled = !syncing,
            ) { Icon(Icons.Default.Refresh, null); Spacer(Modifier.width(8.dp)); Text(if (syncing) "同步中…" else "同步学习通课程内容", fontWeight = FontWeight.Bold) }
            }
            if (loading) item { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) { CircularProgressIndicator(Modifier.size(28.dp)) } }
            error?.let { message -> item { Text(message, color = Color(0xFFC64A46), fontSize = 12.sp) } }
            if (!loading) {
                item {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        itemsIndexed(filters) { _, item ->
                            Button(
                                onClick = { filter = item },
                                shape = RoundedCornerShape(12.dp),
                                contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = if (filter == item) Primary else PrimarySoft, contentColor = if (filter == item) Color.White else Primary),
                            ) { Text(item, fontSize = 11.sp) }
                        }
                    }
                }
                if (visible.isEmpty()) item {
                    val section = summary?.sections?.firstOrNull { it.section == mapOf("章节" to "chapters", "资料" to "materials", "作业" to "assignments", "通知" to "notices", "考试" to "exams", "讨论" to "discussions")[filter] }
                    val text = when (section?.status) {
                        "failed" -> "本次同步失败，正在保留上次数据"
                        "unavailable" -> "学习通当前未开放此栏目"
                        "complete" -> "学习通返回的列表为空"
                        else -> "尚未同步此栏目"
                    }
                    Text(text, color = Muted, fontSize = 12.sp, modifier = Modifier.padding(vertical = 18.dp))
                }
                itemsIndexed(visible, key = { _, item -> item.id }) { _, item ->
                    val icon = when (item.kind) { "notice" -> Icons.Default.Notifications; "assignment" -> Icons.Default.TaskAlt; else -> Icons.Default.FolderOpen }
                    Row(
                        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(PrimarySoft)
                            .campusClickable {
                                scope.launch {
                                    if (item.can_download) {
                                        val file = repository.downloadCourseResource(course.id, item)
                                        Toast.makeText(context, if (file != null) "已缓存到应用临时目录" else "资料下载失败", Toast.LENGTH_SHORT).show()
                                    } else {
                                        val url = repository.getCourseResourceUrl(course.id, item.id)
                                        if (!url.isNullOrBlank()) context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                                    }
                                }
                            }.padding(13.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Icon(icon, null, tint = Primary, modifier = Modifier.size(20.dp))
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(item.title, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis)
                            Text(listOf(item.kind, item.status, if (item.cached) "已缓存" else "").filter { it.isNotBlank() }.joinToString(" · "), color = Muted, fontSize = 10.sp)
                        }
                        Icon(Icons.Default.ChevronRight, null, tint = Muted)
                    }
                }
            }
        }
    }
}

@Composable
private fun DetailRow(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String, value: String) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Box(Modifier.size(38.dp).clip(RoundedCornerShape(11.dp)).background(PrimarySoft), contentAlignment = Alignment.Center) {
            Icon(icon, null, tint = Primary, modifier = Modifier.size(19.dp))
        }
        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(label, color = Muted, fontSize = 10.sp)
            Text(value, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
        }
    }
}

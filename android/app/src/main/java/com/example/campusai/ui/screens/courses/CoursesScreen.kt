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
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Class
import androidx.compose.material.icons.filled.EventAvailable
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.List
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
import androidx.compose.material3.AlertDialog
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
import androidx.core.content.FileProvider
import java.net.URLConnection
import com.example.campusai.ui.components.ModeBadge
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.screens.shell.floatingDockContentBottomPadding
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.launch

private val CourseBlue = Color(0xFF5B70ED)
private val CourseBlueLight = Color(0xFF7E95F5)
private val CourseOrange = Color(0xFFF29A49)
private val CourseGreen = Color(0xFF37B89B)
private val CoursePurple = Color(0xFF9369E8)
private val DetailForest = Color(0xFF22513F)
private val DetailGold = Color(0xFFAF925B)

@Composable
fun CoursesScreen(
    repository: AppRepository,
    onOpenSchedule: () -> Unit = {},
    onOpenClassroom: (String) -> Unit,
    initialCourseId: String? = null,
    initialTab: String? = null,
) {
    val courses by repository.courses.collectAsStateWithLifecycle()
    val mockMode by repository.mockMode.collectAsStateWithLifecycle()
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    val listState = rememberLazyListState()
    var selectedType by remember { mutableStateOf("全部") }
    var selectedDay by remember { mutableIntStateOf(3) }
    var selectedCourse by remember { mutableStateOf<Course?>(null) }

    // 进入页面时尝试从后端拉取最新课程
    androidx.compose.runtime.LaunchedEffect(Unit) { repository.refreshCourses() }
    androidx.compose.runtime.LaunchedEffect(courses, initialCourseId) {
        if (selectedCourse == null && !initialCourseId.isNullOrBlank()) {
            selectedCourse = courses.firstOrNull { it.id == initialCourseId }
        }
    }
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
            top = 0.dp,
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
                onOpenSchedule = onOpenSchedule,
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
        CourseDetailSheet(
            course = course,
            repository = repository,
            onDismiss = { selectedCourse = null },
            onOpenClassroom = onOpenClassroom,
        )
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
    onOpenSchedule: () -> Unit,
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
                HeroAction(Icons.Default.CalendarMonth, "课程表", onOpenSchedule)
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
internal fun CourseDetailSheet(
    course: Course,
    repository: AppRepository,
    onDismiss: () -> Unit,
    onOpenClassroom: (String) -> Unit,
    onStartFocus: (String) -> Unit = {},
) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var summary by remember(course.id) { mutableStateOf<CourseContentSummaryDto?>(null) }
    var content by remember(course.id) { mutableStateOf<List<CourseContentItemDto>>(emptyList()) }
    var loading by remember(course.id) { mutableStateOf(true) }
    var syncing by remember(course.id) { mutableStateOf(false) }
    var error by remember(course.id) { mutableStateOf<String?>(null) }
    var selectedNotice by remember(course.id) { mutableStateOf<CourseContentItemDto?>(null) }
    var downloadFailure by remember(course.id) { mutableStateOf<Pair<CourseContentItemDto, String>?>(null) }
    var filter by remember(course.id) { mutableStateOf("全部") }
    val filters = listOf("全部", "章节", "资料", "作业", "通知", "考试", "讨论")
    val kinds = mapOf(
        "章节" to setOf("chapter"),
        "资料" to setOf("document", "video", "audio", "image", "material", "link"),
        "作业" to setOf("assignment"), "通知" to setOf("notice"),
        "考试" to setOf("exam"), "讨论" to setOf("discussion"),
    )
    val populatedFilters = filters.drop(1).filter { name ->
        content.any { it.kind in kinds[name].orEmpty() }
    }
    val filterOptions = if (populatedFilters.size > 1) listOf("全部") + populatedFilters else populatedFilters.ifEmpty { listOf("全部") }
    val activeFilter = filter.takeIf { it in filterOptions } ?: filterOptions.first()
    val visible = kinds[activeFilter]?.let { accepted -> content.filter { it.kind in accepted } } ?: content

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
        containerColor = Color(0xFFF5F2E8),
        shape = RoundedCornerShape(topStart = 26.dp, topEnd = 26.dp),
    ) {
        LazyColumn(
            modifier = Modifier.fillMaxWidth().fillMaxHeight(0.86f)
                .background(androidx.compose.ui.graphics.Brush.verticalGradient(listOf(Color(0xFFF8F5EA), Color(0xFFE8EEE4)))),
            contentPadding = PaddingValues(start = 22.dp, end = 22.dp, bottom = 34.dp),
            verticalArrangement = Arrangement.spacedBy(15.dp),
        ) {
            item { Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp))
                .background(androidx.compose.ui.graphics.Brush.linearGradient(listOf(Color(0xFF15362F), Color(0xFF376249), Color(0xFF806C46))))
                .padding(18.dp), Arrangement.SpaceBetween, Alignment.Top) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(course.name, color = Color.White, fontSize = 21.sp, fontWeight = FontWeight.ExtraBold)
                    Text(listOf(summary?.teacher_name ?: course.teacher, summary?.class_name ?: course.code)
                        .filter(String::isNotBlank).joinToString(" · "),
                        color = Color.White.copy(alpha = .82f), fontSize = 12.sp)
                }
            } }
            item {
                Button(
                    onClick = { onOpenClassroom(course.id) },
                    modifier = Modifier.fillMaxWidth().height(50.dp),
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = DetailForest, contentColor = Color.White),
                ) {
                    Icon(Icons.Default.Class, null)
                    Spacer(Modifier.width(8.dp))
                    Text("进入互动课堂", fontWeight = FontWeight.Bold)
                    Spacer(Modifier.weight(1f))
                    Icon(Icons.Default.ArrowForward, null)
                }
            }
            item {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text("从课程资料生成讲解与练习", color = Muted, fontSize = 12.sp)
                    Text("去自习室 ›", color = DetailForest, fontSize = 12.sp, fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.campusClickable { onStartFocus("学习《${course.name}》") }.padding(8.dp))
                }
            }
            item {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text("课程内容", color = DetailForest, fontSize = 17.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                    Text("${content.size} 项", color = Muted, fontSize = 12.sp)
                    Box(Modifier.size(42.dp).clip(CircleShape).campusClickable(enabled = !syncing) {
                        syncing = true
                        error = null
                        scope.launch {
                            try {
                                val loaded = repository.syncCourseContent(course.id)
                                summary = loaded.first
                                content = loaded.second
                            } catch (_: Exception) { error = "更新失败，已保留原有内容" }
                            finally { syncing = false }
                        }
                    }, contentAlignment = Alignment.Center) {
                        if (syncing) CircularProgressIndicator(Modifier.size(19.dp), strokeWidth = 2.dp)
                        else Icon(Icons.Default.Refresh, contentDescription = "更新课程内容", tint = DetailForest)
                    }
                }
            }
            if (loading) item { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) { CircularProgressIndicator(Modifier.size(28.dp)) } }
            error?.let { message -> item { Text(message, color = Color(0xFFC64A46), fontSize = 12.sp) } }
            summary?.sections?.let { sections ->
                val blocked = sections.filter { it.status == "failed" || it.status == "partial" }
                if (blocked.isNotEmpty()) item {
                    Text(if (blocked.any { it.error_code in listOf("reauth_required", "verification_required") })
                        "部分栏目需要重新登录学习通或完成验证" else "部分栏目暂未更新成功，已保留现有内容",
                        color = Muted, fontSize = 12.sp)
                }
            }
            if (!loading) {
                if (content.isNotEmpty()) item {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        itemsIndexed(filterOptions) { _, item ->
                            val selected = activeFilter == item
                            val count = if (item == "全部") content.size else content.count { it.kind in kinds[item].orEmpty() }
                            Box(
                                Modifier.clip(CircleShape)
                                    .background(if (selected) DetailForest else Color.White.copy(alpha = .55f))
                                    .border(1.dp, if (selected) DetailGold else DetailForest.copy(alpha = .18f), CircleShape)
                                    .campusClickable { filter = item }
                                    .padding(horizontal = 17.dp, vertical = 9.dp),
                                contentAlignment = Alignment.Center,
                            ) { Text("$item $count", color = if (selected) Color.White else DetailForest, fontSize = 12.sp, fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium) }
                        }
                    }
                }
                if (visible.isEmpty()) item {
                    val section = summary?.sections?.firstOrNull { it.section == mapOf("章节" to "chapters", "资料" to "materials", "作业" to "assignments", "通知" to "notices", "考试" to "exams", "讨论" to "discussions")[activeFilter] }
                    val text = when {
                        section?.error_code in listOf("reauth_required", "verification_required") -> "学习通要求重新登录或验证，请完成后重试"
                        section?.status == "failed" -> "本次同步失败，正在保留上次数据"
                        section?.status == "partial" -> "已读取部分内容，其他来源暂时受限"
                        section?.status == "unavailable" -> "学习通当前未开放此栏目"
                        section?.status == "complete" -> if (activeFilter == "资料") "该课程的学习通资料栏暂无文件" else "学习通返回的列表为空"
                        else -> "尚未同步此栏目"
                    }
                    Text(text, color = Muted, fontSize = 12.sp, modifier = Modifier.padding(vertical = 18.dp))
                }
                itemsIndexed(visible, key = { _, item -> item.id }) { _, item ->
                    val icon = when (item.kind) { "notice" -> Icons.Default.Notifications; "assignment" -> Icons.Default.TaskAlt; "document" -> Icons.Default.Description; else -> Icons.Default.FolderOpen }
                    Row(
                        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp))
                            .background(Brush.horizontalGradient(listOf(Color(0xFFFAF8EF), Color(0xFFE8EFE5))))
                            .border(1.dp, DetailGold.copy(alpha = .25f), RoundedCornerShape(18.dp))
                            .campusClickable {
                                if (item.kind == "notice") {
                                    selectedNotice = item
                                    return@campusClickable
                                }
                                scope.launch {
                                    try {
                                        if (item.can_download) {
                                            val downloaded = repository.downloadCourseResource(course.id, item)
                                            val file = downloaded.file
                                            if (file == null) {
                                                downloadFailure = item to (downloaded.errorCode ?: "unknown")
                                            } else {
                                                val uri = FileProvider.getUriForFile(context, "${context.packageName}.coursefiles", file)
                                                val mimeType = URLConnection.guessContentTypeFromName(file.name) ?: "*/*"
                                                val intent = Intent(Intent.ACTION_VIEW).apply {
                                                    setDataAndType(uri, mimeType)
                                                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                                }
                                                runCatching { context.startActivity(intent) }
                                                    .onFailure { Toast.makeText(context, "资料已下载，但手机上没有可打开它的应用", Toast.LENGTH_SHORT).show() }
                                            }
                                        } else {
                                            val url = repository.getCourseResourceUrl(course.id, item.id)
                                            if (!url.isNullOrBlank() && Uri.parse(url).scheme == "https") {
                                                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                                            } else {
                                                Toast.makeText(context, "这份资料暂时无法打开", Toast.LENGTH_SHORT).show()
                                            }
                                        }
                                    } catch (_: Exception) {
                                        downloadFailure = item to "network_error"
                                    }
                                }
                            }.padding(15.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Box(Modifier.size(38.dp).clip(RoundedCornerShape(11.dp)).background(DetailForest.copy(alpha = .1f)), contentAlignment = Alignment.Center) {
                            Icon(icon, null, tint = DetailForest, modifier = Modifier.size(19.dp))
                        }
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(item.title, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis)
                            Text(
                                if (item.kind == "notice") "教师通知${item.author_name?.let { " · $it" }.orEmpty()}"
                                else listOf(when (item.kind) { "document" -> "文档"; "video" -> "视频"; "audio" -> "音频"; "image" -> "图片"; "chapter" -> "章节"; else -> "课程资料" }, if (item.cached) "已缓存" else "来自学习通").joinToString(" · "),
                                color = Muted, fontSize = 10.sp,
                            )
                        }
                        Icon(Icons.Default.ChevronRight, null, tint = DetailForest)
                    }
                }
            }
        }
    }
    selectedNotice?.let { notice ->
        AlertDialog(
            onDismissRequest = { selectedNotice = null },
            title = { Text(notice.title, fontWeight = FontWeight.Bold) },
            text = { Text(notice.description?.takeIf(String::isNotBlank) ?: "这条通知暂时没有可显示的正文。") },
            confirmButton = {
                Button(onClick = { selectedNotice = null }) { Text("关闭") }
            },
            containerColor = Color(0xFFF5F2E8),
        )
    }
    downloadFailure?.let { (item, code) ->
        AlertDialog(
            onDismissRequest = { downloadFailure = null },
            title = { Text("暂时无法下载") },
            text = {
                Text(when (code) {
                    "verification_required" -> "学习通要求安全验证。可以前往学习通打开此文件，完成验证后下载。"
                    "chaoxing_session_expired", "chaoxing_credentials_not_found", "http_401" -> "学习通登录已失效，请重新连接账号后重试。"
                    "resource_too_large" -> "文件超过应用当前可下载的大小限制，可前往学习通查看。"
                    "resource_not_found" -> "学习通中的这份文件可能已被移除。"
                    else -> "学习通暂未提供可用的文件下载。可以尝试在学习通中打开。"
                })
            },
            confirmButton = {
                Button(onClick = {
                    downloadFailure = null
                    scope.launch {
                        val url = runCatching { repository.getCourseResourceUrl(course.id, item.id) }.getOrNull()
                        if (!url.isNullOrBlank() && Uri.parse(url).scheme == "https") {
                            runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
                                .onFailure { Toast.makeText(context, "无法打开学习通页面", Toast.LENGTH_SHORT).show() }
                        } else {
                            Toast.makeText(context, "学习通没有提供可打开的文件地址", Toast.LENGTH_SHORT).show()
                        }
                    }
                }) { Text("去学习通打开") }
            },
            dismissButton = { Button(onClick = { downloadFailure = null }) { Text("返回") } },
            containerColor = Color(0xFFF5F2E8),
        )
    }
}

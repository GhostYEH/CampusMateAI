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
import androidx.compose.foundation.lazy.items
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
import androidx.compose.material3.Button
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
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Alignment
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
import com.example.campusai.ui.components.ModeBadge
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
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
    val courses by repository.courses.collectAsState()
    val mockMode by repository.mockMode.collectAsState()
    val reduceMotion by repository.reduceMotion.collectAsState()
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()
    var selectedType by remember { mutableStateOf("全部") }
    var selectedDay by remember { mutableIntStateOf(3) }
    var selectedCourse by remember { mutableStateOf<Course?>(null) }
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
        WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + 92.dp

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
            items(visibleCourses, key = { it.code }) { course ->
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
        CourseDetailSheet(course = course, onDismiss = { selectedCourse = null })
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
            items(types) { type ->
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
            items(courses.take(3), key = { "today-${it.code}" }) { course ->
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
private fun CourseDetailSheet(course: Course, onDismiss: () -> Unit) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor = Surface,
        shape = RoundedCornerShape(topStart = 26.dp, topEnd = 26.dp),
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(start = 22.dp, end = 22.dp, bottom = 34.dp),
            verticalArrangement = Arrangement.spacedBy(15.dp),
        ) {
            Row(Modifier.fillMaxWidth(), Arrangement.SpaceBetween, Alignment.Top) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("课程详情", color = Primary, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                    Text(course.name, fontSize = 22.sp, fontWeight = FontWeight.ExtraBold)
                    Text("${course.code} · ${course.type}", color = Muted, fontSize = 12.sp)
                }
                Box(Modifier.size(42.dp).clip(RoundedCornerShape(12.dp)).background(PrimarySoft), contentAlignment = Alignment.Center) {
                    Icon(Icons.Default.MenuBook, null, tint = Primary)
                }
            }
            DetailRow(Icons.Default.Person, "授课教师", course.teacher)
            DetailRow(Icons.Default.LocationOn, "上课地点", course.location)
            DetailRow(Icons.Default.Schedule, "本周安排", "周一、周三 10:10–11:45")
            DetailRow(Icons.Default.FolderOpen, "课程资料", "3 份资料待查看")
            Button(
                onClick = onDismiss,
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Primary),
            ) { Text("知道了", fontWeight = FontWeight.Bold) }
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

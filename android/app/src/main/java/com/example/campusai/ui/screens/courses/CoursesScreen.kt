package com.example.campusai.ui.screens.courses

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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.Course
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.ModeBadge
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.theme.*

private val CourseBlue = Color(0xFF5368E8)
private val CourseBlueDeep = Color(0xFF3449C7)
private val CourseOrange = Color(0xFFFFA43A)

@Composable
fun CoursesScreen(repository: AppRepository) {
    val courses by repository.courses.collectAsState()
    val mockMode by repository.mockMode.collectAsState()
    val reduceMotion by repository.reduceMotion.collectAsState()
    var selectedType by remember { mutableStateOf("全部") }
    var selectedCourse by remember { mutableStateOf<Course?>(null) }
    val types = listOf("全部", "今日课程", "专业课", "公共课")
    val visibleCourses = courses.filter { course ->
        when (selectedType) {
            "专业课" -> course.type.contains("专业")
            "公共课" -> course.type.contains("公共")
            "今日课程" -> course.code in setOf("CS2103", "CS2201", "EN1404")
            else -> true
        }
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize().background(Background),
        contentPadding = PaddingValues(16.dp, 12.dp, 16.dp, 28.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item { PageHeader("课程", "把这周的学习节奏握在手里", mockMode) }
        item { CourseHero(courses.size, reduceMotion) }
        item {
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(types) { type ->
                    FilterChip(
                        selected = selectedType == type,
                        onClick = { selectedType = type },
                        label = { Text(type) },
                        leadingIcon = if (selectedType == type) {
                            { Icon(Icons.Default.Check, null, Modifier.size(16.dp)) }
                        } else null,
                        shape = RoundedCornerShape(12.dp),
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = PrimarySoft,
                            selectedLabelColor = Primary,
                        ),
                        border = FilterChipDefaults.filterChipBorder(
                            enabled = true,
                            selected = selectedType == type,
                            borderColor = Line,
                            selectedBorderColor = Primary.copy(alpha = .24f),
                        ),
                    )
                }
            }
        }
        item {
            Row(Modifier.fillMaxWidth(), Arrangement.SpaceBetween, Alignment.CenterVertically) {
                Text("本学期课程", fontSize = 18.sp, fontWeight = FontWeight.Bold)
                Text("${visibleCourses.size} 门", color = Muted, fontSize = 12.sp)
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
    }

    selectedCourse?.let { course ->
        CourseDetailSheet(course = course, onDismiss = { selectedCourse = null })
    }
}

@Composable
private fun PageHeader(title: String, subtitle: String, mockMode: Boolean) {
    Row(Modifier.fillMaxWidth(), Arrangement.SpaceBetween, Alignment.CenterVertically) {
        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(title, fontSize = 26.sp, fontWeight = FontWeight.ExtraBold, color = TextPrimary)
            Text(subtitle, color = Muted, fontSize = 13.sp)
        }
        ModeBadge(mockMode)
    }
}

@Composable
private fun CourseHero(count: Int, reduceMotion: Boolean) {
    Box(
        Modifier.fillMaxWidth().height(154.dp).clip(RoundedCornerShape(26.dp))
            .background(Brush.linearGradient(listOf(CourseBlue, CourseBlueDeep)))
            .enterAnimation(enabled = !reduceMotion),
    ) {
        Box(
            Modifier.size(150.dp).offset(x = 250.dp, y = (-48).dp).clip(CircleShape)
                .background(Color.White.copy(alpha = .08f)),
        )
        Column(
            Modifier.fillMaxSize().padding(20.dp),
            verticalArrangement = Arrangement.SpaceBetween,
        ) {
            Row(Modifier.fillMaxWidth(), Arrangement.SpaceBetween, Alignment.Top) {
                Column {
                    Text("下一节 · 10:10", color = Color.White.copy(alpha = .76f), fontSize = 12.sp)
                    Spacer(Modifier.height(4.dp))
                    Text("数据结构", color = Color.White, fontSize = 23.sp, fontWeight = FontWeight.Bold)
                    Text("教学楼 2-305 · 张明远", color = Color.White.copy(alpha = .82f), fontSize = 12.sp)
                }
                Box(
                    Modifier.size(44.dp).clip(RoundedCornerShape(14.dp))
                        .background(Color.White.copy(alpha = .14f)),
                    contentAlignment = Alignment.Center,
                ) { Icon(Icons.Default.AutoStories, null, tint = Color.White) }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                HeroMeta(Icons.Default.MenuBook, "$count 门课程")
                HeroMeta(Icons.Default.Schedule, "本周 18 学时")
            }
        }
    }
}

@Composable
private fun HeroMeta(icon: androidx.compose.ui.graphics.vector.ImageVector, text: String) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
        Icon(icon, null, tint = Color.White.copy(alpha = .8f), modifier = Modifier.size(15.dp))
        Text(text, color = Color.White.copy(alpha = .88f), fontSize = 11.sp)
    }
}

@Composable
private fun CourseCard(course: Course, reduceMotion: Boolean, index: Int, onClick: () -> Unit) {
    val accent = when (course.type) {
        "公共基础" -> CourseOrange
        "学科基础" -> Color(0xFF35B99A)
        else -> CourseBlue
    }
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(Surface)
            .border(1.dp, Line.copy(alpha = .8f), RoundedCornerShape(20.dp))
            .campusClickable(onClick = onClick)
            .padding(16.dp)
            .enterAnimation(delayMs = index * 55, enabled = !reduceMotion),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(13.dp),
    ) {
        Box(
            Modifier.size(48.dp).clip(RoundedCornerShape(15.dp)).background(accent.copy(alpha = .12f)),
            contentAlignment = Alignment.Center,
        ) {
            Text(course.code.take(2), color = accent, fontWeight = FontWeight.ExtraBold, fontSize = 15.sp)
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                Text(course.name, fontWeight = FontWeight.Bold, fontSize = 15.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(
                    course.type,
                    color = accent,
                    fontSize = 9.sp,
                    modifier = Modifier.clip(RoundedCornerShape(6.dp)).background(accent.copy(alpha = .1f))
                        .padding(horizontal = 6.dp, vertical = 3.dp),
                )
            }
            Text("${course.teacher} · ${course.location}", color = Muted, fontSize = 12.sp)
            Text(course.code, color = Muted.copy(alpha = .8f), fontSize = 10.sp)
        }
        Icon(Icons.Default.ChevronRight, "查看课程详情", tint = Muted, modifier = Modifier.size(20.dp))
    }
}

@Composable
private fun EmptyCourses() {
    Column(
        Modifier.fillMaxWidth().padding(vertical = 48.dp),
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
        shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp),
    ) {
        Column(
            Modifier.fillMaxWidth().padding(start = 22.dp, end = 22.dp, bottom = 34.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(course.name, fontSize = 22.sp, fontWeight = FontWeight.ExtraBold)
            Text("${course.code} · ${course.type}", color = Primary, fontWeight = FontWeight.SemiBold)
            DetailRow(Icons.Default.Person, "授课教师", course.teacher)
            DetailRow(Icons.Default.LocationOn, "上课地点", course.location)
            DetailRow(Icons.Default.Schedule, "本周安排", "周一、周三 10:10–11:45")
            Button(
                onClick = onDismiss,
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(containerColor = CourseBlue),
            ) { Text("知道了", fontWeight = FontWeight.Bold) }
        }
    }
}

@Composable
private fun DetailRow(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String, value: String) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Box(
            Modifier.size(40.dp).clip(RoundedCornerShape(12.dp)).background(PrimarySoft),
            contentAlignment = Alignment.Center,
        ) { Icon(icon, null, tint = Primary, modifier = Modifier.size(20.dp)) }
        Column {
            Text(label, color = Muted, fontSize = 11.sp)
            Text(value, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
        }
    }
}

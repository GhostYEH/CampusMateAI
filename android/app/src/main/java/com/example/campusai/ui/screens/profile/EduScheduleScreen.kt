package com.example.campusai.ui.screens.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CalendarToday
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.campusai.data.remote.EduScheduleItemDto
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary

private val WEEKDAY_NAMES = listOf("周一", "周二", "周三", "周四", "周五", "周六", "周日")

private val COURSE_COLORS = listOf(
    0xFF5B70ED, 0xFFF29A49, 0xFF37B89B, 0xFF9369E8,
    0xFFE85B7A, 0xFF42A5F5, 0xFF66BB6A, 0xFFAB47BC,
)

@Composable
fun EduScheduleScreen(
    onBack: () -> Unit,
    viewModel: EduViewModel = viewModel(),
) {
    val scheduleItems by viewModel.scheduleItems.collectAsState()
    var currentWeek by remember { mutableIntStateOf(1) }
    var selectedCourse by remember { mutableStateOf<EduScheduleItemDto?>(null) }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(Unit) {
        loading = true
        viewModel.loadScheduleItems(null)
        loading = false
    }

    val allItems = scheduleItems?.items.orEmpty().filter { !it.is_stale }
    val weekFiltered = allItems.filter { weeksContains(it.weeks, it.week_text, currentWeek) }
    val byWeekday = (1..7).associateWith { wd -> weekFiltered.filter { it.weekday == wd } }

    Column(modifier = Modifier.fillMaxSize().background(Background)) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "返回") }
                Text("教务课表", fontSize = 20.sp, fontWeight = FontWeight.Bold)
            }
            IconButton(onClick = { viewModel.loadScheduleItems(null) }) {
                Icon(Icons.Default.Refresh, "刷新")
            }
        }
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Icon(Icons.Default.CalendarToday, null, tint = Muted, modifier = Modifier.size(16.dp))
            OutlinedButton(onClick = { if (currentWeek > 1) currentWeek-- }) { Text("上一周") }
            Text("第 $currentWeek 周", fontWeight = FontWeight.Bold)
            OutlinedButton(onClick = { if (currentWeek < 25) currentWeek++ }) { Text("下一周") }
        }
        if (loading) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        } else if (allItems.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("本学期暂无课程", fontWeight = FontWeight.SemiBold)
                    Text("请先在教务系统页面连接并同步课表", color = Muted, fontSize = 12.sp)
                }
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                (1..7).forEach { wd ->
                    val dayItems = byWeekday[wd].orEmpty().sortedWith(
                        compareBy(nullsLast()) { it.start_section ?: 99 }
                    )
                    if (dayItems.isNotEmpty()) {
                        item(key = "day_$wd") {
                            Text(
                                WEEKDAY_NAMES[wd - 1],
                                fontWeight = FontWeight.Bold,
                                fontSize = 14.sp,
                                color = Primary,
                            )
                        }
                        items(
                            dayItems,
                            key = { it.id ?: "${wd}_${it.course_code}_${it.start_section}_${it.location}_${it.weeks}" },
                        ) { item ->
                            ScheduleCourseCard(item = item, onClick = { selectedCourse = item })
                        }
                    }
                }
                if (weekFiltered.isEmpty()) {
                    item { Text("本周没有课程", color = Muted, modifier = Modifier.padding(16.dp)) }
                }
            }
        }
    }

    selectedCourse?.let { course ->
        CourseDetailBottomSheet(item = course, onDismiss = { selectedCourse = null })
    }
}

@Composable
private fun ScheduleCourseCard(item: EduScheduleItemDto, onClick: () -> Unit) {
    val colorIndex = ((item.course_code ?: item.course_name ?: "").hashCode() and 0x7FFFFFFF) % COURSE_COLORS.size
    val accent = Color(COURSE_COLORS[colorIndex])
    Column(
        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(Surface)
            .campusClickable(onClick = onClick).padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(3.dp),
    ) {
        Text(
            text = item.course_name ?: "未命名课程",
            fontWeight = FontWeight.Bold,
            fontSize = 14.sp,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            color = TextPrimary,
        )
        if (!item.location.isNullOrBlank()) {
            Text(
                text = item.location,
                color = Muted,
                fontSize = 11.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        if (item.start_section != null) {
            Text(
                text = "第${item.start_section}${if (item.end_section != null && item.end_section != item.start_section) "-${item.end_section}" else ""}节",
                color = accent,
                fontSize = 10.sp,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CourseDetailBottomSheet(item: EduScheduleItemDto, onDismiss: () -> Unit) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = Surface,
    ) {
        LazyColumn(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 22.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
            contentPadding = PaddingValues(bottom = 28.dp),
        ) {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(item.course_name ?: "未命名课程", fontSize = 22.sp, fontWeight = FontWeight.ExtraBold)
                    if (!item.course_code.isNullOrBlank()) Text(item.course_code, color = Muted, fontSize = 12.sp)
                }
            }
            val teachersText = formatTeachers(item.teachers, item.teacher)
            if (!teachersText.isNullOrBlank()) item { DetailRow("教师", teachersText) }
            val timeText = formatTime(item.weekday, item.start_section, item.end_section, item.start_time, item.end_time)
            if (!timeText.isNullOrBlank()) item { DetailRow("上课时间", timeText) }
            if (!item.location.isNullOrBlank()) item { DetailRow("地点", item.location) }
            val weeksText = formatWeeks(item.weeks, item.week_text)
            if (!weeksText.isNullOrBlank()) item { DetailRow("周次", weeksText) }
            if (item.credit != null) item { DetailRow("学分", formatCredit(item.credit)) }
            if (!item.course_nature.isNullOrBlank()) item { DetailRow("课程性质", item.course_nature) }
            if (!item.course_category.isNullOrBlank()) item { DetailRow("课程类别", item.course_category) }
            if (!item.course_type.isNullOrBlank()) item { DetailRow("课程类型", item.course_type) }
            if (!item.teaching_class.isNullOrBlank()) item { DetailRow("教学班", item.teaching_class) }
            if (!item.assessment_method.isNullOrBlank()) item { DetailRow("考核方式", item.assessment_method) }
            if (!item.exam_type.isNullOrBlank()) item { DetailRow("考试类型", item.exam_type) }
            if (!item.college.isNullOrBlank()) item { DetailRow("开课学院", item.college) }
            if (!item.department.isNullOrBlank()) item { DetailRow("开课系", item.department) }
            if (!item.campus.isNullOrBlank()) item { DetailRow("校区", item.campus) }
            if (!item.class_name.isNullOrBlank()) item { DetailRow("班级", item.class_name) }
            if (item.total_hours != null) item { DetailRow("总学时", formatHours(item.total_hours)) }
            if (item.theory_hours != null) item { DetailRow("理论学时", formatHours(item.theory_hours)) }
            if (item.practice_hours != null) item { DetailRow("实践学时", formatHours(item.practice_hours)) }
            if (!item.language.isNullOrBlank()) item { DetailRow("授课语言", item.language) }
            if (!item.semester.isNullOrBlank()) item { DetailRow("学期", item.semester) }
            if (!item.note.isNullOrBlank()) item { DetailRow("备注", item.note) }
            val extra = item.extra_info
            if (extra != null && extra.isNotEmpty()) {
                item { Text("更多信息", fontWeight = FontWeight.Bold, fontSize = 13.sp, modifier = Modifier.padding(top = 8.dp)) }
                extra.forEach { (k, v) ->
                    val vs = v?.toString()
                    if (!vs.isNullOrBlank()) item { DetailRow(k, vs) }
                }
            }
            item {
                Text("数据来源：学校教务系统", color = Muted, fontSize = 10.sp, modifier = Modifier.padding(top = 12.dp))
            }
        }
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = Muted, fontSize = 12.sp)
        Text(value, fontWeight = FontWeight.SemiBold, fontSize = 13.sp, maxLines = 3, overflow = TextOverflow.Ellipsis)
    }
}

private fun formatTeachers(teachers: List<String>?, teacher: String?): String? {
    val list = teachers?.filter { !it.isNullOrBlank() }
    if (!list.isNullOrEmpty()) return list.joinToString("、")
    if (!teacher.isNullOrBlank()) return teacher
    return null
}

private fun formatTime(weekday: Int?, start: Int?, end: Int?, startTime: String?, endTime: String?): String? {
    if (weekday == null && start == null) return null
    val sb = StringBuilder()
    if (weekday != null && weekday in 1..7) sb.append(WEEKDAY_NAMES[weekday - 1])
    if (start != null) {
        sb.append(" 第").append(start)
        if (end != null && end != start) sb.append("-").append(end)
        sb.append("节")
    }
    if (!startTime.isNullOrBlank() || !endTime.isNullOrBlank()) {
        sb.append("\n").append(startTime ?: "").append(if (!endTime.isNullOrBlank()) "-$endTime" else "")
    }
    return sb.toString().ifBlank { null }
}

private fun formatWeeks(weeks: String?, weekText: String?): String? {
    if (!weekText.isNullOrBlank()) return if (!weeks.isNullOrBlank()) "$weekText（$weeks）" else weekText
    return weeks
}

private fun formatCredit(credit: Double): String {
    return if (credit == credit.toInt().toDouble()) "${credit.toInt()} 学分" else "$credit 学分"
}

private fun formatHours(hours: Double): String {
    return if (hours == hours.toInt().toDouble()) "${hours.toInt()}" else "$hours"
}

fun weeksContains(weeks: String?, weekText: String?, week: Int): Boolean {
    val w = weeks?.trim()
    if (w.isNullOrBlank()) return true
    if (weekText?.contains("单") == true && week % 2 == 0) return false
    if (weekText?.contains("双") == true && week % 2 == 1) return false
    val cleaned = w.replace("周", "").replace(" ", "")
    val parts = cleaned.split(",", "，", ";", "；")
    for (part in parts) {
        val p = part.trim()
        if (p.isEmpty()) continue
        if (p.endsWith("单") && week % 2 == 0) continue
        if (p.endsWith("双") && week % 2 == 1) continue
        val core = p.removeSuffix("单").removeSuffix("双")
        if (core.contains("-")) {
            val range = core.split("-")
            if (range.size == 2) {
                val s = range[0].toIntOrNull()
                val e = range[1].toIntOrNull()
                if (s != null && e != null && week in s..e) return true
            }
        } else {
            val n = core.toIntOrNull()
            if (n != null && n == week) return true
        }
    }
    return false
}

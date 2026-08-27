package com.example.campusai.ui.screens.exams

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Image
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
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Code
import androidx.compose.material.icons.filled.EventBusy
import androidx.compose.material.icons.filled.Functions
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.NotificationsOff
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.Translate
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.R
import com.example.campusai.data.model.Exam
import com.example.campusai.data.model.ExamStatus
import com.example.campusai.data.repository.ExamRepository
import com.example.campusai.ui.components.EmptyState
import com.example.campusai.ui.components.ErrorState
import com.example.campusai.ui.components.LoadingState
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.strings.CampusStrings
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.DateTimeFormatter

@Composable
fun ExamsScreen(
    repository: ExamRepository,
    reduceMotion: Boolean,
    onBack: () -> Unit,
    onOpenDetail: (Long) -> Unit,
    onOpenEdit: (Long?) -> Unit,
) {
    val exams by repository.exams.collectAsStateWithLifecycle()
    val loading by repository.loading.collectAsStateWithLifecycle()
    val error by repository.error.collectAsStateWithLifecycle()
    var filter by remember { mutableStateOf(CampusStrings.Exams.FILTER_ALL) }
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        while (true) {
            delay(60_000)
            now = System.currentTimeMillis()
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 20.dp),
    ) {
        when {
            loading -> LoadingState()
            error != null -> ErrorState(error ?: CampusStrings.Exams.LOAD_ERROR, onRetry = {
                scope.launch { repository.refresh() }
            })
            else -> {
                val ordered = exams.sortedBy { it.startDateTime() }
                val upcoming = ordered.filter { it.statusAt(now) == ExamStatus.UPCOMING }
                AnimatedContent(
                    targetState = filter,
                    transitionSpec = { fadeIn() togetherWith fadeOut() },
                    label = "exam-filter-content",
                ) { selectedFilter ->
                    val filtered = when (selectedFilter) {
                        CampusStrings.Exams.FILTER_UPCOMING -> upcoming
                        CampusStrings.Exams.FILTER_ENDED -> ordered.filter { it.statusAt(now) == ExamStatus.ENDED }
                        else -> ordered
                    }
                    val grouped = filtered.groupBy { it.date }
                    LazyColumn(
                        verticalArrangement = Arrangement.spacedBy(14.dp),
                        contentPadding = PaddingValues(
                            top = 10.dp,
                            bottom = WindowInsets.navigationBars.asPaddingValues()
                                .calculateBottomPadding() + BottomDockReservedHeight + 22.dp,
                        ),
                    ) {
                        item(key = "overview") {
                            ExamOverview(
                                upcoming = upcoming.firstOrNull(),
                                upcomingCount = upcoming.size,
                                now = now,
                                reduceMotion = reduceMotion,
                                onClick = { upcoming.firstOrNull()?.let { onOpenDetail(it.id) } },
                            )
                        }
                        item(key = "filters") {
                            ExamFilterTabs(selected = selectedFilter, onSelect = { filter = it })
                        }
                        if (filtered.isEmpty()) {
                            item { EmptyState(Icons.Default.EventBusy, CampusStrings.Exams.EMPTY) }
                        } else {
                            item(key = "schedule-label") {
                                ExamScheduleLabel(count = filtered.size)
                            }
                            grouped.forEach { (date, dateExams) ->
                                item(key = "date-$date") { ExamDateHeader(date) }
                                itemsIndexed(
                                    items = dateExams,
                                    key = { index, exam -> "exam|${exam.id}|$date|$index" },
                                ) { _, exam ->
                                    ExamTimelineItem(
                                        exam = exam,
                                        now = now,
                                        reduceMotion = reduceMotion,
                                        onClick = { onOpenDetail(exam.id) },
                                        onToggleReminder = { enabled ->
                                            scope.launch { repository.setReminder(exam.id, enabled) }
                                        },
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
        Box(
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(end = 6.dp, bottom = BottomDockReservedHeight + 20.dp),
        ) {
            ExamCreateFab(onClick = { onOpenEdit(null) })
        }
    }
}

@Composable
private fun ExamOverview(
    upcoming: Exam?,
    upcomingCount: Int,
    now: Long,
    reduceMotion: Boolean,
    onClick: () -> Unit,
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(24.dp))
            .background(if (upcoming == null) Surface else Primary)
            .border(1.dp, if (upcoming == null) Line else Primary, RoundedCornerShape(24.dp))
            .campusClickable(enabled = upcoming != null, onClick = onClick)
            .enterAnimation(enabled = !reduceMotion)
            .padding(18.dp),
    ) {
        if (upcoming == null) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier.size(48.dp).clip(CircleShape).background(PrimarySoft),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(Icons.Default.EventBusy, null, tint = Primary, modifier = Modifier.size(24.dp))
                }
                Spacer(Modifier.width(13.dp))
                Column {
                    Text(CampusStrings.Exams.NO_UPCOMING, color = TextPrimary, fontSize = 17.sp, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(5.dp))
                    Text(CampusStrings.Exams.OVERVIEW_EMPTY_HINT, color = Muted, fontSize = 12.sp)
                }
            }
        } else {
            val days = upcoming.daysUntil(now)
            Image(
                painter = painterResource(R.drawable.exam_calendar_hero),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .align(Alignment.CenterEnd)
                    .padding(end = 10.dp)
                    .size(122.dp)
                    .clip(CircleShape),
                alpha = .46f,
            )
            Column {
                Row(
                    modifier = Modifier.padding(end = 106.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    DateTile(upcoming)
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.AutoAwesome, null, tint = Color.White.copy(alpha = .88f), modifier = Modifier.size(14.dp))
                            Spacer(Modifier.width(5.dp))
                            Text(CampusStrings.Exams.NEAREST_TITLE, color = Color.White.copy(alpha = .88f), fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                        }
                        Spacer(Modifier.height(7.dp))
                        Text(upcoming.courseName, color = Color.White, fontSize = 19.sp, fontWeight = FontWeight.ExtraBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Spacer(Modifier.height(7.dp))
                        Text("${upcoming.startTime}–${upcoming.endTime} · ${upcoming.location}", color = Color.White.copy(alpha = .88f), fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                }
                Spacer(Modifier.height(15.dp))
                Box(Modifier.fillMaxWidth().height(1.dp).background(Color.White.copy(alpha = .18f)))
                Spacer(Modifier.height(11.dp))
                Text(
                    text = if (days == 0L) {
                        "${CampusStrings.Exams.TODAY} · ${CampusStrings.Exams.OVERVIEW_COUNT.format(upcomingCount)}"
                    } else {
                        "${days ?: 0}${CampusStrings.Exams.DAYS_LEFT} · ${CampusStrings.Exams.OVERVIEW_COUNT.format(upcomingCount)}"
                    },
                    color = Color.White.copy(alpha = .88f),
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Medium,
                )
            }
        }
    }
}

@Composable
private fun ExamCreateFab(onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .size(56.dp)
            .shadow(12.dp, CircleShape, ambientColor = Primary.copy(alpha = .28f), spotColor = Primary.copy(alpha = .36f))
            .clip(CircleShape)
            .background(Primary)
            .campusClickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Icon(Icons.Default.Add, CampusStrings.Exams.ADD, tint = Color.White, modifier = Modifier.size(29.dp))
    }
}

@Composable
private fun DateTile(exam: Exam) {
    val date = runCatching { LocalDate.parse(exam.date) }.getOrNull()
    Column(
        modifier = Modifier
            .width(54.dp)
            .height(64.dp)
            .clip(RoundedCornerShape(16.dp))
            .background(Color.White.copy(alpha = .18f)),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(date?.monthValue?.toString() ?: "--", color = Color.White.copy(alpha = .8f), fontSize = 11.sp, fontWeight = FontWeight.Bold)
        Text(date?.dayOfMonth?.toString() ?: "--", color = Color.White, fontSize = 24.sp, fontWeight = FontWeight.ExtraBold)
    }
}

@Composable
private fun ExamFilterTabs(selected: String, onSelect: (String) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        listOf(CampusStrings.Exams.FILTER_ALL, CampusStrings.Exams.FILTER_UPCOMING, CampusStrings.Exams.FILTER_ENDED).forEach { option ->
            val active = option == selected
            Box(
                modifier = Modifier
                    .clip(CircleShape)
                    .background(if (active) Primary else Surface)
                    .border(1.dp, if (active) Primary else Line, CircleShape)
                    .campusClickable { onSelect(option) }
                    .padding(horizontal = 18.dp, vertical = 9.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(option, color = if (active) Color.White else Muted, fontSize = 13.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
private fun ExamScheduleLabel(count: Int) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(CampusStrings.Exams.SCHEDULE_TITLE, color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.width(8.dp))
        Text(CampusStrings.Exams.SCHEDULE_COUNT.format(count), color = Muted, fontSize = 12.sp, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun ExamDateHeader(date: String) {
    val label = runCatching { LocalDate.parse(date).format(DateTimeFormatter.ofPattern("M月d日 EEEE")) }.getOrDefault(date)
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(8.dp).clip(CircleShape).background(Primary))
        Spacer(Modifier.width(8.dp))
        Text(label, color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun ExamTimelineItem(
    exam: Exam,
    now: Long,
    reduceMotion: Boolean,
    onClick: () -> Unit,
    onToggleReminder: (Boolean) -> Unit,
) {
    val upcoming = exam.statusAt(now) == ExamStatus.UPCOMING
    val accent = if (upcoming) Primary else Color(0xFF8795A8)
    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
        Column(
            modifier = Modifier.width(44.dp).padding(top = 17.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(exam.startTime, color = accent, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)
            Spacer(Modifier.height(6.dp))
            Box(Modifier.size(9.dp).clip(CircleShape).background(accent))
        }
        Box(
            modifier = Modifier
                .weight(1f)
                .shadow(5.dp, RoundedCornerShape(20.dp), ambientColor = Color(0x120E1A38), spotColor = Color(0x120E1A38))
                .clip(RoundedCornerShape(20.dp))
                .background(Surface)
                .border(1.dp, Line, RoundedCornerShape(20.dp))
                .campusClickable(onClick = onClick)
                .enterAnimation(enabled = !reduceMotion),
        ) {
            Row(modifier = Modifier.padding(15.dp), verticalAlignment = Alignment.CenterVertically) {
                SubjectIcon(exam, accent, upcoming)
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(exam.courseName, color = TextPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f, fill = false))
                        Spacer(Modifier.width(6.dp))
                        ExamTypeTag(exam.type, upcoming)
                    }
                    Spacer(Modifier.height(8.dp))
                    ExamMeta(Icons.Default.Schedule, "${exam.startTime}–${exam.endTime}")
                    Spacer(Modifier.height(5.dp))
                    ExamMeta(Icons.Default.LocationOn, "${exam.location} · ${CampusStrings.Exams.SEAT_PREFIX}${exam.seatNumber}")
                }
                Spacer(Modifier.width(5.dp))
                Box(
                    modifier = Modifier
                        .size(36.dp)
                        .clip(CircleShape)
                        .background(if (exam.reminderEnabled) PrimarySoft else Background)
                        .campusClickable { onToggleReminder(!exam.reminderEnabled) },
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        if (exam.reminderEnabled) Icons.Default.Notifications else Icons.Default.NotificationsOff,
                        contentDescription = if (exam.reminderEnabled) "关闭${CampusStrings.Exams.REMINDER}" else "开启${CampusStrings.Exams.REMINDER}",
                        tint = if (exam.reminderEnabled) Primary else Muted,
                        modifier = Modifier.size(20.dp),
                    )
                }
            }
        }
    }
}

@Composable
private fun SubjectIcon(exam: Exam, tint: Color, upcoming: Boolean) {
    val icon = when {
        exam.courseName.contains("英语") -> Icons.Default.Translate
        exam.courseName.contains("数据") || exam.courseName.contains("网络") -> Icons.Default.Code
        exam.courseName.contains("计算机") || exam.courseName.contains("组成") -> Icons.Default.Memory
        else -> Icons.Default.Functions
    }
    Box(
        modifier = Modifier.size(44.dp).clip(RoundedCornerShape(14.dp)).background(if (upcoming) PrimarySoft else Background),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, null, tint = tint, modifier = Modifier.size(22.dp))
    }
}

@Composable
private fun ExamTypeTag(type: String, upcoming: Boolean) {
    Text(
        type,
        color = if (upcoming) Primary else Muted,
        fontSize = 10.sp,
        fontWeight = FontWeight.SemiBold,
        maxLines = 1,
        modifier = Modifier.clip(CircleShape).background(if (upcoming) PrimarySoft else Background).padding(horizontal = 7.dp, vertical = 4.dp),
    )
}

@Composable
private fun ExamMeta(icon: ImageVector, text: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = Muted, modifier = Modifier.size(14.dp))
        Spacer(Modifier.width(5.dp))
        Text(text, color = Muted, fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

package com.example.campusai.ui.screens.exams

import androidx.compose.foundation.background
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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.EventBusy
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.NotificationsOff
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.Exam
import com.example.campusai.data.model.ExamStatus
import com.example.campusai.data.repository.ExamRepository
import com.example.campusai.ui.components.CampusCard
import com.example.campusai.ui.components.CampusPageHeader
import com.example.campusai.ui.components.EmptyState
import com.example.campusai.ui.components.ErrorState
import com.example.campusai.ui.components.FilterChipRow
import com.example.campusai.ui.components.LoadingState
import com.example.campusai.ui.components.StatusTag
import com.example.campusai.ui.components.StatusTone
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
import androidx.compose.runtime.LaunchedEffect

@Composable
fun ExamsScreen(
    repository: ExamRepository,
    reduceMotion: Boolean,
    onBack: () -> Unit,
    onOpenDetail: (Long) -> Unit,
    onOpenEdit: (Long?) -> Unit,
) {
    val exams by repository.exams.collectAsState()
    val loading by repository.loading.collectAsState()
    val error by repository.error.collectAsState()
    var filter by remember { mutableStateOf(CampusStrings.Exams.FILTER_ALL) }
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        while (true) {
            delay(60_000)
            now = System.currentTimeMillis()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 16.dp),
    ) {
        Spacer(Modifier.height(12.dp))
        CampusPageHeader(
            title = CampusStrings.Exams.TITLE,
            subtitle = CampusStrings.Exams.SUBTITLE,
            onBack = onBack,
            actions = {
                Box(
                    modifier = Modifier
                        .size(36.dp)
                        .clip(CircleShape)
                        .background(Primary)
                        .campusClickable { onOpenEdit(null) },
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(Icons.Default.Add, CampusStrings.Exams.ADD, tint = Color.White, modifier = Modifier.size(19.dp))
                }
            },
        )
        Spacer(Modifier.height(14.dp))

        when {
            loading -> LoadingState()
            error != null -> ErrorState(error ?: CampusStrings.Exams.LOAD_ERROR, onRetry = {
                scope.launch { repository.refresh() }
            })
            else -> {
                val upcoming = exams.filter { it.statusAt(now) == ExamStatus.UPCOMING }
                val filtered = when (filter) {
                    CampusStrings.Exams.FILTER_UPCOMING -> upcoming
                    CampusStrings.Exams.FILTER_ENDED -> exams.filter { it.statusAt(now) == ExamStatus.ENDED }
                    else -> exams
                }
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                    contentPadding = PaddingValues(
                        bottom = WindowInsets.navigationBars.asPaddingValues()
                            .calculateBottomPadding() + BottomDockReservedHeight + 16.dp,
                    ),
                ) {
                    if (upcoming.isNotEmpty()) {
                        item {
                            NearestExamCard(
                                exam = upcoming.first(),
                                now = now,
                                reduceMotion = reduceMotion,
                                onClick = { onOpenDetail(upcoming.first().id) },
                            )
                        }
                    }
                    item {
                        FilterChipRow(
                            options = listOf(
                                CampusStrings.Exams.FILTER_ALL,
                                CampusStrings.Exams.FILTER_UPCOMING,
                                CampusStrings.Exams.FILTER_ENDED,
                            ),
                            selected = filter,
                            onSelect = { filter = it },
                        )
                    }
                    if (filtered.isEmpty()) {
                        item {
                            EmptyState(Icons.Default.EventBusy, CampusStrings.Exams.EMPTY)
                        }
                    } else {
                        items(filtered, key = { it.id }) { exam ->
                            ExamRow(
                                exam = exam,
                                now = now,
                                onClick = { onOpenDetail(exam.id) },
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun NearestExamCard(
    exam: Exam,
    now: Long,
    reduceMotion: Boolean,
    onClick: () -> Unit,
) {
    val days = exam.daysUntil(now)
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(20.dp))
            .background(Primary)
            .campusClickable(onClick = onClick)
            .enterAnimation(enabled = !reduceMotion)
            .padding(18.dp),
    ) {
        Text(CampusStrings.Exams.NEAREST_TITLE, color = Color.White.copy(alpha = .8f), fontSize = 11.sp)
        Spacer(Modifier.height(8.dp))
        Row(verticalAlignment = Alignment.Bottom) {
            Text(
                if (days == 0L) CampusStrings.Exams.TODAY else "${days ?: 0}",
                color = Color.White,
                fontSize = if (days == 0L) 22.sp else 34.sp,
                fontWeight = FontWeight.Bold,
            )
            if (days != 0L && days != null) {
                Spacer(Modifier.width(6.dp))
                Text(
                    CampusStrings.Exams.DAYS_LEFT,
                    color = Color.White.copy(alpha = .85f),
                    fontSize = 13.sp,
                    modifier = Modifier.padding(bottom = 5.dp),
                )
            }
        }
        Spacer(Modifier.height(10.dp))
        Text(exam.courseName, color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(4.dp))
        Text(
            "${exam.dateLabel()}  ${exam.startTime}-${exam.endTime}  ·  ${exam.location}",
            color = Color.White.copy(alpha = .82f),
            fontSize = 12.sp,
        )
    }
}

@Composable
private fun ExamRow(exam: Exam, now: Long, onClick: () -> Unit) {
    val status = exam.statusAt(now)
    CampusCard(
        modifier = Modifier.campusClickable(onClick = onClick),
        padding = PaddingValues(14.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        exam.courseName,
                        color = TextPrimary,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.weight(1f, fill = false),
                    )
                    Spacer(Modifier.width(8.dp))
                    StatusTag(exam.type, StatusTone.NEUTRAL)
                }
                Spacer(Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Schedule, null, tint = Muted, modifier = Modifier.size(14.dp))
                    Spacer(Modifier.width(5.dp))
                    Text(
                        "${exam.dateLabel()}  ${exam.startTime}-${exam.endTime}",
                        color = Muted,
                        fontSize = 12.sp,
                    )
                }
                Spacer(Modifier.height(4.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.LocationOn, null, tint = Muted, modifier = Modifier.size(14.dp))
                    Spacer(Modifier.width(5.dp))
                    Text(
                        "${exam.location} · 座位 ${exam.seatNumber}",
                        color = Muted,
                        fontSize = 12.sp,
                    )
                }
            }
            Spacer(Modifier.width(10.dp))
            Column(horizontalAlignment = Alignment.End) {
                StatusTag(
                    text = if (status == ExamStatus.UPCOMING) CampusStrings.Exams.FILTER_UPCOMING else CampusStrings.Exams.FILTER_ENDED,
                    tone = if (status == ExamStatus.UPCOMING) StatusTone.INFO else StatusTone.NEUTRAL,
                )
                Spacer(Modifier.height(8.dp))
                Icon(
                    if (exam.reminderEnabled) Icons.Default.Notifications else Icons.Default.NotificationsOff,
                    contentDescription = CampusStrings.Exams.REMINDER,
                    tint = if (exam.reminderEnabled) Primary else Muted,
                    modifier = Modifier.size(17.dp),
                )
            }
        }
    }
}

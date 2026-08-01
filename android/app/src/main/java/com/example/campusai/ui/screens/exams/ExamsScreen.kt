package com.example.campusai.ui.screens.exams

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Image
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
import androidx.compose.foundation.layout.weight
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
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
import com.example.campusai.ui.components.CampusPageHeader
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
            .padding(horizontal = 20.dp),
    ) {
        Spacer(Modifier.height(16.dp))
        CampusPageHeader(
            title = CampusStrings.Exams.TITLE,
            subtitle = CampusStrings.Exams.SUBTITLE,
            onBack = onBack,
            actions = {
                Box(
                    modifier = Modifier
                        .size(48.dp)
                        .shadow(10.dp, CircleShape, ambientColor = Primary.copy(alpha = .28f), spotColor = Primary.copy(alpha = .36f))
                        .clip(CircleShape)
                        .background(Brush.linearGradient(listOf(Color(0xFF6679FF), Color(0xFF4054EF))))
                        .campusClickable { onOpenEdit(null) },
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(Icons.Default.Add, CampusStrings.Exams.ADD, tint = Color.White, modifier = Modifier.size(28.dp))
                }
            },
        )
        Spacer(Modifier.height(18.dp))

        when {
            loading -> LoadingState()
            error != null -> ErrorState(error ?: CampusStrings.Exams.LOAD_ERROR, onRetry = {
                scope.launch { repository.refresh() }
            })
            else -> {
                val upcoming = exams.filter { it.statusAt(now) == ExamStatus.UPCOMING }
                AnimatedContent(
                    targetState = filter,
                    transitionSpec = { fadeIn() togetherWith fadeOut() },
                    label = "exam-filter-content",
                ) { selectedFilter ->
                    val filtered = when (selectedFilter) {
                        CampusStrings.Exams.FILTER_UPCOMING -> upcoming
                        CampusStrings.Exams.FILTER_ENDED -> exams.filter { it.statusAt(now) == ExamStatus.ENDED }
                        else -> exams
                    }
                    LazyColumn(
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                        contentPadding = PaddingValues(
                            bottom = WindowInsets.navigationBars.asPaddingValues()
                                .calculateBottomPadding() + BottomDockReservedHeight + 20.dp,
                        ),
                    ) {
                        if (upcoming.isNotEmpty()) {
                            item(key = "nearest") {
                                NearestExamCard(
                                    exam = upcoming.first(),
                                    now = now,
                                    reduceMotion = reduceMotion,
                                    onClick = { onOpenDetail(upcoming.first().id) },
                                )
                            }
                        }
                        item(key = "filters") {
                            ExamFilterTabs(selected = selectedFilter, onSelect = { filter = it })
                        }
                        if (filtered.isEmpty()) {
                            item { EmptyState(Icons.Default.EventBusy, CampusStrings.Exams.EMPTY) }
                        } else {
                            items(filtered, key = { it.id }) { exam ->
                                ExamScheduleCard(
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
}

@Composable
private fun NearestExamCard(
    exam: Exam,
    now: Long,
    reduceMotion: Boolean,
    onClick: () -> Unit,
) {
    val days = exam.daysUntil(now)
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(218.dp)
            .clip(RoundedCornerShape(28.dp))
            .background(Brush.linearGradient(listOf(Color(0xFF6877FB), Color(0xFF3547E5))))
            .campusClickable(onClick = onClick)
            .enterAnimation(enabled = !reduceMotion),
    ) {
        Image(
            painter = painterResource(R.drawable.exam_calendar_hero),
            contentDescription = null,
            contentScale = ContentScale.Crop,
            modifier = Modifier
                .align(Alignment.CenterEnd)
                .padding(end = 4.dp)
                .size(196.dp)
                .clip(CircleShape),
            alpha = .92f,
        )
        Column(
            modifier = Modifier
                .align(Alignment.TopStart)
                .padding(start = 24.dp, top = 22.dp, end = 126.dp),
        ) {
            Row(
                modifier = Modifier
                    .clip(CircleShape)
                    .background(Color.White.copy(alpha = .13f))
                    .padding(horizontal = 11.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Icons.Default.AutoAwesome, null, tint = Color.White, modifier = Modifier.size(15.dp))
                Spacer(Modifier.width(6.dp))
                Text(CampusStrings.Exams.NEAREST_TITLE, color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
            }
            Spacer(Modifier.height(16.dp))
            Row(verticalAlignment = Alignment.Bottom) {
                Text(
                    text = if (days == 0L) "今天" else "${days ?: 0}",
                    color = Color.White,
                    fontSize = if (days == 0L) 30.sp else 58.sp,
                    lineHeight = if (days == 0L) 34.sp else 58.sp,
                    fontWeight = FontWeight.ExtraBold,
                )
                if (days != 0L) {
                    Spacer(Modifier.width(7.dp))
                    Text(CampusStrings.Exams.DAYS_LEFT, color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(bottom = 9.dp))
                }
            }
            Spacer(Modifier.height(6.dp))
            Text(
                exam.courseName,
                color = Color.White,
                fontSize = 27.sp,
                fontWeight = FontWeight.ExtraBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Row(
            modifier = Modifier
                .align(Alignment.BottomStart)
                .padding(start = 24.dp, end = 20.dp, bottom = 20.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(Icons.Default.Schedule, null, tint = Color.White, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(7.dp))
            Text("${exam.dateLabel()}  ${exam.startTime}-${exam.endTime}", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Medium)
            Spacer(Modifier.width(10.dp))
            Icon(Icons.Default.LocationOn, null, tint = Color.White, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(4.dp))
            Text(exam.location, color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}

@Composable
private fun ExamFilterTabs(selected: String, onSelect: (String) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        listOf(
            CampusStrings.Exams.FILTER_ALL,
            CampusStrings.Exams.FILTER_UPCOMING,
            CampusStrings.Exams.FILTER_ENDED,
        ).forEach { option ->
            val active = option == selected
            Box(
                modifier = Modifier
                    .shadow(if (active) 7.dp else 2.dp, CircleShape, ambientColor = Primary.copy(alpha = .2f), spotColor = Primary.copy(alpha = .2f))
                    .clip(CircleShape)
                    .background(if (active) Primary else Surface)
                    .campusClickable { onSelect(option) }
                    .padding(horizontal = 21.dp, vertical = 11.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(option, color = if (active) Color.White else Muted, fontSize = 14.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
private fun ExamScheduleCard(
    exam: Exam,
    now: Long,
    reduceMotion: Boolean,
    onClick: () -> Unit,
    onToggleReminder: (Boolean) -> Unit,
) {
    val upcoming = exam.statusAt(now) == ExamStatus.UPCOMING
    val accent = if (upcoming) Primary else Color(0xFF718097)
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .shadow(7.dp, RoundedCornerShape(24.dp), ambientColor = Color(0x160E1A38), spotColor = Color(0x160E1A38))
            .clip(RoundedCornerShape(24.dp))
            .background(Surface)
            .campusClickable(onClick = onClick)
            .enterAnimation(enabled = !reduceMotion),
    ) {
        Box(
            modifier = Modifier
                .align(Alignment.CenterStart)
                .width(6.dp)
                .height(150.dp)
                .clip(RoundedCornerShape(topEnd = 6.dp, bottomEnd = 6.dp))
                .background(accent),
        )
        Row(
            modifier = Modifier.padding(start = 22.dp, top = 18.dp, end = 18.dp, bottom = 18.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            SubjectIcon(exam = exam, tint = accent, upcoming = upcoming)
            Spacer(Modifier.width(16.dp))
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        exam.courseName,
                        color = TextPrimary,
                        fontSize = 19.sp,
                        fontWeight = FontWeight.Bold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f, fill = false),
                    )
                    Spacer(Modifier.width(8.dp))
                    ExamTypeTag(exam.type, upcoming)
                }
                Spacer(Modifier.height(11.dp))
                ExamMeta(Icons.Default.Schedule, "${exam.dateLabel()}  ${exam.startTime}-${exam.endTime}")
                Spacer(Modifier.height(7.dp))
                ExamMeta(Icons.Default.LocationOn, "${exam.location} · 座位 ${exam.seatNumber}")
            }
            Spacer(Modifier.width(8.dp))
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    text = if (upcoming) CampusStrings.Exams.FILTER_UPCOMING else CampusStrings.Exams.FILTER_ENDED,
                    color = if (upcoming) Primary else Muted,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier
                        .clip(CircleShape)
                        .background(if (upcoming) PrimarySoft else Background)
                        .padding(horizontal = 12.dp, vertical = 7.dp),
                )
                Spacer(Modifier.height(13.dp))
                Box(
                    modifier = Modifier
                        .size(36.dp)
                        .clip(CircleShape)
                        .campusClickable { onToggleReminder(!exam.reminderEnabled) },
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        if (exam.reminderEnabled) Icons.Default.Notifications else Icons.Default.NotificationsOff,
                        contentDescription = if (exam.reminderEnabled) "关闭${CampusStrings.Exams.REMINDER}" else "开启${CampusStrings.Exams.REMINDER}",
                        tint = if (exam.reminderEnabled) Primary else Muted,
                        modifier = Modifier.size(23.dp),
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
        modifier = Modifier
            .size(58.dp)
            .shadow(7.dp, CircleShape, ambientColor = tint.copy(alpha = .22f), spotColor = tint.copy(alpha = .22f))
            .clip(CircleShape)
            .background(if (upcoming) tint else Color(0xFFE9EDF5)),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, null, tint = if (upcoming) Color.White else Muted, modifier = Modifier.size(29.dp))
    }
}

@Composable
private fun ExamTypeTag(type: String, upcoming: Boolean) {
    Text(
        type,
        color = if (upcoming) Primary else Muted,
        fontSize = 11.sp,
        fontWeight = FontWeight.SemiBold,
        modifier = Modifier
            .clip(CircleShape)
            .background(if (upcoming) PrimarySoft else Background)
            .padding(horizontal = 8.dp, vertical = 5.dp),
    )
}

@Composable
private fun ExamMeta(icon: ImageVector, text: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = Muted, modifier = Modifier.size(17.dp))
        Spacer(Modifier.width(7.dp))
        Text(text, color = Muted, fontSize = 13.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

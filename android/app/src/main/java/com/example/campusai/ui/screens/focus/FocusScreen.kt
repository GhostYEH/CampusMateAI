package com.example.campusai.ui.screens.focus

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
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.LocalFireDepartment
import androidx.compose.material.icons.filled.SelfImprovement
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
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
import com.example.campusai.data.model.FocusMode
import com.example.campusai.data.model.FocusTimerState
import com.example.campusai.data.repository.FocusRepository
import com.example.campusai.ui.components.AnimatedCircularProgress
import com.example.campusai.ui.components.CampusCard
import com.example.campusai.ui.components.CampusPageHeader
import com.example.campusai.ui.components.ConfirmDialog
import com.example.campusai.ui.components.EmptyState
import com.example.campusai.ui.components.FilterChipRow
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

@Composable
fun FocusScreen(
    repository: FocusRepository,
    reduceMotion: Boolean,
    onBack: () -> Unit,
    onOpenCounselorPlan: (String) -> Unit,
) {
    val records by repository.records.collectAsState()
    val stats by repository.stats.collectAsState()
    val persistedTimer by repository.timer.collectAsState()
    val loading by repository.loading.collectAsState()
    val scope = rememberCoroutineScope()

    var mode by remember { mutableStateOf(FocusMode.FOCUS) }
    var secondsLeft by remember { mutableIntStateOf(FocusMode.FOCUS.totalSeconds) }
    var running by remember { mutableStateOf(false) }
    var restored by remember { mutableStateOf(false) }
    var showEndConfirm by remember { mutableStateOf(false) }
    var showCompleted by remember { mutableStateOf(false) }

    // 恢复上次退出时保存的计时状态（页面退出后状态不丢失）
    LaunchedEffect(loading) {
        if (!loading && !restored) {
            restored = true
            val saved = persistedTimer ?: return@LaunchedEffect
            val savedMode = FocusMode.byName(saved.mode)
            val remaining = saved.currentRemaining(System.currentTimeMillis())
            if (saved.running && remaining <= 0) {
                // 离开期间计时已自然结束，计为完成
                repository.addRecord(savedMode, savedMode.minutes, finished = true)
                repository.saveTimer(null)
                showCompleted = true
            } else {
                mode = savedMode
                secondsLeft = remaining
                running = saved.running
            }
        }
    }

    fun persistTimer(isRunning: Boolean, remaining: Int, currentMode: FocusMode) {
        scope.launch {
            repository.saveTimer(
                FocusTimerState(
                    mode = currentMode.name,
                    remainingSeconds = remaining,
                    running = isRunning,
                    savedAtEpochMillis = System.currentTimeMillis(),
                ),
            )
        }
    }

    fun finishSession(completed: Boolean) {
        val elapsedSeconds = mode.totalSeconds - secondsLeft
        val actualMinutes = if (completed) mode.minutes else elapsedSeconds / 60
        if (completed || actualMinutes > 0) {
            scope.launch { repository.addRecord(mode, actualMinutes, finished = completed) }
        }
        scope.launch { repository.saveTimer(null) }
        running = false
        secondsLeft = mode.totalSeconds
        if (completed) showCompleted = true
    }

    LaunchedEffect(running) {
        while (running && secondsLeft > 0) {
            delay(1000)
            secondsLeft--
            // 每 10 秒持久化一次，异常退出也能恢复
            if (secondsLeft % 10 == 0) persistTimer(true, secondsLeft, mode)
            if (secondsLeft <= 0) finishSession(completed = true)
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            if (secondsLeft != mode.totalSeconds || running) {
                persistTimer(running, secondsLeft, mode)
            }
        }
    }

    val minutes = (secondsLeft / 60).toString().padStart(2, '0')
    val secs = (secondsLeft % 60).toString().padStart(2, '0')
    val progress = secondsLeft.toFloat() / mode.totalSeconds.toFloat()
    val statusText = when {
        running && mode == FocusMode.FOCUS -> CampusStrings.Focus.STATUS_RUNNING
        running -> CampusStrings.Focus.STATUS_BREAK
        secondsLeft != mode.totalSeconds -> CampusStrings.Focus.STATUS_PAUSED
        else -> CampusStrings.Focus.STATUS_READY
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = PaddingValues(
            top = 12.dp,
            bottom = WindowInsets.navigationBars.asPaddingValues()
                .calculateBottomPadding() + BottomDockReservedHeight + 16.dp,
        ),
    ) {
        item {
            CampusPageHeader(
                title = CampusStrings.Focus.TITLE,
                subtitle = CampusStrings.Focus.SUBTITLE,
                onBack = onBack,
            )
        }

        item {
            CampusCard(
                modifier = Modifier.enterAnimation(enabled = !reduceMotion),
                padding = PaddingValues(20.dp),
            ) {
                FilterChipRow(
                    options = listOf(
                        CampusStrings.Focus.MODE_FOCUS,
                        CampusStrings.Focus.MODE_SHORT,
                        CampusStrings.Focus.MODE_LONG,
                    ),
                    selected = when (mode) {
                        FocusMode.FOCUS -> CampusStrings.Focus.MODE_FOCUS
                        FocusMode.SHORT_BREAK -> CampusStrings.Focus.MODE_SHORT
                        FocusMode.LONG_BREAK -> CampusStrings.Focus.MODE_LONG
                    },
                    onSelect = { label ->
                        if (!running) {
                            val next = when (label) {
                                CampusStrings.Focus.MODE_SHORT -> FocusMode.SHORT_BREAK
                                CampusStrings.Focus.MODE_LONG -> FocusMode.LONG_BREAK
                                else -> FocusMode.FOCUS
                            }
                            mode = next
                            secondsLeft = next.totalSeconds
                            scope.launch { repository.saveTimer(null) }
                        }
                    },
                )
                Spacer(Modifier.height(18.dp))
                Box(
                    modifier = Modifier.fillMaxWidth(),
                    contentAlignment = Alignment.Center,
                ) {
                    Box(contentAlignment = Alignment.Center, modifier = Modifier.size(190.dp)) {
                        AnimatedCircularProgress(
                            targetProgress = progress,
                            color = if (running) Primary else Primary.copy(alpha = .55f),
                            trackColor = PrimarySoft,
                            strokeWidth = 10.dp,
                            modifier = Modifier.fillMaxSize(),
                        )
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                "$minutes:$secs",
                                fontSize = 46.sp,
                                fontWeight = FontWeight.Bold,
                                color = Primary,
                                letterSpacing = 2.sp,
                            )
                            Text(statusText, color = Muted, fontSize = 11.sp)
                        }
                    }
                }
                Spacer(Modifier.height(18.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp, Alignment.CenterHorizontally),
                ) {
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(12.dp))
                            .background(Primary)
                            .campusClickable {
                                if (running) {
                                    running = false
                                    persistTimer(false, secondsLeft, mode)
                                } else {
                                    running = true
                                    persistTimer(true, secondsLeft, mode)
                                }
                            }
                            .padding(horizontal = 26.dp, vertical = 12.dp),
                    ) {
                        Text(
                            if (running) CampusStrings.Focus.PAUSE
                            else if (secondsLeft != mode.totalSeconds) CampusStrings.Focus.RESUME
                            else CampusStrings.Focus.START,
                            color = Color.White,
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 14.sp,
                        )
                    }
                    if (secondsLeft != mode.totalSeconds) {
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(12.dp))
                                .background(PrimarySoft)
                                .campusClickable { showEndConfirm = true }
                                .padding(horizontal = 26.dp, vertical = 12.dp),
                        ) {
                            Text(
                                CampusStrings.Focus.END,
                                color = Primary,
                                fontWeight = FontWeight.SemiBold,
                                fontSize = 14.sp,
                            )
                        }
                    }
                }
            }
        }

        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                StatCard(
                    modifier = Modifier.weight(1f),
                    icon = Icons.Default.Timer,
                    value = "${stats.todayMinutes}",
                    unit = CampusStrings.Focus.MINUTES_UNIT,
                    label = CampusStrings.Focus.STATS_TODAY,
                )
                StatCard(
                    modifier = Modifier.weight(1f),
                    icon = Icons.Default.SelfImprovement,
                    value = "${stats.todayCount}",
                    unit = CampusStrings.Focus.TIMES_UNIT,
                    label = CampusStrings.Focus.STATS_COUNT,
                )
                StatCard(
                    modifier = Modifier.weight(1f),
                    icon = Icons.Default.LocalFireDepartment,
                    value = "${stats.streakDays}",
                    unit = CampusStrings.Focus.DAYS_UNIT,
                    label = CampusStrings.Focus.STATS_STREAK,
                )
            }
        }

        item {
            CampusCard {
                Text(CampusStrings.Focus.GOAL_TITLE, color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(4.dp))
                Text(
                    CampusStrings.Focus.GOAL_FORMAT.format(stats.goalMinutes),
                    color = Muted,
                    fontSize = 11.5.sp,
                )
                Spacer(Modifier.height(10.dp))
                FilterChipRow(
                    options = listOf("30", "60", "90", "120"),
                    selected = stats.goalMinutes.toString(),
                    onSelect = { scope.launch { repository.setGoal(it.toInt()) } },
                )
                Spacer(Modifier.height(12.dp))
                val goalProgress = (stats.todayMinutes.toFloat() / stats.goalMinutes).coerceIn(0f, 1f)
                Box(
                    Modifier
                        .fillMaxWidth()
                        .height(8.dp)
                        .clip(CircleShape)
                        .background(PrimarySoft),
                ) {
                    Box(
                        Modifier
                            .fillMaxWidth(goalProgress)
                            .height(8.dp)
                            .clip(CircleShape)
                            .background(Primary),
                    )
                }
            }
        }

        item {
            CampusCard(
                modifier = Modifier.campusClickable {
                    onOpenCounselorPlan(CampusStrings.Focus.PLAN_PROMPT)
                },
                padding = PaddingValues(14.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(38.dp)
                            .clip(RoundedCornerShape(11.dp))
                            .background(PrimarySoft),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(Icons.Default.AutoAwesome, null, tint = Primary, modifier = Modifier.size(20.dp))
                    }
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(CampusStrings.Focus.PLAN_ENTRY, color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                        Text("由 AI 导员结合你的课程与待办生成", color = Muted, fontSize = 11.sp)
                    }
                }
            }
        }

        item {
            Text(CampusStrings.Focus.RECORDS_TITLE, color = TextPrimary, fontSize = 15.sp, fontWeight = FontWeight.Bold)
        }
        if (records.isEmpty()) {
            item { EmptyState(Icons.Default.Timer, CampusStrings.Focus.RECORDS_EMPTY) }
        } else {
            items(records.take(10), key = { it.id }) { record ->
                CampusCard(padding = PaddingValues(13.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(
                                FocusMode.byName(record.mode).label + " · " + record.date,
                                color = TextPrimary,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.SemiBold,
                            )
                            Spacer(Modifier.height(3.dp))
                            Text(
                                "${record.actualMinutes}/${record.plannedMinutes} ${CampusStrings.Focus.MINUTES_UNIT} · ${record.endedAt}",
                                color = Muted,
                                fontSize = 11.sp,
                            )
                        }
                        StatusTag(
                            text = if (record.finished) CampusStrings.Focus.FINISHED_TAG else CampusStrings.Focus.UNFINISHED_TAG,
                            tone = if (record.finished) StatusTone.SUCCESS else StatusTone.NEUTRAL,
                        )
                    }
                }
            }
        }
    }

    if (showEndConfirm) {
        ConfirmDialog(
            title = CampusStrings.Focus.END_TITLE,
            message = CampusStrings.Focus.END_MESSAGE,
            confirmText = CampusStrings.Focus.END,
            danger = true,
            onConfirm = {
                showEndConfirm = false
                finishSession(completed = false)
            },
            onDismiss = { showEndConfirm = false },
        )
    }

    if (showCompleted) {
        AlertDialog(
            onDismissRequest = { showCompleted = false },
            title = { Text(CampusStrings.Focus.COMPLETED_TITLE, fontWeight = FontWeight.Bold) },
            text = { Text(CampusStrings.Focus.COMPLETED_MESSAGE, color = Muted) },
            confirmButton = {
                TextButton(onClick = { showCompleted = false }) {
                    Text(CampusStrings.Common.CONFIRM, color = Primary, fontWeight = FontWeight.SemiBold)
                }
            },
            containerColor = Surface,
            shape = RoundedCornerShape(20.dp),
        )
    }
}

@Composable
private fun StatCard(
    modifier: Modifier,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    value: String,
    unit: String,
    label: String,
) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(16.dp))
            .background(Surface)
            .padding(vertical = 13.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(icon, null, tint = Primary, modifier = Modifier.size(18.dp))
        Spacer(Modifier.height(7.dp))
        Row(verticalAlignment = Alignment.Bottom) {
            Text(value, color = TextPrimary, fontSize = 19.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.width(2.dp))
            Text(unit, color = Muted, fontSize = 10.sp, modifier = Modifier.padding(bottom = 2.dp))
        }
        Text(label, color = Muted, fontSize = 10.5.sp)
    }
}

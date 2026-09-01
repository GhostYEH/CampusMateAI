package com.example.campusai.ui.screens.dashboard.gamified

import com.example.campusai.ui.components.GlassTextButton

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.automirrored.filled.Assignment
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Event
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.LocalFireDepartment
import androidx.compose.material.icons.filled.MeetingRoom
import androidx.compose.material.icons.filled.MilitaryTech
import androidx.compose.material.icons.filled.School
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Stars
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.GamificationTokens
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary

@Composable
internal fun MainQuestSection(
    quests: List<MainQuestUiState>,
    emptyMessage: String?,
    reduceMotion: Boolean,
    onNavigate: (String) -> Unit,
) {
    DashboardPanel {
        SectionHeader("MAIN QUEST", "今日主线", Icons.AutoMirrored.Filled.Assignment)
        Spacer(Modifier.height(12.dp))
        Crossfade(
            targetState = quests to emptyMessage,
            animationSpec = if (reduceMotion) snap() else tween(240),
            label = "main-quest-state",
        ) { (visibleQuests, visibleEmptyMessage) ->
            Column {
                if (visibleQuests.isEmpty()) {
                    EmptyState(visibleEmptyMessage ?: "暂无主线", Icons.AutoMirrored.Filled.Assignment) { onNavigate("tasks") }
                } else {
                    visibleQuests.forEachIndexed { index, quest ->
                        QuestCard(quest, onNavigate)
                        if (index != visibleQuests.lastIndex) Spacer(Modifier.height(9.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun QuestCard(quest: MainQuestUiState, onNavigate: (String) -> Unit) {
    val accent = when (quest.route) {
        "exams" -> GamificationTokens.Purple
        "tasks" -> GamificationTokens.XpAmber
        else -> GamificationTokens.CampusBlue
    }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(18.dp))
            .background(if (quest.primary) accent.copy(alpha = .1f) else Background)
            .border(1.dp, if (quest.primary) accent.copy(alpha = .28f) else Line, RoundedCornerShape(18.dp))
            .campusClickable { onNavigate(quest.route) }
            .padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(42.dp).clip(RoundedCornerShape(13.dp)).background(accent.copy(alpha = .14f)), contentAlignment = Alignment.Center) {
            Icon(if (quest.route == "exams") Icons.Default.Event else if (quest.route == "courses") Icons.Default.School else Icons.AutoMirrored.Filled.Assignment, null, tint = accent)
        }
        Column(Modifier.padding(start = 12.dp).weight(1f)) {
            Text(quest.eyebrow, color = accent, fontSize = 8.5.sp, fontWeight = FontWeight.Bold, letterSpacing = .8.sp)
            Text(quest.title, color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(listOf(quest.meta, quest.detail).filter(String::isNotBlank).joinToString(" · "), color = Muted, fontSize = 10.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        Column(horizontalAlignment = Alignment.End) {
            Text(quest.status, color = Muted, fontSize = 9.sp)
            if (quest.rewardXp > 0) Text("+${quest.rewardXp} XP", color = GamificationTokens.XpAmber, fontSize = 10.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
internal fun SideQuestSection(
    quests: List<SideQuestUiState>,
    columns: Int,
    onNavigate: (String) -> Unit,
) {
    DashboardPanel {
        SectionHeader("SIDE QUESTS", "校园探索", Icons.Default.Search)
        Spacer(Modifier.height(12.dp))
        quests.chunked(columns).forEachIndexed { rowIndex, rowQuests ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                rowQuests.forEach { quest ->
                    SideQuestCard(quest, Modifier.weight(1f), onNavigate)
                }
                repeat(columns - rowQuests.size) { Spacer(Modifier.weight(1f)) }
            }
            if (rowIndex != (quests.size - 1) / columns) Spacer(Modifier.height(9.dp))
        }
    }
}

@Composable
private fun SideQuestCard(quest: SideQuestUiState, modifier: Modifier, onNavigate: (String) -> Unit) {
    val (icon, tone) = sideQuestVisual(quest.route)
    Column(
        modifier = modifier
            .height(118.dp)
            .clip(RoundedCornerShape(18.dp))
            .background(Background)
            .campusClickable { onNavigate(quest.route) }
            .padding(12.dp),
    ) {
        Box(Modifier.size(35.dp).clip(RoundedCornerShape(11.dp)).background(tone.copy(alpha = .14f)), contentAlignment = Alignment.Center) {
            Icon(icon, null, tint = tone, modifier = Modifier.size(20.dp))
        }
        Spacer(Modifier.weight(1f))
        Text(quest.title, color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.Bold, maxLines = 1)
        Text(quest.description, color = Muted, fontSize = 9.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
    }
}

private fun sideQuestVisual(route: String): Pair<ImageVector, Color> = when (route) {
    "focus" -> Icons.Default.Timer to GamificationTokens.XpAmber
    "counselor" -> Icons.Default.AutoAwesome to GamificationTokens.Purple
    "classrooms" -> Icons.Default.MeetingRoom to GamificationTokens.Sky
    "services" -> Icons.AutoMirrored.Filled.Assignment to GamificationTokens.CampusBlue
    "lostfound" -> Icons.Default.Search to GamificationTokens.SuccessGreen
    else -> Icons.Default.Event to GamificationTokens.Indigo
}

@Composable
internal fun GrowthSection(growth: GrowthUiState, columns: Int) {
    DashboardPanel {
        SectionHeader("GROWTH", "成长总览", Icons.Default.LocalFireDepartment)
        Spacer(Modifier.height(12.dp))
        val metrics = listOf(
            GrowthMetric("本周 XP", "+${growth.weekXp}", GamificationTokens.XpAmber),
            GrowthMetric("专注时间", "${growth.weekFocusMinutes} min", GamificationTokens.CampusBlue),
            GrowthMetric("任务完成", "${growth.weekCompletedTasks} Tasks", GamificationTokens.SuccessGreen),
            GrowthMetric("连续天数", "${growth.streakDays} Days", GamificationTokens.Purple),
        )
        metrics.chunked(columns).forEachIndexed { rowIndex, row ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                row.forEach { metric -> GrowthMetricCard(metric, Modifier.weight(1f)) }
                repeat(columns - row.size) { Spacer(Modifier.weight(1f)) }
            }
            if (rowIndex != (metrics.size - 1) / columns) Spacer(Modifier.height(8.dp))
        }
    }
}

private data class GrowthMetric(val label: String, val value: String, val color: Color)

@Composable
private fun GrowthMetricCard(metric: GrowthMetric, modifier: Modifier) {
    Column(modifier.clip(RoundedCornerShape(16.dp)).background(Background).padding(12.dp)) {
        Box(Modifier.size(7.dp).clip(CircleShape).background(metric.color))
        Spacer(Modifier.height(9.dp))
        Text(metric.value, color = TextPrimary, fontSize = 15.sp, fontWeight = FontWeight.Bold, maxLines = 1)
        Text(metric.label, color = Muted, fontSize = 9.sp, maxLines = 1)
    }
}

@Composable
internal fun AchievementSection(
    achievements: List<AchievementUiState>,
    reduceMotion: Boolean,
    onSelect: (AchievementUiState) -> Unit,
) {
    DashboardPanel {
        SectionHeader("ACHIEVEMENTS", "最近成就", Icons.Default.MilitaryTech)
        Spacer(Modifier.height(12.dp))
        achievements.take(3).forEachIndexed { index, achievement ->
            val progress by animateFloatAsState(
                targetValue = (achievement.current.toFloat() / achievement.target.coerceAtLeast(1)).coerceIn(0f, 1f),
                animationSpec = if (reduceMotion) snap() else tween(600),
                label = "achievement-${achievement.id}",
            )
            Row(
                Modifier.fillMaxWidth().campusClickable { onSelect(achievement) }.padding(vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(
                    Modifier.size(44.dp).clip(CircleShape).background(if (achievement.unlocked) GamificationTokens.XpAmber.copy(alpha = .18f) else Background),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(if (achievement.unlocked) Icons.Default.MilitaryTech else Icons.Default.Stars, null, tint = if (achievement.unlocked) GamificationTokens.XpAmber else Muted)
                }
                Column(Modifier.padding(start = 12.dp).weight(1f)) {
                    Row {
                        Text(achievement.title, color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                        if (reduceMotion) {
                            if (achievement.unlocked) {
                                Icon(Icons.Default.CheckCircle, null, tint = GamificationTokens.SuccessGreen, modifier = Modifier.padding(start = 5.dp).size(15.dp))
                            }
                        } else {
                            AnimatedVisibility(achievement.unlocked) {
                                Icon(Icons.Default.CheckCircle, null, tint = GamificationTokens.SuccessGreen, modifier = Modifier.padding(start = 5.dp).size(15.dp))
                            }
                        }
                    }
                    Text(achievement.description, color = Muted, fontSize = 9.5.sp, maxLines = 1)
                    Spacer(Modifier.height(5.dp))
                    LinearProgressIndicator(
                        progress = { progress },
                        modifier = Modifier.fillMaxWidth().height(4.dp).clip(CircleShape),
                        color = if (achievement.unlocked) GamificationTokens.SuccessGreen else GamificationTokens.CampusBlue,
                        trackColor = Line,
                    )
                }
                Text(if (achievement.unlocked) "已解锁" else "${achievement.current}/${achievement.target}", color = if (achievement.unlocked) GamificationTokens.SuccessGreen else Muted, fontSize = 9.sp)
            }
            if (index != achievements.take(3).lastIndex) HorizontalDivider(color = Line, modifier = Modifier.padding(start = 56.dp))
        }
    }
}

@Composable
internal fun AchievementDialog(achievement: AchievementUiState, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = { Icon(Icons.Default.MilitaryTech, null, tint = if (achievement.unlocked) GamificationTokens.XpAmber else Muted, modifier = Modifier.size(42.dp)) },
        title = { Text(achievement.title) },
        text = {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(achievement.description)
                Spacer(Modifier.height(10.dp))
                Text(if (achievement.unlocked) "已于 ${achievement.unlockedAtLabel} 解锁" else "进度 ${achievement.current}/${achievement.target} ${achievement.unit}", color = Muted, fontSize = 12.sp)
            }
        },
        confirmButton = { GlassTextButton(onClick = onDismiss) { Text("知道了") } },
    )
}

@Composable
internal fun CampusWorldSection(items: List<CampusWorldUiState>, onNavigate: (String) -> Unit) {
    DashboardPanel {
        SectionHeader("CAMPUS WORLD", "校园世界", Icons.Default.Groups)
        Spacer(Modifier.height(10.dp))
        if (items.isEmpty()) {
            EmptyState("校园世界暂时安静", Icons.Default.Groups) { onNavigate("community") }
        } else {
            items.forEachIndexed { index, item ->
                Row(
                    Modifier.fillMaxWidth().campusClickable { onNavigate(item.route) }.padding(vertical = 9.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(Modifier.size(35.dp).clip(RoundedCornerShape(11.dp)).background(GamificationTokens.CampusBlue.copy(alpha = .1f)), contentAlignment = Alignment.Center) {
                        Text("#", color = GamificationTokens.CampusBlue, fontWeight = FontWeight.Bold)
                    }
                    Column(Modifier.padding(start = 11.dp).weight(1f)) {
                        Text(item.title, color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text(item.summary, color = Muted, fontSize = 9.5.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                    Text(item.category, color = Muted, fontSize = 8.5.sp)
                    Icon(Icons.AutoMirrored.Filled.ArrowForward, null, tint = Muted, modifier = Modifier.padding(start = 4.dp).size(15.dp))
                }
                if (index != items.lastIndex) HorizontalDivider(color = Line, modifier = Modifier.padding(start = 46.dp))
            }
        }
    }
}

@Composable
internal fun DashboardStatus(messages: List<String>, isLoading: Boolean) {
    if (isLoading) {
        Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Surface).padding(13.dp), verticalAlignment = Alignment.CenterVertically) {
            CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp, color = GamificationTokens.CampusBlue)
            Text(" 正在同步校园成长数据…", color = Muted, fontSize = 10.5.sp)
        }
    }
    messages.forEach { message ->
        Text(message, color = Muted, fontSize = 10.sp, modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(Surface).padding(12.dp))
    }
}

@Composable
private fun DashboardPanel(content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).background(Surface).padding(16.dp), content = content)
}

@Composable
private fun SectionHeader(eyebrow: String, title: String, icon: ImageVector) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(eyebrow, color = GamificationTokens.CampusBlue, fontSize = 8.5.sp, fontWeight = FontWeight.Bold, letterSpacing = .9.sp)
            Text(title, color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.Bold)
        }
        Icon(icon, null, tint = GamificationTokens.CampusBlue, modifier = Modifier.size(23.dp))
    }
}

@Composable
private fun EmptyState(message: String, icon: ImageVector, onAction: () -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(17.dp)).background(Background).campusClickable(onClick = onAction).padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = Muted, modifier = Modifier.size(24.dp))
        Text(message, color = Muted, fontSize = 11.sp, modifier = Modifier.padding(start = 10.dp).weight(1f))
        Icon(Icons.AutoMirrored.Filled.ArrowForward, null, tint = Muted, modifier = Modifier.size(17.dp))
    }
}

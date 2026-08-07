package com.example.campusai.ui.screens.dashboard

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
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountBalance
import androidx.compose.material.icons.filled.ArrowForward
import androidx.compose.material.icons.filled.AutoStories
import androidx.compose.material.icons.filled.BarChart
import androidx.compose.material.icons.filled.Campaign
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.EventNote
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FindInPage
import androidx.compose.material.icons.filled.Grade
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.MeetingRoom
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.School
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.R
import com.example.campusai.data.model.Task
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.AnimatedCircularProgress
import com.example.campusai.ui.components.AnimatedPercent
import com.example.campusai.ui.components.breathingFloat
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.screens.profile.ReferenceAvatar
import com.example.campusai.ui.theme.Accent
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.DangerText
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Success
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.launch

private val HeroBlue = Color(0xFF5368E8)
private val HeroBlueDeep = Color(0xFF3449C7)
private val HeroMist = Color(0xFFDCE5FF)
private val WarmOrange = Color(0xFFFFA43A)

@Composable
fun DashboardScreen(
    repository: AppRepository,
    onNavigate: (String) -> Unit,
) {
    val session by repository.session.collectAsState()
    val tasks by repository.tasks.collectAsState()
    val campusNews by repository.campusNews.collectAsState()
    val reduceMotion by repository.reduceMotion.collectAsState()

    // 首页加载时尝试从后端拉取最新数据（通知 / 动态 / 课程 / 任务）
    androidx.compose.runtime.LaunchedEffect(Unit) {
        repository.refreshNotices()
        repository.refreshCampusNews()
        repository.refreshCourses()
        repository.refreshTasks()
    }
    val floatingDockScrollPadding =
        WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + 92.dp

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .statusBarsPadding(),
        contentPadding = PaddingValues(
            start = 16.dp,
            top = 12.dp,
            end = 16.dp,
            bottom = floatingDockScrollPadding,
        ),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .campusClickable { onNavigate("profile") },
                verticalAlignment = Alignment.CenterVertically,
            ) {
                ReferenceAvatar(size = 42.dp)
                Column(Modifier.padding(start = 10.dp)) {
                    Text(
                        session?.name ?: "林知夏",
                        color = TextPrimary,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        "点击头像进入个人中心",
                        color = Muted,
                        fontSize = 11.sp,
                    )
                }
            }
        }
        item { ExamHero(onNavigate, reduceMotion) }
        item { QuickActions(onNavigate, reduceMotion) }
        item { TodayCourseCard(onNavigate, reduceMotion) }
        item { OverviewAndDeadlines(tasks, onNavigate, reduceMotion) }
        item { CampusUpdates(campusNews, onNavigate, reduceMotion) }
    }
}

@Composable
private fun ExamHero(onNavigate: (String) -> Unit, reduceMotion: Boolean) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(188.dp)
            .clip(RoundedCornerShape(26.dp))
            .background(HeroBlue)
            .campusClickable { onNavigate("tasks") }
            .enterAnimation(enabled = !reduceMotion)
            .breathingFloat(enabled = !reduceMotion, amplitude = 3f, periodMs = 4000),
    ) {
        Image(
            painter = painterResource(R.drawable.campus_login_poster),
            contentDescription = null,
            contentScale = ContentScale.Crop,
            alignment = Alignment.Center,
            modifier = Modifier.fillMaxSize(),
        )
        Box(
            Modifier.fillMaxSize().background(
                Brush.horizontalGradient(
                    0f to HeroBlueDeep.copy(alpha = .97f),
                    .55f to HeroBlue.copy(alpha = .82f),
                    1f to HeroBlue.copy(alpha = .18f),
                ),
            ),
        )
        Column(
            modifier = Modifier
                .fillMaxHeight()
                .fillMaxWidth(.72f)
                .padding(horizontal = 22.dp, vertical = 20.dp),
            verticalArrangement = Arrangement.Center,
        ) {
            Text(
                "期末考试周进行中",
                color = Color.White,
                fontSize = 23.sp,
                lineHeight = 28.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = (-.4).sp,
            )
            Spacer(Modifier.height(7.dp))
            Text("合理规划时间，稳住节奏，我们能赢。", color = HeroMist, fontSize = 12.sp)
            Spacer(Modifier.height(19.dp))
            Row(
                modifier = Modifier
                    .border(1.dp, Color.White.copy(alpha = .72f), CircleShape)
                    .padding(horizontal = 15.dp, vertical = 9.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("查看复习计划", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.width(7.dp))
                Icon(Icons.Default.ArrowForward, null, tint = Color.White, modifier = Modifier.size(15.dp))
            }
        }
        Row(
            modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            repeat(4) { index ->
                Box(
                    Modifier
                        .size(if (index == 0) 7.dp else 6.dp)
                        .clip(CircleShape)
                        .background(Color.White.copy(alpha = if (index == 0) 1f else .42f)),
                )
            }
        }
    }
}

private data class QuickAction(
    val title: String,
    val route: String,
    val icon: androidx.compose.ui.graphics.vector.ImageVector,
    val color: Color,
)

@Composable
private fun QuickActions(
    onNavigate: (String) -> Unit,
    reduceMotion: Boolean,
) {
    // 与底部导航不重复的五个校园服务入口
    val actions = listOf(
        QuickAction("考试安排", "exams", Icons.Default.EventNote, Color(0xFF5B68F2)),
        QuickAction("空教室", "classrooms", Icons.Default.MeetingRoom, Color(0xFF397CEF)),
        QuickAction("办事大厅", "services", Icons.Default.AccountBalance, Color(0xFF35B99A)),
        QuickAction("专注自习", "focus", Icons.Default.Timer, WarmOrange),
        QuickAction("失物招领", "lostfound", Icons.Default.FindInPage, Color(0xFF7C6BE8)),
    )
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Surface, RoundedCornerShape(24.dp))
            .padding(horizontal = 8.dp, vertical = 16.dp)
            .enterAnimation(delayMs = 70, enabled = !reduceMotion),
    ) {
        actions.forEach { action ->
            Column(
                modifier = Modifier
                    .weight(1f)
                    .campusClickable { onNavigate(action.route) },
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Box(
                    modifier = Modifier.size(44.dp).clip(RoundedCornerShape(13.dp)).background(action.color),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(action.icon, action.title, tint = Color.White, modifier = Modifier.size(24.dp))
                }
                Spacer(Modifier.height(8.dp))
                Text(action.title, color = TextPrimary, fontSize = 11.sp, maxLines = 1)
            }
        }
    }
}

@Composable
private fun TodayCourseCard(onNavigate: (String) -> Unit, reduceMotion: Boolean) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(Surface, RoundedCornerShape(24.dp))
            .padding(16.dp)
            .enterAnimation(delayMs = 120, enabled = !reduceMotion),
    ) {
        SectionTitle("今日课程", "查看全部") { onNavigate("courses") }
        Spacer(Modifier.height(13.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Column(
                modifier = Modifier
                    .weight(1.02f)
                    .height(166.dp)
                    .clip(RoundedCornerShape(18.dp))
                    .background(
                        Brush.linearGradient(
                            listOf(Color(0xFF4259E8), Color(0xFF7B78F7)),
                        ),
                    )
                    .campusClickable { onNavigate("courses") }
                    .padding(15.dp),
            ) {
                Text(
                    "下一节",
                    color = Color.White,
                    fontSize = 10.sp,
                    modifier = Modifier
                        .background(Color.White.copy(alpha = .16f), CircleShape)
                        .padding(horizontal = 9.dp, vertical = 4.dp),
                )
                Spacer(Modifier.height(10.dp))
                Text("数据结构", color = Color.White, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.weight(1f))
                CourseMeta(Icons.Default.Schedule, "10:00 · 进行中")
                Spacer(Modifier.height(8.dp))
                CourseMeta(Icons.Default.LocationOn, "C-202 · 李老师")
            }
            Column(
                modifier = Modifier
                    .weight(.98f)
                    .height(166.dp)
                    .border(1.dp, Line, RoundedCornerShape(18.dp))
                    .padding(horizontal = 12.dp),
                verticalArrangement = Arrangement.Center,
            ) {
                CourseTimeline("高等数学", "08:00 · B-301", "已结束", false)
                Box(Modifier.fillMaxWidth().height(1.dp).background(Line))
                CourseTimeline("计算机网络", "14:00 · A-105", "未开始", true)
            }
        }
    }
}

@Composable
private fun CourseMeta(icon: androidx.compose.ui.graphics.vector.ImageVector, text: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = Color.White.copy(alpha = .88f), modifier = Modifier.size(15.dp))
        Spacer(Modifier.width(5.dp))
        Text(text, color = Color.White.copy(alpha = .9f), fontSize = 11.sp)
    }
}

@Composable
private fun CourseTimeline(title: String, meta: String, state: String, upcoming: Boolean) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier.size(9.dp).clip(CircleShape)
                .background(if (upcoming) HeroBlue else Color.White)
                .border(1.5.dp, HeroBlue, CircleShape),
        )
        Spacer(Modifier.width(9.dp))
        Column(Modifier.weight(1f)) {
            Text(title, color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(4.dp))
            Text(meta, color = Muted, fontSize = 9.5.sp)
        }
        Text(
            state,
            color = if (upcoming) HeroBlue else Muted,
            fontSize = 9.sp,
            modifier = Modifier.background(PrimarySoft, CircleShape).padding(horizontal = 7.dp, vertical = 5.dp),
        )
    }
}

@Composable
private fun OverviewAndDeadlines(
    tasks: List<Task>,
    onNavigate: (String) -> Unit,
    reduceMotion: Boolean,
) {
    Row(
        modifier = Modifier.fillMaxWidth().enterAnimation(delayMs = 170, enabled = !reduceMotion),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Column(
            modifier = Modifier
                .weight(.88f)
                .height(191.dp)
                .background(Surface, RoundedCornerShape(22.dp))
                .padding(15.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("学习总览", color = TextPrimary, fontSize = 17.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.weight(1f))
                Icon(Icons.Default.Visibility, null, tint = Muted, modifier = Modifier.size(19.dp))
            }
            Spacer(Modifier.height(12.dp))
            Row(
                modifier = Modifier.fillMaxWidth().weight(1f).background(Background, RoundedCornerShape(16.dp)).padding(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text("本周进度", color = Muted, fontSize = 10.sp)
                    AnimatedPercent(target = 72, color = TextPrimary, fontSize = 28.sp)
                    Text("较上周 ↑12%", color = Success, fontSize = 10.sp)
                }
                Box(contentAlignment = Alignment.Center, modifier = Modifier.size(65.dp)) {
                    AnimatedCircularProgress(
                        targetProgress = 0.72f,
                        delayMs = 400,
                        color = HeroBlue,
                        trackColor = PrimarySoft,
                        strokeWidth = 7.dp,
                        modifier = Modifier.fillMaxSize(),
                    )
                    Icon(Icons.Default.BarChart, null, tint = HeroBlue, modifier = Modifier.size(22.dp))
                }
            }
        }
        Column(
            modifier = Modifier
                .weight(1.12f)
                .height(191.dp)
                .background(Surface, RoundedCornerShape(22.dp))
                .padding(15.dp),
        ) {
            SectionTitle("近期截止", "更多") { onNavigate("tasks") }
            Spacer(Modifier.height(9.dp))
            tasks.filterNot { it.done }.take(2).forEachIndexed { index, task ->
                DeadlineRow(task, index == 0, onToggle = {})
                if (index == 0) Spacer(Modifier.height(7.dp))
            }
        }
    }
}

@Composable
private fun DeadlineRow(task: Task, urgent: Boolean, onToggle: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Background, RoundedCornerShape(12.dp))
            .campusClickable(onClick = onToggle)
            .padding(horizontal = 9.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier.size(28.dp).clip(RoundedCornerShape(8.dp))
                .background(if (urgent) PrimarySoft else Accent.copy(alpha = .16f)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                Icons.Default.AutoStories,
                null,
                tint = if (urgent) Primary else WarmOrange,
                modifier = Modifier.size(17.dp),
            )
        }
        Spacer(Modifier.width(8.dp))
        Column(Modifier.weight(1f)) {
            Text(task.title, color = TextPrimary, fontSize = 10.5.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(task.due, color = if (urgent) DangerText else WarmOrange, fontSize = 9.5.sp, fontWeight = FontWeight.SemiBold)
        }
    }
}

@Composable
private fun CampusUpdates(
    items: List<com.example.campusai.data.model.CampusNews>,
    onNavigate: (String) -> Unit,
    reduceMotion: Boolean,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(Surface, RoundedCornerShape(24.dp))
            .padding(16.dp)
            .enterAnimation(delayMs = 220, enabled = !reduceMotion),
    ) {
        SectionTitle("校园动态", "查看更多") { onNavigate("notifications") }
        Spacer(Modifier.height(12.dp))
        LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            items(items, key = { it.id }) { item ->
                Column(
                    modifier = Modifier
                        .width(236.dp)
                        .border(1.dp, Line, RoundedCornerShape(16.dp))
                        .clip(RoundedCornerShape(16.dp))
                        .campusClickable { onNavigate("campus-news-detail/${item.id}") },
                ) {
                    Box(Modifier.fillMaxWidth().height(76.dp)) {
                        Image(
                            painter = painterResource(R.drawable.campus_login_poster),
                            contentDescription = null,
                            contentScale = ContentScale.Crop,
                            modifier = Modifier.fillMaxSize(),
                        )
                        val overlayColor = when {
                            item.category.contains("学习") -> HeroBlue.copy(alpha = .62f)
                            item.category.contains("创新") || item.category.contains("比赛") -> WarmOrange.copy(alpha = .55f)
                            item.category.contains("心理") || item.category.contains("活动") -> Color(0xFF8B5CF6).copy(alpha = .55f)
                            else -> Success.copy(alpha = .55f)
                        }
                        Box(Modifier.fillMaxSize().background(overlayColor))
                        val icon = when {
                            item.category.contains("学习") -> Icons.Default.School
                            item.category.contains("创新") || item.category.contains("比赛") -> Icons.Default.Campaign
                            item.category.contains("心理") -> Icons.Default.Favorite
                            else -> Icons.Default.Notifications
                        }
                        Icon(
                            icon,
                            null,
                            tint = Color.White,
                            modifier = Modifier.align(Alignment.Center).size(28.dp),
                        )
                    }
                    Column(Modifier.padding(11.dp)) {
                        Text(item.title, color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                        Text(item.summary, color = Muted, fontSize = 10.sp, maxLines = 1)
                    }
                }
            }
        }
    }
}

@Composable
private fun SectionTitle(title: String, action: String, onAction: () -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(title, color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.weight(1f))
        Row(Modifier.campusClickable(onClick = onAction), verticalAlignment = Alignment.CenterVertically) {
            Text(action, color = Muted, fontSize = 10.5.sp)
            Icon(Icons.Default.ChevronRight, null, tint = Muted, modifier = Modifier.size(16.dp))
        }
    }
}

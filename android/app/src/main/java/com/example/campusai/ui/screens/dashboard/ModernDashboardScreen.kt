package com.example.campusai.ui.screens.dashboard

import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowForward
import androidx.compose.material.icons.filled.EventNote
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import androidx.compose.ui.layout.ContentScale
import com.example.campusai.data.model.Course
import com.example.campusai.data.model.HomeBanner
import com.example.campusai.data.model.Task
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.screens.shell.floatingDockContentBottomPadding
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary

private val Ink = Color(0xFF10243A)
private val Sky = Color(0xFF4369E8)
private val Mint = Color(0xFFB8F0DB)

private data class HomeShortcut(val title: String, val route: String, val icon: ImageVector)

private val shortcuts = listOf(
    HomeShortcut("整理通知", "notifications", Icons.Default.Notifications),
    HomeShortcut("安排待办", "tasks", Icons.Default.EventNote),
    HomeShortcut("查看课程", "courses", Icons.Default.MenuBook),
)

@Composable
fun ModernDashboardScreen(repository: AppRepository, onNavigate: (String) -> Unit) {
    val session by repository.session.collectAsStateWithLifecycle()
    val tasks by repository.tasks.collectAsStateWithLifecycle()
    val courses by repository.courses.collectAsStateWithLifecycle()
    val campusNews by repository.campusNews.collectAsStateWithLifecycle()
    val banners by repository.homeBanners.collectAsStateWithLifecycle()
    val pending = tasks.filterNot(Task::done)
    val bottomPadding = floatingDockContentBottomPadding(
        WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding(),
    )

    LaunchedEffect(Unit) {
        repository.refreshNotices()
        repository.refreshCampusNews()
        repository.refreshCourses()
        repository.refreshTasks()
        repository.refreshHomeBanners()
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize().background(Background).statusBarsPadding(),
        contentPadding = PaddingValues(start = 18.dp, top = 18.dp, end = 18.dp, bottom = bottomPadding),
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        item { HomeHeading(session?.name ?: "同学", onNavigate) }
        item { FocusHero(pending.firstOrNull(), onNavigate) }
        item { HomeMetrics(courses.size, pending.size, onNavigate) }
        item { ShortcutSection(onNavigate) }
        banners.firstOrNull()?.let { banner -> item { HomeBannerCard(banner, onNavigate) } }
        item { CourseSection(courses, onNavigate) }
        item { TaskSection(pending, onNavigate) }
        if (campusNews.isNotEmpty()) {
            item {
                HomeSectionHeader("校园动态", "查看全部") { onNavigate("campus-news") }
                Spacer(Modifier.height(10.dp))
                campusNews.take(2).forEach { news ->
                    HomeListCard(news.title, news.summary, Icons.Default.Notifications) {
                        onNavigate("campus-news-detail/${news.id}")
                    }
                    Spacer(Modifier.height(8.dp))
                }
            }
        }
    }
}

@Composable
private fun HomeHeading(name: String, onNavigate: (String) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.weight(1f)) {
            Text("CAMPUSMATE  /  TODAY", color = Primary, fontSize = 11.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.4.sp)
            Spacer(Modifier.height(6.dp))
            Text("你好，$name", color = TextPrimary, fontSize = 27.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text("把今天的学习安排得刚刚好", color = Muted, fontSize = 13.sp)
        }
        Box(
            Modifier.size(46.dp).clip(CircleShape).background(PrimarySoft).clickable { onNavigate("profile") },
            contentAlignment = Alignment.Center,
        ) { Text(name.take(1), color = Primary, fontSize = 19.sp, fontWeight = FontWeight.Bold) }
    }
}

@Composable
private fun FocusHero(nextTask: Task?, onNavigate: (String) -> Unit) {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(28.dp))
            .background(Brush.linearGradient(listOf(Ink, Color(0xFF254B85), Sky)))
            .padding(22.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(8.dp).background(Mint, CircleShape))
            Spacer(Modifier.width(8.dp))
            Text("你的学习空间", color = Mint, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
        }
        Spacer(Modifier.height(18.dp))
        Text("现在，专注一件事。", color = Color.White, fontSize = 27.sp, lineHeight = 33.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(7.dp))
        Text(
            nextTask?.let { "可以先处理：${it.title}" } ?: "给自己一段不被打扰的学习时间",
            color = Color.White.copy(alpha = .78f), fontSize = 12.sp, maxLines = 2, overflow = TextOverflow.Ellipsis,
        )
        Spacer(Modifier.height(22.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(
                Modifier.clip(CircleShape).background(Mint).clickable { onNavigate("focus") }
                    .padding(horizontal = 17.dp, vertical = 11.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Icons.Default.Timer, null, tint = Ink, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(7.dp))
                Text("开始专注", color = Ink, fontSize = 13.sp, fontWeight = FontWeight.Bold)
            }
            Row(
                Modifier.clip(CircleShape).background(Color.White.copy(alpha = .13f)).clickable { onNavigate("tasks") }
                    .padding(horizontal = 16.dp, vertical = 11.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("查看待办", color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.width(4.dp))
                Icon(Icons.Default.ArrowForward, null, tint = Color.White, modifier = Modifier.size(16.dp))
            }
        }
    }
}

@Composable
private fun HomeMetrics(courseCount: Int, pendingCount: Int, onNavigate: (String) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        MetricCard("我的课程", "$courseCount 门", Icons.Default.MenuBook, Modifier.weight(1f)) { onNavigate("courses") }
        MetricCard("待办事项", "$pendingCount 项", Icons.Default.EventNote, Modifier.weight(1f)) { onNavigate("tasks") }
    }
}

@Composable
private fun MetricCard(label: String, value: String, icon: ImageVector, modifier: Modifier, onClick: () -> Unit) {
    Row(
        modifier.clip(RoundedCornerShape(20.dp)).background(Surface).clickable(onClick = onClick).padding(15.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(36.dp).clip(RoundedCornerShape(12.dp)).background(PrimarySoft), contentAlignment = Alignment.Center) {
            Icon(icon, null, tint = Primary, modifier = Modifier.size(19.dp))
        }
        Spacer(Modifier.width(10.dp))
        Column {
            Text(label, color = Muted, fontSize = 11.sp)
            Text(value, color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun ShortcutSection(onNavigate: (String) -> Unit) {
    Column {
        HomeSectionHeader("从通知到行动", "") {}
        Spacer(Modifier.height(12.dp))
        Column(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).background(Surface).padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("收集重要信息，排进待办，再开始专注。", color = Muted, fontSize = 12.sp, modifier = Modifier.padding(start = 7.dp, top = 3.dp))
            shortcuts.chunked(3).forEach { row ->
                Row(Modifier.fillMaxWidth()) {
                    row.forEach { item ->
                        Column(
                            Modifier.weight(1f).clip(RoundedCornerShape(16.dp)).clickable { onNavigate(item.route) }.padding(vertical = 8.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Box(Modifier.size(42.dp).clip(RoundedCornerShape(14.dp)).background(PrimarySoft), contentAlignment = Alignment.Center) {
                                Icon(item.icon, null, tint = Primary, modifier = Modifier.size(22.dp))
                            }
                            Spacer(Modifier.height(7.dp))
                            Text(item.title, color = TextPrimary, fontSize = 10.sp, maxLines = 1)
                        }
                    }
                    repeat(3 - row.size) { Spacer(Modifier.weight(1f)) }
                }
            }
        }
    }
}

@Composable
private fun HomeBannerCard(banner: HomeBanner, onNavigate: (String) -> Unit) {
    val destination = banner.destination
    Box(
        Modifier.fillMaxWidth().height(142.dp).clip(RoundedCornerShape(22.dp)).background(Ink)
            .then(if (destination == null) Modifier else Modifier.clickable { onNavigate(destination) }),
    ) {
        AsyncImage(model = banner.imageUrl, contentDescription = null, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
        Box(Modifier.fillMaxSize().background(Brush.horizontalGradient(listOf(Ink.copy(alpha = .92f), Ink.copy(alpha = .65f), Color.Transparent))))
        Column(Modifier.align(Alignment.CenterStart).padding(18.dp)) {
            Text(banner.eyebrow, color = Mint, fontSize = 10.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(6.dp))
            Text(banner.title, color = Color.White, fontSize = 19.sp, fontWeight = FontWeight.Bold, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Text(banner.subtitle, color = Color.White.copy(alpha = .8f), fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}

@Composable
private fun CourseSection(courses: List<Course>, onNavigate: (String) -> Unit) {
    Column {
        HomeSectionHeader("我的课程", "全部课程") { onNavigate("courses") }
        Spacer(Modifier.height(10.dp))
        if (courses.isEmpty()) {
            HomeEmptyCard("还没有同步课程", "连接学习通或教务系统后，课程会显示在这里") { onNavigate("courses") }
        } else courses.take(2).forEach { course ->
            HomeListCard(course.name, listOf(course.teacher, course.location).filter(String::isNotBlank).joinToString(" · ").ifBlank { "查看课程详情" }, Icons.Default.MenuBook) {
                onNavigate(if (course.id.isBlank()) "courses" else "courses/${Uri.encode(course.id)}")
            }
            Spacer(Modifier.height(8.dp))
        }
    }
}

@Composable
private fun TaskSection(tasks: List<Task>, onNavigate: (String) -> Unit) {
    Column {
        HomeSectionHeader("下一步要做", "全部待办") { onNavigate("tasks") }
        Spacer(Modifier.height(10.dp))
        if (tasks.isEmpty()) {
            HomeEmptyCard("目前没有待办", "有新任务时会显示在这里") { onNavigate("tasks") }
        } else tasks.take(2).forEach { task ->
            HomeListCard(task.title, task.due.ifBlank { task.course.ifBlank { "查看待办详情" } }, Icons.Default.EventNote) {
                onNavigate(if (task.id.isBlank()) "tasks" else "task_detail/${Uri.encode(task.id)}")
            }
            Spacer(Modifier.height(8.dp))
        }
    }
}

@Composable
private fun HomeSectionHeader(title: String, action: String, onAction: () -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(title, color = TextPrimary, fontSize = 19.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
        if (action.isNotBlank()) Text(action, color = Primary, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.clickable(onClick = onAction))
    }
}

@Composable
private fun HomeListCard(title: String, subtitle: String, icon: ImageVector, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Surface).clickable(onClick = onClick).padding(15.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(40.dp).clip(RoundedCornerShape(13.dp)).background(PrimarySoft), contentAlignment = Alignment.Center) {
            Icon(icon, null, tint = Primary, modifier = Modifier.size(21.dp))
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(title, color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(subtitle, color = Muted, fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        Icon(Icons.Default.ArrowForward, null, tint = Muted, modifier = Modifier.size(17.dp))
    }
}

@Composable
private fun HomeEmptyCard(title: String, subtitle: String, onClick: () -> Unit) {
    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Surface).clickable(onClick = onClick).padding(18.dp)) {
        Text(title, color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
        Text(subtitle, color = Muted, fontSize = 11.sp)
    }
}

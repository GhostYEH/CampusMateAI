package com.example.campusai.ui.screens.dashboard

import androidx.compose.animation.core.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.Notice
import com.example.campusai.data.model.Task
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.MockBadge
import com.example.campusai.ui.components.SectionHead
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch

@Composable
fun DashboardScreen(
    repository: AppRepository,
    onNavigate: (String) -> Unit
) {
    val session by repository.session.collectAsState()
    val tasks by repository.tasks.collectAsState()
    val notices by repository.notices.collectAsState()
    val pendingCount by repository.pendingCount.collectAsState()
    val role = session?.role ?: "student"

    val animatedAlpha by animateFloatAsState(
        targetValue = 1f,
        animationSpec = tween(400, easing = CubicBezierEasing(0.2f, 0.8f, 0.2f, 1f))
    )

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp, vertical = 16.dp)
            .graphicsLayer { alpha = animatedAlpha },
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        when (role) {
                            "student" -> "早上好，${session?.name ?: "同学"}"
                            "teacher" -> "教学工作台"
                            else -> "系统管理概览"
                        },
                        style = MaterialTheme.typography.headlineMedium
                    )
                    Spacer(Modifier.height(4.dp))
                    Text(
                        when (role) {
                            "student" -> "把今天的校园生活理清楚，专注重要的事。"
                            "teacher" -> "课程、班级和待批任务都在这里。"
                            else -> "查看平台运行状态与关键管理任务。"
                        },
                        color = Muted, fontSize = 13.sp
                    )
                }
                OutlinedButton(
                    onClick = { },
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = Primary)
                ) {
                    Icon(Icons.Default.Tune, null, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("自定义首页", fontSize = 13.sp)
                }
            }
        }

        if (role == "student") {
            item { NextActionCard(onNavigate) }
            item { TaskNoticeCourseRow(tasks, notices, pendingCount, repository, onNavigate) }
            item { WeeklyScheduleCard() }
            item { CompanionRail(onNavigate) }
        } else {
            item { RoleOverviewCards(role) }
            item { RoleActivityPanel(role) }
        }
    }
}

@Composable
private fun NextActionCard(onNavigate: (String) -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(Color(0xFFF0F7FB))
            .border(1.dp, Line, RoundedCornerShape(10.dp))
            .padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(18.dp)) {
            Text("下一步行动", fontWeight = FontWeight.Bold, color = TextPrimary)
            Box(
                modifier = Modifier.size(52.dp).clip(CircleShape).border(2.dp, Color(0xFFD7E9F5), CircleShape),
                contentAlignment = Alignment.Center
            ) {
                Text("1", color = Primary, fontSize = 24.sp, fontWeight = FontWeight.Bold)
            }
        }
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            ActionItem("《数据结构》作业提交", "今天 23:59 截止", isDanger = true, modifier = Modifier.weight(1f))
            ActionItem("图书馆预约", "今天 14:00", modifier = Modifier.weight(1f))
        }
        Button(
            onClick = { onNavigate("tasks") },
            shape = RoundedCornerShape(8.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Primary),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 10.dp)
        ) {
            Text("去完成", fontWeight = FontWeight.SemiBold)
            Icon(Icons.Default.ArrowForward, null, modifier = Modifier.size(16.dp))
        }
    }
}

@Composable
private fun ActionItem(title: String, subtitle: String, isDanger: Boolean = false, modifier: Modifier = Modifier) {
    Column(modifier = modifier.padding(start = 12.dp)) {
        Text(title, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, color = TextPrimary)
        Text(subtitle, fontSize = 12.sp, color = if (isDanger) DangerText else Muted)
    }
}

@Composable
private fun TaskNoticeCourseRow(
    tasks: List<Task>,
    notices: List<Notice>,
    pendingCount: Int,
    repository: AppRepository,
    onNavigate: (String) -> Unit
) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(14.dp)) {
        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            DataPanel {
                SectionHead("截止提醒", badge = pendingCount, actionLabel = "全部待办", onAction = { onNavigate("tasks") })
                Spacer(Modifier.height(8.dp))
                tasks.take(5).forEach { task ->
                    TaskRow(task, repository)
                }
            }
        }
        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            DataPanel {
                SectionHead("校园通知", actionLabel = "全部通知", onAction = { onNavigate("notifications") })
                Spacer(Modifier.height(8.dp))
                notices.forEach { notice ->
                    NoticeRowCompact(notice)
                }
            }
        }
    }
}

@Composable
private fun TaskRow(task: Task, repository: AppRepository) {
    val scope = rememberCoroutineScope()
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(9.dp)
    ) {
        Checkbox(
            checked = task.done,
            onCheckedChange = { scope.launch { repository.toggleTask(task.id) } },
            modifier = Modifier.size(17.dp),
            colors = CheckboxDefaults.colors(checkedColor = Success, uncheckedColor = Muted)
        )
        Column(modifier = Modifier.weight(1f)) {
            Text(
                task.title,
                fontSize = 13.sp,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                color = if (task.done) Muted else TextPrimary
            )
            Text(task.due, fontSize = 11.sp, color = if (task.done) Muted else DangerText)
        }
        Text(task.course, fontSize = 10.sp, color = Primary, modifier = Modifier
            .background(PrimarySoft, RoundedCornerShape(4.dp))
            .padding(horizontal = 5.dp, vertical = 2.dp))
    }
}

@Composable
private fun NoticeRowCompact(notice: Notice) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(9.dp)
    ) {
        if (notice.unread) {
            Box(Modifier.size(6.dp).clip(CircleShape).background(UnreadDot))
        } else {
            Spacer(Modifier.size(6.dp))
        }
        Column(modifier = Modifier.weight(1f)) {
            Text(notice.title, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(notice.source, fontSize = 11.sp, color = Muted)
        }
        Text(notice.time, fontSize = 11.sp, color = Muted)
    }
}

@Composable
private fun WeeklyScheduleCard() {
    val days = listOf(
        "周一" to listOf("数据结构", "高等数学（下）"),
        "周二" to listOf("操作系统", "大学英语 IV"),
        "周三" to listOf("计算机组成原理", "体育"),
        "周四" to listOf("数据库系统", "高等数学（下）"),
        "周五" to listOf("操作系统", ""),
    )
    DataPanel {
        SectionHead("本周课表")
        Spacer(Modifier.height(8.dp))
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            items(days) { (day, classes) ->
                Column(
                    modifier = Modifier
                        .width(80.dp)
                        .clip(RoundedCornerShape(8.dp))
                        .background(PrimarySoft)
                        .padding(10.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Text(day, fontSize = 12.sp, fontWeight = FontWeight.Bold, color = Primary)
                    classes.forEach { cls ->
                        if (cls.isNotEmpty()) Text(cls, fontSize = 10.sp, color = TextPrimary, maxLines = 1)
                    }
                }
            }
        }
    }
}

@Composable
private fun CompanionRail(onNavigate: (String) -> Unit) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(14.dp)) {
        DataPanel(modifier = Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("AI 导员", style = MaterialTheme.typography.titleSmall)
                MockBadge()
            }
            Spacer(Modifier.height(8.dp))
            Text("有问题，问小夏。", fontSize = 13.sp, color = Muted)
            Spacer(Modifier.height(8.dp))
            listOf("期末考试周的自习教室推荐", "如何申请课程重修？", "奖学金申请条件有哪些？").forEach { q ->
                OutlinedButton(
                    onClick = { onNavigate("counselor") },
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(8.dp),
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = TextPrimary)
                ) {
                    Text(q, fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                    Icon(Icons.Default.ChevronRight, null, modifier = Modifier.size(14.dp))
                }
                Spacer(Modifier.height(6.dp))
            }
        }
        DataPanel(modifier = Modifier.weight(1f)) {
            Text("学习陪伴", style = MaterialTheme.typography.titleSmall)
            Spacer(Modifier.height(8.dp))
            Text("本周学习时长", fontSize = 12.sp, color = Muted)
            Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("12.6", fontSize = 28.sp, fontWeight = FontWeight.Bold, color = Primary)
                Text("小时", fontSize = 12.sp, color = Muted)
            }
            Spacer(Modifier.height(8.dp))
            MiniBars(listOf(42, 58, 36, 76, 64, 88, 50))
            Spacer(Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text("专注状态", fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                    Text("识别结果仅供辅助参考", fontSize = 9.sp, color = Muted)
                }
                Text("良好", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Success)
            }
            Spacer(Modifier.height(8.dp))
            Button(
                onClick = { onNavigate("study") },
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(8.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Primary)
            ) {
                Text("开始学习", fontWeight = FontWeight.SemiBold)
            }
        }
    }
}

@Composable
private fun MiniBars(heights: List<Int>) {
    Row(modifier = Modifier.fillMaxWidth().height(40.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        heights.forEach { h ->
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxHeight()
                    .clip(RoundedCornerShape(2.dp))
                    .background(PrimarySoft),
                contentAlignment = Alignment.BottomCenter
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .fillMaxHeight(h / 100f)
                        .clip(RoundedCornerShape(2.dp))
                        .background(Primary.copy(alpha = 0.6f))
                )
            }
        }
    }
}

@Composable
private fun RoleOverviewCards(role: String) {
    val items = if (role == "teacher") listOf("3" to "进行中课程", "5" to "教学班级", "90" to "学生人数", "12" to "待批作业")
    else listOf("1,248" to "活跃用户", "42" to "课程总数", "99.9%" to "服务可用率", "6" to "待处理事项")
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(14.dp)) {
        items.forEach { (value, label) ->
            DataPanel(modifier = Modifier.weight(1f)) {
                Text(value, fontSize = 28.sp, fontWeight = FontWeight.Bold, color = Primary)
                Text(label, fontSize = 12.sp, color = Muted)
            }
        }
    }
}

@Composable
private fun RoleActivityPanel(role: String) {
    val activities = if (role == "teacher") listOf("批改数据结构第三次作业", "发布计算机网络课程通知", "查看高等数学提交统计", "更新操作系统课程资料")
    else listOf("知识库索引构建完成", "教师张明远创建新课程", "夜间备份任务执行成功", "学生账号批量导入完成")
    DataPanel {
        SectionHead(if (role == "teacher") "近期教学任务" else "系统动态", actionLabel = "查看全部", onAction = { })
        Spacer(Modifier.height(8.dp))
        activities.forEachIndexed { i, activity ->
            Row(
                modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(9.dp)
            ) {
                Icon(
                    if (role == "teacher") Icons.Default.Description else Icons.Default.MonitorHeart,
                    null, tint = Primary,
                    modifier = Modifier.size(20.dp).background(PrimarySoft, CircleShape).padding(3.dp)
                )
                Column(modifier = Modifier.weight(1f)) {
                    Text(activity, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                    Text("${i + 1} 小时前", fontSize = 11.sp, color = Muted)
                }
                Icon(Icons.Default.ChevronRight, null, tint = Muted, modifier = Modifier.size(16.dp))
            }
        }
    }
}

@Composable
private fun DataPanel(
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit
) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(10.dp))
            .background(Surface)
            .border(1.dp, Line, RoundedCornerShape(10.dp))
            .padding(14.dp),
        content = content
    )
}


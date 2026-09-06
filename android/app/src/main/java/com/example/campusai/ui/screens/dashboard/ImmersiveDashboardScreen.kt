package com.example.campusai.ui.screens.dashboard

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.AutoStories
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.School
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material3.Icon
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.launch
import com.example.campusai.R
import com.example.campusai.data.model.CampusNews
import com.example.campusai.data.model.Course
import com.example.campusai.data.model.Task
import com.example.campusai.data.repository.ApiFocusRepository
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.components.GlassTextButton as TextButton
import com.example.campusai.ui.screens.shell.floatingDockContentBottomPadding
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Success
import com.example.campusai.ui.theme.TextPrimary
import com.example.campusai.ui.glass.CampusGlassRole
import com.example.campusai.ui.glass.campusGlass

private val CampusBlue = Color(0xFF5B68F2)
private val CommunityOrange = Color(0xFFFFA43A)
private val SoftBlue = Color(0xFFE9F0FF)
private val SoftOrange = Color(0xFFFFF0DF)

@Composable
fun ImmersiveDashboardScreen(
    repository: AppRepository,
    focusRepository: ApiFocusRepository,
    onNavigate: (String) -> Unit,
) {
    val session by repository.session.collectAsStateWithLifecycle()
    val tasks by repository.tasks.collectAsStateWithLifecycle()
    val courses by repository.courses.collectAsStateWithLifecycle()
    val notices by repository.notices.collectAsStateWithLifecycle()
    val campusNews by repository.campusNews.collectAsStateWithLifecycle()
    val hitokoto by repository.hitokoto.collectAsStateWithLifecycle()
    val bingDailyWallpaper by repository.bingDailyWallpaper.collectAsStateWithLifecycle()
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    val focusStats by focusRepository.stats.collectAsStateWithLifecycle()
    var overviewMetricSelection by remember { mutableStateOf(defaultOverviewMetricIds()) }
    var showOverviewCustomization by remember { mutableStateOf(false) }
    val visibleOverviewMetricIds = normalizeOverviewMetricIds(overviewMetricSelection, defaultOverviewMetricIds())
    val unreadCount = notices.count { it.unread }
    val bottomPadding = floatingDockContentBottomPadding(
        WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding(),
    )

    LaunchedEffect(Unit) {
        launch { repository.refreshHitokoto() }
        launch { repository.refreshBingDailyWallpaper() }
        launch { focusRepository.refresh() }
        repository.refreshNotices()
        repository.refreshCampusNews()
        repository.refreshCourses()
        repository.refreshTasks()
    }

    Box(Modifier.fillMaxSize().background(Background)) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(bottom = bottomPadding),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item(key = "immersive-header") {
                ImmersiveHeader(
                    name = session?.name ?: "校园同学",
                    hitokoto = hitokoto.displayText(),
                    wallpaperUrl = bingDailyWallpaper.wallpaper?.imageUrl,
                    unreadCount = unreadCount,
                    reduceMotion = reduceMotion,
                    onProfile = { onNavigate("profile") },
                    onNotifications = { onNavigate("notifications") },
                    onScan = { onNavigate("qr_scanner") },
                )
            }
            item(key = "cpm-assistant") {
                AssistantCard(
                    reduceMotion = reduceMotion,
                    onClick = { onNavigate("counselor") },
                )
            }
            item(key = "feature-cards") {
                FeatureCards(
                    reduceMotion = reduceMotion,
                    todayFocusMinutes = focusStats.todayMinutes,
                    onNavigate = onNavigate,
                )
            }
            item(key = "overview") {
                OverviewCard(
                    courseCount = courses.size,
                    pendingCount = tasks.count { !it.done },
                    unreadCount = unreadCount,
                    todayFocusMinutes = focusStats.todayMinutes,
                    visibleMetricIds = visibleOverviewMetricIds.toSet(),
                    onCustomize = { showOverviewCustomization = true },
                    onNavigate = onNavigate,
                    reduceMotion = reduceMotion,
                )
            }
            item(key = "today-courses") {
                TodayCoursesCard(courses = courses, onNavigate = onNavigate, reduceMotion = reduceMotion)
            }
            item(key = "campus-updates") {
                CampusUpdatesCard(items = campusNews, onNavigate = onNavigate, reduceMotion = reduceMotion)
            }
        }
    }

    if (showOverviewCustomization) {
        OverviewCustomizationDialog(
            selectedIds = visibleOverviewMetricIds.toSet(),
            onDismiss = { showOverviewCustomization = false },
            onApply = { ids ->
                overviewMetricSelection = normalizeOverviewMetricIds(ids, defaultOverviewMetricIds())
                showOverviewCustomization = false
            },
        )
    }
}

@Composable
private fun ImmersiveHeader(
    name: String,
    hitokoto: String,
    wallpaperUrl: String?,
    unreadCount: Int,
    reduceMotion: Boolean,
    onProfile: () -> Unit,
    onNotifications: () -> Unit,
    onScan: () -> Unit,
) {
    val contentTopPadding = dashboardHeaderContentTopPadding(
        WindowInsets.statusBars.asPaddingValues().calculateTopPadding(),
    )

    Box(Modifier.fillMaxWidth().height(214.dp)) {
        AsyncImage(
            model = wallpaperUrl,
            contentDescription = null,
            contentScale = ContentScale.Crop,
            placeholder = painterResource(R.drawable.campus_login_poster),
            error = painterResource(R.drawable.campus_login_poster),
            fallback = painterResource(R.drawable.campus_login_poster),
            modifier = Modifier.fillMaxSize(),
        )
        Box(
            Modifier.fillMaxSize().background(
                Brush.verticalGradient(
                    0f to Color.White.copy(alpha = .18f),
                    .42f to Color.White.copy(alpha = .32f),
                    1f to Background,
                ),
            ),
        )
        Row(
            modifier = Modifier.fillMaxWidth().padding(start = 22.dp, top = contentTopPadding, end = 18.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            HeaderAvatar(onClick = onProfile)
            Column(Modifier.padding(start = 11.dp).clickable(role = Role.Button, onClick = onProfile)) {
                Text("${greeting()}，$name", color = TextPrimary, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                Text(
                    hitokoto,
                    color = TextPrimary.copy(alpha = .72f),
                    fontSize = 12.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
            Spacer(Modifier.weight(1f))
            HeaderIconButton(Icons.Default.Notifications, "通知", unreadCount > 0, reduceMotion, onNotifications)
            Spacer(Modifier.width(9.dp))
            HeaderIconButton(Icons.Default.QrCodeScanner, "扫一扫", false, reduceMotion, onScan)
        }
    }
}

private fun greeting(): String = "早上好"

@Composable
private fun HeaderAvatar(onClick: () -> Unit) {
    Image(
        painter = painterResource(R.drawable.profile_avatar_reference),
        contentDescription = "个人头像",
        contentScale = ContentScale.Crop,
        modifier = Modifier.size(54.dp).clip(CircleShape).border(2.dp, Color.White, CircleShape).shadow(8.dp, CircleShape).campusClickable(onClick = onClick),
    )
}

@Composable
private fun HeaderIconButton(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    description: String,
    showBadge: Boolean,
    reduceMotion: Boolean,
    onClick: () -> Unit,
) {
    Box(
        Modifier.size(52.dp).campusGlass(
            shape = RoundedCornerShape(18.dp),
            role = CampusGlassRole.PANEL,
            tint = Color.White.copy(alpha = .58f),
        ).campusClickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, description, tint = TextPrimary, modifier = Modifier.size(24.dp))
        if (showBadge) {
            Box(
                Modifier.size(10.dp).align(Alignment.TopEnd).offset(x = (-8).dp, y = 8.dp).clip(CircleShape).background(Color(0xFFE95656)).border(2.dp, Color.White, CircleShape),
            )
        }
    }
}

@Composable
private fun AssistantCard(reduceMotion: Boolean, onClick: () -> Unit) {
    Box(
        Modifier.fillMaxWidth().height(210.dp).offset(y = (-24).dp).padding(horizontal = 16.dp).campusGlass(
            shape = RoundedCornerShape(28.dp),
            role = CampusGlassRole.PANEL,
            tint = Color.White.copy(alpha = .62f),
        ).campusClickable(onClick = onClick).enterAnimation(enabled = !reduceMotion),
    ) {
        Box(Modifier.fillMaxSize().background(Brush.horizontalGradient(listOf(Color.White.copy(alpha = .16f), SoftBlue.copy(alpha = .46f)))))
        Image(
            painter = painterResource(R.drawable.cpm_avatar_fallback),
            contentDescription = "CPM 数字人",
            contentScale = ContentScale.Fit,
            modifier = Modifier.width(158.dp).height(204.dp).align(Alignment.BottomStart).offset(x = 8.dp, y = 9.dp),
        )
        Column(
            modifier = Modifier.align(Alignment.CenterEnd).fillMaxWidth(.62f).padding(end = 19.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("AI 学习助手", color = TextPrimary, fontSize = 21.sp, fontWeight = FontWeight.Bold)
                Icon(Icons.Default.AutoAwesome, null, tint = CampusBlue, modifier = Modifier.padding(start = 7.dp).size(18.dp))
            }
            Text("我是你的 CPM 学习搭子", color = TextPrimary.copy(alpha = .78f), fontSize = 12.sp, modifier = Modifier.padding(top = 8.dp))
            Text("制定学习计划、解答问题，陪你把校园生活安排得更从容。", color = Muted, fontSize = 11.sp, lineHeight = 17.sp, modifier = Modifier.padding(top = 4.dp))
            Row(
                Modifier.padding(top = 13.dp).border(1.dp, CampusBlue.copy(alpha = .62f), CircleShape).padding(horizontal = 16.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("去提问", color = CampusBlue, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                Icon(Icons.Default.ChevronRight, null, tint = CampusBlue, modifier = Modifier.padding(start = 5.dp).size(16.dp))
            }
        }
        Box(Modifier.size(34.dp).align(Alignment.TopStart).offset(x = 19.dp, y = 18.dp).clip(CircleShape).background(Color.White.copy(alpha = .8f)), contentAlignment = Alignment.Center) {
            Text("AI", color = CampusBlue, fontSize = 12.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun FeatureCards(
    reduceMotion: Boolean,
    todayFocusMinutes: Int,
    onNavigate: (String) -> Unit,
) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        dashboardFeatureCards().forEachIndexed { index, card ->
            val orange = card.route == "community"
            val shape = RoundedCornerShape(24.dp)
            Column(
                Modifier.weight(1f).height(124.dp).campusGlass(
                    shape = shape,
                    role = CampusGlassRole.PANEL,
                    tint = if (orange) Color(0xFFFFF4E6).copy(alpha = .42f) else Color(0xFFEAF1FF).copy(alpha = .44f),
                ).background(
                    Brush.linearGradient(
                        if (orange) listOf(Color.White.copy(alpha = .12f), SoftOrange.copy(alpha = .25f))
                        else listOf(Color.White.copy(alpha = .16f), SoftBlue.copy(alpha = .24f)),
                    ),
                    shape,
                ).campusClickable { onNavigate(card.route) }.padding(14.dp).enterAnimation(delayMs = 80 + index * 50, enabled = !reduceMotion),
            ) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
                    Icon(if (orange) Icons.Default.Groups else Icons.Default.Timer, null, tint = if (orange) CommunityOrange else CampusBlue, modifier = Modifier.size(22.dp))
                    Column(Modifier.padding(start = 9.dp).weight(1f)) {
                        Text(card.title, color = TextPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Clip)
                        Text(card.subtitle, color = Muted, fontSize = 9.5.sp, lineHeight = 14.sp, modifier = Modifier.padding(top = 3.dp), maxLines = 2, overflow = TextOverflow.Ellipsis)
                    }
                    Icon(Icons.Default.ChevronRight, null, tint = TextPrimary.copy(alpha = .55f), modifier = Modifier.size(18.dp))
                }
                Spacer(Modifier.weight(1f))
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Bottom) {
                    if (!orange) {
                        Column(Modifier.weight(1f)) {
                            Text("今日专注", color = Muted, fontSize = 8.5.sp, maxLines = 1)
                            Text(
                                dashboardFocusDurationValue(todayFocusMinutes),
                                color = CampusBlue,
                                fontSize = 10.5.sp,
                                fontWeight = FontWeight.SemiBold,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                    } else {
                        Spacer(Modifier.width(1.dp))
                    }
                    Spacer(Modifier.weight(1f))
                    if (orange) CommunityBubbles() else FocusIllustration()
                }
            }
        }
    }
}

@Composable
private fun CommunityBubbles() {
    Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Box(Modifier.size(22.dp).clip(CircleShape).background(CommunityOrange.copy(alpha = .78f)))
        Box(Modifier.size(30.dp).clip(CircleShape).background(CommunityOrange.copy(alpha = .38f)))
        Box(Modifier.size(18.dp).clip(CircleShape).background(Color(0xFFFFC979).copy(alpha = .75f)))
    }
}

@Composable
private fun FocusIllustration() {
    Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        Box(Modifier.width(34.dp).height(6.dp).clip(CircleShape).background(CampusBlue.copy(alpha = .25f)))
        Icon(Icons.Default.AutoStories, null, tint = CampusBlue.copy(alpha = .48f), modifier = Modifier.size(22.dp))
    }
}

@Composable
private fun OverviewCard(
    courseCount: Int,
    pendingCount: Int,
    unreadCount: Int,
    todayFocusMinutes: Int,
    visibleMetricIds: Set<String>,
    onCustomize: () -> Unit,
    onNavigate: (String) -> Unit,
    reduceMotion: Boolean,
) {
    DashboardCard(modifier = Modifier.padding(horizontal = 16.dp), delayMs = 150, reduceMotion = reduceMotion) {
        Row(Modifier.fillMaxWidth().campusClickable(onClick = onCustomize), verticalAlignment = Alignment.CenterVertically) {
            Text("信息总览", color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.weight(1f))
            Text("自定义", color = Muted, fontSize = 10.5.sp)
            Icon(Icons.Default.ChevronRight, null, tint = Muted, modifier = Modifier.size(16.dp))
        }
        Spacer(Modifier.height(12.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if ("courses" in visibleMetricIds) OverviewMetric(Modifier.weight(1f), Icons.Default.MenuBook, "今日课程", "$courseCount 门", "打开课程", CampusBlue) { onNavigate("courses") }
            if ("tasks" in visibleMetricIds) OverviewMetric(Modifier.weight(1f), Icons.Default.Schedule, "近期截止", "$pendingCount 项", "查看待办", Color(0xFF7B68EE)) { onNavigate("tasks") }
            if ("focus" in visibleMetricIds) OverviewMetric(Modifier.weight(1f), Icons.Default.Timer, "今日专注", "${todayFocusMinutes.coerceAtLeast(0)} 分钟", "开始专注", Success) { onNavigate("focus") }
            if ("notifications" in visibleMetricIds) OverviewMetric(Modifier.weight(1f), Icons.Default.Notifications, "未读通知", "$unreadCount 条", "查看待办", Success) { onNavigate(dashboardUnreadNotificationRoute()) }
        }
    }
}

@Composable
private fun OverviewCustomizationDialog(
    selectedIds: Set<String>,
    onDismiss: () -> Unit,
    onApply: (List<String>) -> Unit,
) {
    var draftIds by remember(selectedIds) { mutableStateOf(selectedIds) }
    val options = listOf(
        "courses" to "今日课程",
        "tasks" to "近期截止",
        "focus" to "今日专注",
        "notifications" to "未读通知",
    )
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("自定义信息总览", fontWeight = FontWeight.Bold) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text("选择要显示的卡片，至少保留一项。", color = Muted, fontSize = 12.sp)
                options.forEach { (id, label) ->
                    Row(Modifier.fillMaxWidth().campusClickable {
                        draftIds = when {
                            id in draftIds && draftIds.size == 1 -> draftIds
                            id in draftIds -> draftIds - id
                            else -> draftIds + id
                        }
                    }, verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(
                            checked = id in draftIds,
                            onCheckedChange = { checked ->
                                if (checked || draftIds.size > 1) {
                                    draftIds = if (checked) draftIds + id else draftIds - id
                                }
                            },
                            colors = CheckboxDefaults.colors(checkedColor = CampusBlue),
                        )
                        Text(label, color = TextPrimary, fontSize = 14.sp)
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = { onApply(options.map { it.first }.filter { it in draftIds }) }) { Text("应用", color = CampusBlue) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消", color = Muted) } },
    )
}

@Composable
private fun OverviewMetric(
    modifier: Modifier,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    value: String,
    hint: String,
    tint: Color,
    onClick: () -> Unit,
) {
    val shape = RoundedCornerShape(17.dp)
    Column(
        modifier.campusGlass(
            shape = shape,
            role = CampusGlassRole.DENSE,
            tint = Color.White.copy(alpha = .34f),
        ).background(Color.White.copy(alpha = .12f), shape).campusClickable(onClick = onClick).padding(10.dp),
    ) {
        Icon(icon, null, tint = tint, modifier = Modifier.size(20.dp))
        Text(label, color = Muted, fontSize = 9.5.sp, modifier = Modifier.padding(top = 9.dp), maxLines = 1, overflow = TextOverflow.Ellipsis)
        Text(value, color = TextPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 4.dp), maxLines = 1)
        Text(hint, color = Muted, fontSize = 9.sp, modifier = Modifier.padding(top = 3.dp), maxLines = 1)
    }
}

@Composable
private fun TodayCoursesCard(courses: List<Course>, onNavigate: (String) -> Unit, reduceMotion: Boolean) {
    DashboardCard(modifier = Modifier.padding(horizontal = 16.dp), delayMs = 190, reduceMotion = reduceMotion) {
        SectionHeader("今日课程", "查看课表", dashboardCourseSectionRoute(), onNavigate)
        Spacer(Modifier.height(12.dp))
        if (courses.isEmpty()) {
            EmptyCourseRow(onNavigate)
        } else {
            courses.take(3).forEachIndexed { index, course ->
                CourseRow(course, index == 0, onNavigate)
                if (index != courses.take(3).lastIndex) Spacer(Modifier.height(8.dp))
            }
        }
    }
}

@Composable
private fun CourseRow(course: Course, current: Boolean, onNavigate: (String) -> Unit) {
    val shape = RoundedCornerShape(18.dp)
    Row(
        Modifier.fillMaxWidth().campusGlass(
            shape = shape,
            role = CampusGlassRole.DENSE,
            tint = if (current) SoftBlue.copy(alpha = .48f) else Color.White.copy(alpha = .28f),
        ).background(if (current) SoftBlue.copy(alpha = .14f) else Color.White.copy(alpha = .08f), shape)
            .campusClickable { onNavigate("courses") }.padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.width(68.dp)) {
            Text(if (current) "进行中" else "课程", color = if (current) CampusBlue else Muted, fontSize = 10.sp, fontWeight = FontWeight.Bold)
            Text(if (current) "现在" else "今日", color = Muted, fontSize = 10.sp, modifier = Modifier.padding(top = 4.dp))
        }
        Box(Modifier.width(1.dp).height(35.dp).background(Line))
        Column(Modifier.weight(1f).padding(start = 12.dp)) {
            Text(course.name, color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(listOf(course.location, course.teacher).filter(String::isNotBlank).joinToString(" · ").ifBlank { "课程信息待同步" }, color = Muted, fontSize = 10.5.sp, modifier = Modifier.padding(top = 4.dp), maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        Icon(Icons.Default.ChevronRight, null, tint = Muted, modifier = Modifier.size(18.dp))
    }
}

@Composable
private fun EmptyCourseRow(onNavigate: (String) -> Unit) {
    val shape = RoundedCornerShape(18.dp)
    Row(
        Modifier.fillMaxWidth().campusGlass(
            shape = shape,
            role = CampusGlassRole.DENSE,
            tint = SoftBlue.copy(alpha = .44f),
        ).background(SoftBlue.copy(alpha = .14f), shape).campusClickable { onNavigate("courses") }.padding(16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Default.MenuBook, null, tint = CampusBlue, modifier = Modifier.size(26.dp))
        Column(Modifier.padding(start = 12.dp).weight(1f)) {
            Text("今日暂无课程", color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.Bold)
            Text("可以安排一段专注学习", color = Muted, fontSize = 10.5.sp, modifier = Modifier.padding(top = 4.dp))
        }
        Icon(Icons.Default.ChevronRight, null, tint = CampusBlue, modifier = Modifier.size(18.dp))
    }
}

@Composable
private fun CampusUpdatesCard(items: List<CampusNews>, onNavigate: (String) -> Unit, reduceMotion: Boolean) {
    DashboardCard(modifier = Modifier.padding(horizontal = 16.dp), delayMs = 230, reduceMotion = reduceMotion) {
        SectionHeader("校园动态", "查看更多", "campus-news", onNavigate)
        Spacer(Modifier.height(12.dp))
        if (items.isEmpty()) {
            Text("校园消息正在整理中", color = Muted, fontSize = 11.sp)
        } else {
            LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                items(items.take(4), key = { it.id }) { item ->
                    val shape = RoundedCornerShape(18.dp)
                    Column(
                        Modifier.width(220.dp).campusGlass(
                            shape = shape,
                            role = CampusGlassRole.DENSE,
                            tint = Color.White.copy(alpha = .28f),
                        ).background(Color.White.copy(alpha = .08f), shape)
                            .campusClickable { onNavigate("campus-news-detail/${item.id}") }.padding(13.dp),
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.AutoAwesome, null, tint = CampusBlue, modifier = Modifier.size(17.dp))
                            Text(item.category, color = CampusBlue, fontSize = 10.sp, modifier = Modifier.padding(start = 6.dp))
                        }
                        Text(item.title, color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 8.dp), maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text(item.summary, color = Muted, fontSize = 10.sp, modifier = Modifier.padding(top = 4.dp), maxLines = 2, overflow = TextOverflow.Ellipsis)
                    }
                }
            }
        }
    }
}

@Composable
private fun DashboardCard(modifier: Modifier, delayMs: Int, reduceMotion: Boolean, content: @Composable ColumnScope.() -> Unit) {
    Column(
        modifier.fillMaxWidth().campusGlass(
            shape = RoundedCornerShape(26.dp),
            role = CampusGlassRole.PANEL,
            tint = Color.White.copy(alpha = .62f),
        ).padding(16.dp).enterAnimation(delayMs = delayMs, enabled = !reduceMotion),
        content = content,
    )
}

@Composable
private fun SectionHeader(title: String, action: String, route: String?, onNavigate: (String) -> Unit) {
    val actionModifier = route?.let { target ->
        Modifier.clip(RoundedCornerShape(7.dp)).campusClickable { onNavigate(target) }.padding(vertical = 4.dp)
    } ?: Modifier
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(title, color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.weight(1f))
        Row(actionModifier, verticalAlignment = Alignment.CenterVertically) {
            Text(action, color = Muted, fontSize = 10.5.sp)
            if (route != null) {
                Icon(Icons.Default.ChevronRight, null, tint = Muted, modifier = Modifier.size(16.dp))
            }
        }
    }
}

package com.example.campusai.ui.screens.shell

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BarChart
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material.icons.filled.Timeline
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
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
import androidx.navigation.NavHostController
import androidx.navigation.compose.currentBackStackEntryAsState
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.PulseEffect
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import com.example.campusai.ui.theme.UnreadDot

data class NavItem(val route: String, val label: String, val icon: ImageVector)

val studentNavItems = listOf(
    NavItem("home", "首页", Icons.Default.Home),
    NavItem("courses", "课程", Icons.Default.MenuBook),
    NavItem("tasks", "待办", Icons.Default.CheckCircle),
    NavItem("counselor", "AI 导员", Icons.Default.SmartToy),
    NavItem("profile", "我的", Icons.Default.Person),
)

val teacherNavItems = listOf(
    NavItem("home", "工作台", Icons.Default.Dashboard),
    NavItem("courses", "课程", Icons.Default.MenuBook),
    NavItem("publish", "发布", Icons.Default.Send),
    NavItem("stats", "统计", Icons.Default.BarChart),
    NavItem("profile", "我的", Icons.Default.Person),
)

val adminNavItems = listOf(
    NavItem("home", "概览", Icons.Default.Dashboard),
    NavItem("users", "用户", Icons.Default.People),
    NavItem("courses", "课程", Icons.Default.MenuBook),
    NavItem("system", "系统", Icons.Default.Settings),
)

@Composable
fun AppShell(
    navController: NavHostController,
    repository: AppRepository,
    content: @Composable () -> Unit,
) {
    val session by repository.session.collectAsState()
    val pendingCount by repository.pendingCount.collectAsState()
    val navItems = when (session?.role ?: "student") {
        "teacher" -> teacherNavItems
        "admin" -> adminNavItems
        else -> studentNavItems
    }.take(5)
    val backStack by navController.currentBackStackEntryAsState()
    val route = backStack?.destination?.route ?: "home"
    val isProfileFlow = route in setOf("profile", "settings", "account")

    Column(
        Modifier.fillMaxSize().background(
            if (isProfileFlow) Color(0xFFF8F9FD) else Background
        )
    ) {
        if (route != "home" && !isProfileFlow) {
            CampusTopBar(
                name = session?.name ?: "校园同学",
                role = session?.role ?: "student",
                onProfileClick = {
                    navController.navigate("profile") { launchSingleTop = true }
                },
                onNotificationsClick = {
                    navController.navigate("notifications") { launchSingleTop = true }
                },
            )
        }
        Box(Modifier.weight(1f)) { content() }
        CampusDock(
            items = navItems,
            route = route,
            pendingCount = pendingCount,
            referenceStyle = isProfileFlow,
            onNavigate = { target ->
                navController.navigate(target) {
                    popUpTo("home") { inclusive = false }
                    launchSingleTop = true
                }
            },
        )
    }
}

@Composable
private fun CampusTopBar(
    name: String,
    role: String,
    onProfileClick: () -> Unit,
    onNotificationsClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Surface)
            .statusBarsPadding()
            .padding(start = 18.dp, top = 11.dp, end = 14.dp, bottom = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier.size(34.dp).clip(RoundedCornerShape(10.dp)).background(PrimarySoft)
                .campusClickable(onClick = onProfileClick),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                if (role == "student") "知" else if (role == "teacher") "师" else "管",
                color = Primary,
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
            )
        }
        Column(
            Modifier.padding(start = 10.dp).campusClickable(onClick = onProfileClick)
        ) {
            Text(
                name,
                color = TextPrimary,
                fontSize = 14.sp,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text("第 12 周 · 今天也慢慢来", color = Muted, fontSize = 10.sp)
        }
        Spacer(Modifier.weight(1f))
        Box(
            Modifier
                .size(36.dp)
                .clip(CircleShape)
                .background(PrimarySoft)
                .campusClickable(onClick = onNotificationsClick),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.Default.Notifications, "通知", tint = Muted, modifier = Modifier.size(19.dp))
            Box(
                Modifier.align(Alignment.TopEnd)
                    .padding(top = 4.dp, end = 4.dp)
                    .size(10.dp),
            ) {
                Box(
                    Modifier
                        .size(6.dp)
                        .clip(CircleShape)
                        .background(UnreadDot)
                        .align(Alignment.Center),
                )
                PulseEffect(
                    color = UnreadDot,
                    pulseSize = 10.dp,
                    modifier = Modifier.fillMaxSize(),
                )
            }
        }
    }
}

@Composable
private fun CampusDock(
    items: List<NavItem>,
    route: String,
    pendingCount: Int,
    referenceStyle: Boolean,
    onNavigate: (String) -> Unit,
) {
    val dockSurface = if (referenceStyle) Color.White else Surface
    val dockLine = if (referenceStyle) Color(0xFFF0F1F6) else Line
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(dockSurface)
            .border(1.dp, dockLine.copy(alpha = .65f), RoundedCornerShape(topStart = 18.dp, topEnd = 18.dp))
            .navigationBarsPadding()
            .height(62.dp)
            .padding(horizontal = 8.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        items.forEach { item ->
            val selected = route == item.route ||
                (item.route == "profile" && route in setOf("settings", "account"))
            val color by animateColorAsState(
                if (referenceStyle && selected) Color(0xFF6668F7)
                else if (referenceStyle) Color(0xFF6D748A)
                else if (selected) Primary else Muted,
                label = "dock-color",
            )
            val markerWidth by animateDpAsState(
                if (selected) 22.dp else 0.dp,
                label = "dock-marker",
            )
            Column(
                Modifier
                    .weight(1f)
                    .height(50.dp)
                    .campusClickable { onNavigate(item.route) },
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(item.icon, item.label, tint = color, modifier = Modifier.size(20.dp))
                    if (item.route == "tasks" && pendingCount > 0) {
                        Box(
                            Modifier.align(Alignment.TopEnd)
                                .size(14.dp)
                                .clip(CircleShape)
                                .background(UnreadDot),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(
                                pendingCount.coerceAtMost(9).toString(),
                                color = Color.White,
                                fontSize = 8.sp,
                                fontWeight = FontWeight.Bold,
                            )
                        }
                    }
                }
                Spacer(Modifier.height(3.dp))
                Text(
                    item.label,
                    color = color,
                    fontSize = 9.5.sp,
                    fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
                )
                Spacer(Modifier.height(3.dp))
                Box(
                    Modifier
                        .size(width = markerWidth, height = 2.dp)
                        .clip(CircleShape)
                        .background(
                            if (selected && referenceStyle) Color(0xFF6668F7)
                            else if (selected) Primary else Color.Transparent
                        ),
                )
            }
        }
    }
}

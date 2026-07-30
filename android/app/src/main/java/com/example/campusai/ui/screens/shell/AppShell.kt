package com.example.campusai.ui.screens.shell

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.NavHostController
import androidx.navigation.compose.currentBackStackEntryAsState
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.MockBadge
import com.example.campusai.ui.theme.*

data class NavItem(val route: String, val label: String, val icon: ImageVector)

val studentNavItems = listOf(
    NavItem("home", "首页", Icons.Default.Home),
    NavItem("courses", "课程", Icons.Default.MenuBook),
    NavItem("tasks", "待办", Icons.Default.CheckCircle),
    NavItem("counselor", "AI 导员", Icons.Default.SmartToy),
    NavItem("notifications", "通知整理", Icons.Default.Notifications),
    NavItem("study", "学习陪伴", Icons.Default.Timeline),
    NavItem("profile", "个人中心", Icons.Default.Person),
)

val teacherNavItems = listOf(
    NavItem("home", "教师工作台", Icons.Default.Dashboard),
    NavItem("courses", "课程管理", Icons.Default.MenuBook),
    NavItem("publish", "发布中心", Icons.Default.Send),
    NavItem("stats", "教学统计", Icons.Default.BarChart),
    NavItem("profile", "个人中心", Icons.Default.Person),
)

val adminNavItems = listOf(
    NavItem("home", "管理概览", Icons.Default.Dashboard),
    NavItem("users", "用户管理", Icons.Default.People),
    NavItem("courses", "课程管理", Icons.Default.MenuBook),
    NavItem("system", "系统状态", Icons.Default.Settings),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppShell(
    navController: NavHostController,
    repository: AppRepository,
    content: @Composable () -> Unit
) {
    val session by repository.session.collectAsState()
    val pendingCount by repository.pendingCount.collectAsState()
    val role = session?.role ?: "student"
    val navItems = when (role) {
        "teacher" -> teacherNavItems
        "admin" -> adminNavItems
        else -> studentNavItems
    }

    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route


    Scaffold(
        bottomBar = {
            NavigationBar(
                containerColor = Surface,
                tonalElevation = 0.dp,
                modifier = Modifier.height(64.dp)
            ) {
                val bottomItems = navItems.take(5)
                bottomItems.forEach { item ->
                    NavigationBarItem(
                        selected = currentRoute == item.route,
                        onClick = { navController.navigate(item.route) { popUpTo("home") { inclusive = false }; launchSingleTop = true } },
                        icon = {
                            BadgedBox(
                                badge = {
                                    if (item.route == "tasks" && pendingCount > 0) {
                                        Badge { Text(pendingCount.toString()) }
                                    }
                                }
                            ) {
                                Icon(
                                    item.icon,
                                    item.label,
                                    tint = if (currentRoute == item.route) Primary else Muted
                                )
                            }
                        },
                        label = {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(item.label, fontSize = 11.sp, maxLines = 1)
                                if (item.route == "counselor") MockBadge()
                            }
                        },
                        colors = NavigationBarItemDefaults.colors()
                    )
                }
            }
        },
        topBar = {
            TopAppBar(
                title = {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Default.School, null, tint = Primary, modifier = Modifier.size(24.dp))
                        Text("CampusMate AI", fontWeight = FontWeight.Bold, fontSize = 16.sp, color = TextPrimary)
                    }
                },
                actions = {
                    IconButton(onClick = { }) {
                        BadgedBox(badge = { Box(Modifier.size(8.dp).clip(CircleShape).background(UnreadDot)) }) {
                            Icon(Icons.Default.Notifications, "通知", tint = Muted)
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Surface,
                    titleContentColor = TextPrimary
                )
            )
        },
        containerColor = Background
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            content()
        }
    }
}
package com.example.campusai.ui.screens.shell

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
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
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
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
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import com.example.campusai.ui.theme.UnreadDot
import kotlinx.coroutines.launch

data class NavItem(val route: String, val label: String, val icon: ImageVector)

/**
 * Bottom dock visible height reserved on top of the system navigation bar.
 * Equals 76dp (dock row) + 6dp (top padding) + 10dp (bottom padding).
 * Screens that draw content above the dock (FABs, lists' bottom contentPadding)
 * should add this height to their own bottom insets.
 */
val BottomDockReservedHeight = 76.dp + 6.dp + 10.dp

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
    val reduceMotion by repository.reduceMotion.collectAsState()
    val navItems = when (session?.role ?: "student") {
        "teacher" -> teacherNavItems
        "admin" -> adminNavItems
        else -> studentNavItems
    }.take(5)
    val backStack by navController.currentBackStackEntryAsState()
    val route = backStack?.destination?.route ?: "home"
    val profileRoutes = setOf("profile", "settings", "account", "files", "activities", "favorites")
    val isProfileFlow = route in profileRoutes

    Box(
        Modifier.fillMaxSize().background(Background),
    ) {
        // The app uses page content and the bottom dock as its navigation model;
        // no secondary personal header is shown above the main tabs.
        if (false) {
            CampusTopBar(
                name = session?.name ?: "校园同学",
                role = session?.role ?: "student",
                reduceMotion = reduceMotion,
                onProfileClick = {
                    navController.navigate("profile") { launchSingleTop = true }
                },
                onNotificationsClick = {
                    navController.navigate("notifications") { launchSingleTop = true }
                },
            )
        }
        Box(
            Modifier.fillMaxSize().then(
                if (route == "home" || isProfileFlow) Modifier else Modifier.statusBarsPadding(),
            ),
        ) { content() }
        CampusDock(
            modifier = Modifier
                .align(Alignment.BottomCenter),
            items = navItems,
            route = route,
            pendingCount = pendingCount,
            reduceMotion = reduceMotion,
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
    reduceMotion: Boolean,
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
                    enabled = !reduceMotion,
                    modifier = Modifier.fillMaxSize(),
                )
            }
        }
    }
}

@Composable
private fun CampusDock(
    modifier: Modifier = Modifier,
    items: List<NavItem>,
    route: String,
    pendingCount: Int,
    reduceMotion: Boolean,
    onNavigate: (String) -> Unit,
) {
    val profileRoutes = setOf("profile", "settings", "account", "files", "activities", "favorites")
    val primaryColor = Primary
    Box(
        modifier = modifier
            .fillMaxWidth()
            .navigationBarsPadding()
            .padding(start = 14.dp, top = 6.dp, end = 14.dp, bottom = 10.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(76.dp)
                .clip(RoundedCornerShape(38.dp))
                .background(Color.White.copy(alpha = .68f))
                .drawBehind {
                    // Two soft highlights create the depth of frosted glass without
                    // requiring an API-level-specific blur implementation.
                    drawRoundRect(
                        color = Color.White.copy(alpha = .34f),
                        cornerRadius = CornerRadius(size.height / 2f),
                    )
                    drawCircle(
                        brush = Brush.radialGradient(
                            colors = listOf(Color.White.copy(alpha = .56f), Color.Transparent),
                            center = Offset(0f, 0f),
                            radius = size.width * .62f,
                        ),
                        radius = size.width * .62f,
                        center = Offset(0f, 0f),
                    )
                    drawCircle(
                        brush = Brush.radialGradient(
                            colors = listOf(primaryColor.copy(alpha = .08f), Color.Transparent),
                            center = Offset(size.width, size.height),
                            radius = size.width * .52f,
                        ),
                        radius = size.width * .52f,
                        center = Offset(size.width, size.height),
                    )
                }
                .border(1.dp, Color.White.copy(alpha = .86f), RoundedCornerShape(38.dp))
                .padding(horizontal = 7.dp, vertical = 7.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            items.forEach { item ->
                val selected = route == item.route ||
                    (item.route == "profile" && route in profileRoutes)
                LiquidGlassNavItem(
                    item = item,
                    isSelected = selected,
                    pendingCount = pendingCount,
                    reduceMotion = reduceMotion,
                    onNavigate = onNavigate,
                )
            }
        }
    }
}

@Composable
private fun RowScope.LiquidGlassNavItem(
    item: NavItem,
    isSelected: Boolean,
    pendingCount: Int,
    reduceMotion: Boolean,
    onNavigate: (String) -> Unit,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val pressed by interactionSource.collectIsPressedAsState()
    val scope = rememberCoroutineScope()
    val tapGlow = remember { Animatable(0f) }
    val primaryColor = Primary
    val color by animateColorAsState(
        targetValue = if (isSelected) primaryColor else Muted,
        label = "dock-color-${item.route}",
    )
    val iconScale by animateFloatAsState(
        targetValue = if (isSelected && !reduceMotion) 1.08f else 1f,
        animationSpec = spring(
            stiffness = if (reduceMotion) 10_000f else 620f,
            dampingRatio = .78f,
        ),
        label = "dock-icon-scale-${item.route}",
    )
    val pressScale by animateFloatAsState(
        targetValue = if (pressed && !reduceMotion) .96f else 1f,
        animationSpec = tween(140),
        label = "dock-press-scale-${item.route}",
    )
    val itemShape = RoundedCornerShape(27.dp)

    Box(
        modifier = Modifier
            .weight(1f)
            .fillMaxHeight()
            .padding(horizontal = 2.dp)
            .graphicsLayer {
                scaleX = pressScale
                scaleY = pressScale
            }
            .clickable(
                interactionSource = interactionSource,
                indication = null,
                role = Role.Tab,
            ) {
                if (!reduceMotion) {
                    scope.launch {
                        tapGlow.snapTo(1f)
                        tapGlow.animateTo(
                            0f,
                            animationSpec = tween(540, easing = FastOutSlowInEasing),
                        )
                    }
                }
                onNavigate(item.route)
            },
        contentAlignment = Alignment.Center,
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(54.dp)
                .clip(itemShape)
                .background(
                    if (isSelected) Color.White.copy(alpha = .66f) else Color.Transparent,
                )
                .drawBehind {
                    val activeGlow = if (isSelected) .9f else 0f
                    val flashGlow = tapGlow.value
                    if (activeGlow > 0f || flashGlow > 0f) {
                        drawRoundRect(
                            brush = Brush.radialGradient(
                                colors = listOf(
                                    primaryColor.copy(alpha = .28f * activeGlow + .34f * flashGlow),
                                    primaryColor.copy(alpha = .10f * activeGlow + .16f * flashGlow),
                                    Color.Transparent,
                                ),
                                center = Offset(size.width / 2f, size.height / 2f),
                                radius = size.width * .82f,
                            ),
                            cornerRadius = CornerRadius(size.height / 2f),
                        )
                    }
                }
                .border(
                    width = if (isSelected) 1.dp else 0.dp,
                    color = Color.White.copy(alpha = if (isSelected) .78f else 0f),
                    shape = itemShape,
                ),
            contentAlignment = Alignment.Center,
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Box(
                    modifier = Modifier.height(27.dp).width(42.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        imageVector = item.icon,
                        contentDescription = item.label,
                        tint = color,
                        modifier = Modifier
                            .size(21.dp)
                            .graphicsLayer {
                                scaleX = iconScale
                                scaleY = iconScale
                            },
                    )
                    if (item.route == "tasks" && pendingCount > 0) {
                        Box(
                            modifier = Modifier
                                .align(Alignment.TopEnd)
                                .size(16.dp)
                                .clip(CircleShape)
                                .background(UnreadDot),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(
                                text = pendingCount.coerceAtMost(9).toString(),
                                color = Color.White,
                                fontSize = 8.sp,
                                fontWeight = FontWeight.Bold,
                            )
                        }
                    }
                }
                Spacer(Modifier.height(2.dp))
                Text(
                    text = item.label,
                    color = color,
                    fontSize = 10.sp,
                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                )
            }
        }
    }
}

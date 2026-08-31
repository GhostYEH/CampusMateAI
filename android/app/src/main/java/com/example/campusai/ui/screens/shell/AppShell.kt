package com.example.campusai.ui.screens.shell

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.os.Build
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
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.AssignmentTurnedIn
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.sp
import androidx.navigation.NavHostController
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.core.view.WindowCompat
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.PulseEffect
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.system.systemBarPolicy
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import com.example.campusai.ui.theme.UnreadDot
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.HazeStyle
import dev.chrisbanes.haze.haze
import dev.chrisbanes.haze.hazeChild

data class NavItem(val route: String, val label: String, val icon: ImageVector)

/**
 * Bottom dock visible height reserved on top of the system navigation bar.
 * Equals 76dp (dock row) + 6dp (top padding) + 10dp (bottom padding).
 * Screens that draw content above the dock (FABs, lists' bottom contentPadding)
 * should add this height to their own bottom insets.
 */
val BottomDockReservedHeight = 76.dp + 6.dp + 10.dp

internal fun floatingDockContentBottomPadding(navigationBarHeight: Dp): Dp =
    navigationBarHeight + BottomDockReservedHeight

val studentNavItems = listOf(
    NavItem("home", "首页", Icons.Default.Home),
    NavItem("courses", "课程", Icons.Default.MenuBook),
    NavItem("tasks", "待办", Icons.Default.AssignmentTurnedIn),
    NavItem("counselor", "CPM", Icons.Default.SmartToy),
    NavItem("profile", "我的", Icons.Default.Person),
)

private val studentProfileRoutes = setOf(
    "profile",
    "settings",
    "account",
    "files",
    "favorites",
    "university",
    "academic",
    "edu_system",
    "edu_schedule",
    "edu_login",
    "help-feedback",
)

internal fun selectedStudentDockRoute(route: String): String = when {
    route == "community" -> "home"
    route == "lostfound" -> "counselor"
    route in studentProfileRoutes -> "profile"
    else -> route
}



@Composable
fun AppShell(
    navController: NavHostController,
    repository: AppRepository,
    content: @Composable () -> Unit,
) {
    val session by repository.session.collectAsStateWithLifecycle()
    val pendingCount by repository.pendingCount.collectAsStateWithLifecycle()
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    val darkMode by repository.darkMode.collectAsStateWithLifecycle()
    val navItems = studentNavItems.take(5)
    val hazeState = remember { HazeState() }
    val backStack by navController.currentBackStackEntryAsState()
    // destination.route may contain query parameters; compare its base route.
    val route = (backStack?.destination?.route ?: "home").substringBefore('?').substringBefore('/')
    val view = LocalView.current
    val systemBarPolicy = systemBarPolicy(
        route = route,
        darkTheme = darkMode,
        authenticated = true,
    )

    SideEffect {
        view.context.findActivity()?.let { activity ->
            WindowCompat.getInsetsController(activity.window, view).apply {
                isAppearanceLightStatusBars = systemBarPolicy.darkStatusBarIcons
                isAppearanceLightNavigationBars = systemBarPolicy.darkNavigationBarIcons
            }
        }
    }

    Box(Modifier.fillMaxSize()) {
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
            Modifier
                .fillMaxSize()
                .haze(
                    state = hazeState,
                    style = HazeStyle(
                        tint = Background.copy(alpha = .16f),
                        blurRadius = 8.dp,
                        noiseFactor = .04f,
                    ),
                )
                .background(Background),
        ) {
            content()
        }
        CampusDock(
            modifier = Modifier
                .align(Alignment.BottomCenter),
            hazeState = hazeState,
            items = navItems,
            route = route,
            pendingCount = pendingCount,
            reduceMotion = reduceMotion,
            darkMode = darkMode,
            onNavigate = { target ->
                navController.navigate(target) {
                    popUpTo("home") { inclusive = false }
                    launchSingleTop = true
                }
            },
        )
    }
}

private tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
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
                if (role == "student") "知" else "管",
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
    hazeState: HazeState,
    items: List<NavItem>,
    route: String,
    pendingCount: Int,
    reduceMotion: Boolean,
    darkMode: Boolean,
    onNavigate: (String) -> Unit,
) {
    val selectedRoute = selectedStudentDockRoute(route)
    val primaryColor = Primary
    val dockSurface = Surface
    val dockLine = Line
    val glassProfile = liquidGlassDockProfile(Build.VERSION.SDK_INT, darkMode)
    val interactionProfile = liquidGlassDockInteractionProfile(reduceMotion)
    val dockShape = RoundedCornerShape(38.dp)
    val dockGlassModifier = if (glassProfile.blurEnabled) {
        Modifier.hazeChild(
            state = hazeState,
            shape = dockShape,
            style = HazeStyle(
                tint = dockSurface.copy(alpha = glassProfile.surfaceAlpha),
                blurRadius = glassProfile.blurRadiusDp.dp,
                noiseFactor = .08f,
            ),
        )
    } else {
        Modifier
            .clip(dockShape)
            .background(dockSurface.copy(alpha = glassProfile.surfaceAlpha))
    }
    Box(
        modifier = modifier
            .fillMaxWidth()
            .navigationBarsPadding()
            .padding(start = 14.dp, top = 6.dp, end = 14.dp, bottom = 10.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(80.dp)
                .shadow(
                    elevation = 18.dp,
                    shape = dockShape,
                    clip = false,
                )
                .then(dockGlassModifier)
                .drawBehind {
                    drawRoundRect(
                        color = Color.White.copy(alpha = if (darkMode) .04f else .12f),
                        cornerRadius = CornerRadius(size.height / 2f),
                    )
                    drawCircle(
                        brush = Brush.radialGradient(
                            colors = listOf(dockSurface.copy(alpha = .54f), Color.Transparent),
                            center = Offset(0f, 0f),
                            radius = size.width * .62f,
                        ),
                        radius = size.width * .62f,
                        center = Offset(0f, 0f),
                    )
                    drawCircle(
                        brush = Brush.radialGradient(
                            colors = listOf(
                                primaryColor.copy(
                                    alpha = if (glassProfile.vibrancyEnabled) .12f else .07f,
                                ),
                                Color.Transparent,
                            ),
                            center = Offset(size.width, size.height),
                            radius = size.width * .52f,
                        ),
                        radius = size.width * .52f,
                        center = Offset(size.width, size.height),
                    )
                }
                .border(0.8.dp, dockLine.copy(alpha = .58f), dockShape)
                .padding(horizontal = 7.dp, vertical = 7.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            items.forEach { item ->
                val selected = selectedRoute == item.route
                LiquidGlassNavItem(
                    glassProfile = glassProfile,
                    interactionProfile = interactionProfile,
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
    glassProfile: LiquidGlassDockProfile,
    interactionProfile: LiquidGlassDockInteractionProfile,
    item: NavItem,
    isSelected: Boolean,
    pendingCount: Int,
    reduceMotion: Boolean,
    onNavigate: (String) -> Unit,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val pressed by interactionSource.collectIsPressedAsState()
    val pressWaveProgress = remember { Animatable(1f) }
    val primaryColor = Primary
    val primarySoftColor = PrimarySoft
    val color by animateColorAsState(
        targetValue = if (isSelected) primaryColor else Muted,
        animationSpec = tween(260, easing = FastOutSlowInEasing),
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
        targetValue = if (pressed) interactionProfile.pressScale else 1f,
        animationSpec = tween(140),
        label = "dock-press-scale-${item.route}",
    )
    LaunchedEffect(pressed, interactionProfile.pressWaveEnabled) {
        if (!interactionProfile.pressWaveEnabled) {
            pressWaveProgress.snapTo(if (pressed) 0f else 1f)
        } else if (pressed) {
            pressWaveProgress.snapTo(0f)
            pressWaveProgress.animateTo(
                targetValue = 1f,
                animationSpec = tween(
                    durationMillis = interactionProfile.pressWaveDurationMillis,
                    easing = FastOutSlowInEasing,
                ),
            )
        } else if (pressWaveProgress.value < 1f) {
            pressWaveProgress.animateTo(
                targetValue = 1f,
                animationSpec = tween(180, easing = FastOutSlowInEasing),
            )
        }
    }
    val itemShape = RoundedCornerShape(27.dp)
    val selectedGlassModifier = if (isSelected) {
        Modifier.drawBehind {
            val pressBoost = if (pressed && !reduceMotion) .12f else 0f
            drawRoundRect(
                brush = Brush.linearGradient(
                    colors = listOf(
                        Color.White.copy(alpha = .34f + pressBoost),
                        primarySoftColor.copy(alpha = if (glassProfile.lensEnabled) .48f else .70f),
                        primaryColor.copy(alpha = .16f + pressBoost),
                    ),
                ),
                cornerRadius = CornerRadius(size.height / 2f),
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color.White.copy(alpha = .26f), Color.Transparent),
                    center = Offset(size.width * .28f, size.height * .18f),
                    radius = size.width * .72f,
                ),
                radius = size.width * .72f,
                center = Offset(size.width * .28f, size.height * .18f),
            )
            drawRoundRect(
                brush = Brush.linearGradient(
                    colors = listOf(
                        Color.White.copy(alpha = .72f),
                        primaryColor.copy(alpha = .24f),
                        Color.White.copy(alpha = .18f),
                    ),
                ),
                cornerRadius = CornerRadius(size.height / 2f),
                style = Stroke(width = (if (pressed) 1.4.dp else .8.dp).toPx()),
            )
        }
    } else {
        Modifier
    }

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
                onNavigate(item.route)
            },
        contentAlignment = Alignment.Center,
    ) {
        Box(
            modifier = selectedGlassModifier
                .fillMaxWidth()
                .height(58.dp)
                .clip(itemShape)
                .drawBehind {
                    val activeGlow = if (isSelected) .9f else 0f
                    if (activeGlow > 0f) {
                        drawRoundRect(
                            brush = Brush.radialGradient(
                                colors = listOf(
                                    primaryColor.copy(alpha = .28f * activeGlow),
                                    primaryColor.copy(alpha = .10f * activeGlow),
                                    Color.Transparent,
                                ),
                                center = Offset(size.width / 2f, size.height / 2f),
                                radius = size.width * .82f,
                            ),
                            cornerRadius = CornerRadius(size.height / 2f),
                        )
                    }
                    if (!interactionProfile.pressWaveEnabled && pressed) {
                        drawRoundRect(
                            color = primaryColor.copy(alpha = .11f),
                            cornerRadius = CornerRadius(size.height / 2f),
                        )
                    }
                    val waveProgress = pressWaveProgress.value
                    if (interactionProfile.pressWaveEnabled && waveProgress < 1f) {
                        val waveAlpha = (1f - waveProgress) * .34f
                        val waveRadius = interactionProfile.pressWaveRadiusDp.dp.toPx() *
                            (.22f + .78f * waveProgress)
                        val center = Offset(size.width / 2f, size.height / 2f)
                        drawCircle(
                            brush = Brush.radialGradient(
                                colors = listOf(
                                    primaryColor.copy(alpha = waveAlpha * .48f),
                                    primaryColor.copy(alpha = waveAlpha * .16f),
                                    Color.Transparent,
                                ),
                                center = center,
                                radius = waveRadius,
                            ),
                            radius = waveRadius,
                            center = center,
                        )
                        drawCircle(
                            color = Color.White.copy(alpha = waveAlpha),
                            radius = waveRadius,
                            center = center,
                            style = Stroke(width = 1.2.dp.toPx()),
                        )
                    }
                }
                .border(
                    width = if (isSelected) 1.dp else 0.dp,
                    color = Primary.copy(alpha = if (isSelected) .3f else 0f),
                    shape = itemShape,
                ),
            contentAlignment = Alignment.Center,
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Box(
                    modifier = Modifier.height(29.dp).width(42.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        imageVector = item.icon,
                        contentDescription = item.label,
                        tint = color,
                        modifier = Modifier
                            .size(if (item.route == "counselor" && isSelected) 24.dp else 21.dp)
                            .graphicsLayer {
                                scaleX = iconScale
                                scaleY = iconScale
                            },
                    )
                    if (item.route == "tasks" && pendingCount > 0) {
                        Box(
                            modifier = Modifier
                                .align(Alignment.TopEnd)
                                .size(18.dp)
                                .clip(CircleShape)
                                .background(UnreadDot),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(
                                text = if (pendingCount > 9) "9+" else pendingCount.toString(),
                                color = Color.White,
                                fontSize = 7.sp,
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

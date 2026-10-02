package com.example.campusai.ui.screens.dashboard

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AssignmentTurnedIn
import androidx.compose.material.icons.filled.ArrowForwardIos
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.campusai.R
import com.example.campusai.data.repository.AppRepository
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.PI
import kotlin.math.sin

private val WorldInk = Color(0xFF142A35)
private val StudyAmber = Color(0xFFF0C37A)
private val LibraryViolet = Color(0xFFB5C9D8)
private val GrowthGreen = Color(0xFFB6D4B7)

/** A navigable campus scene. The illustration contains no baked-in controls or text. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ModernDashboardScreen(repository: AppRepository, onNavigate: (String) -> Unit) {
    var showMore by remember { mutableStateOf(false) }
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    var pendingRoute by remember { mutableStateOf<String?>(null) }
    val drift = if (reduceMotion) 0f else {
        val transition = rememberInfiniteTransition(label = "campus-camera")
        val position by transition.animateFloat(
            initialValue = -1f, targetValue = 1f,
            animationSpec = infiniteRepeatable(tween(14000, easing = LinearEasing), RepeatMode.Reverse),
            label = "slow-drift",
        )
        position
    }
    val arrival by animateFloatAsState(
        targetValue = if (pendingRoute == null || reduceMotion) 0f else 1f,
        animationSpec = tween(260), label = "destination-approach",
    )
    fun enter(route: String) {
        if (pendingRoute != null) return
        if (reduceMotion) { onNavigate(route); return }
        pendingRoute = route
        scope.launch {
            delay(270)
            onNavigate(route)
            pendingRoute = null
        }
    }

    BoxWithConstraints(Modifier.fillMaxSize().clipToBounds().background(WorldInk)) {
        val sceneWidth = maxWidth
        val sceneHeight = maxHeight
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
            Box(Modifier.fillMaxWidth().height(sceneHeight).clipToBounds()) {
                WorldSceneImage(R.drawable.campus_world_study_library_v4, drift, arrival,
                    Modifier.fillMaxSize(), when (pendingRoute) {
                        "focus" -> TransformOrigin(.25f, .41f)
                        "courses" -> TransformOrigin(.76f, .42f)
                        else -> TransformOrigin(.5f, .57f)
                    })
                Box(Modifier.fillMaxWidth().height(sceneHeight * .21f).align(Alignment.TopCenter)
                    .background(Brush.verticalGradient(listOf(Color(0xD00B2030), Color.Transparent))))
                if (!reduceMotion) {
                    CampusAmbientLight()
                    CampusWalkers()
                }
                Row(
                    Modifier.fillMaxWidth().statusBarsPadding().padding(start = 22.dp, top = 20.dp, end = 18.dp),
                    verticalAlignment = Alignment.Top,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text("CampusMate", color = Color.White, fontSize = 30.sp, fontWeight = FontWeight.Bold)
                        Text("今天，学一点新东西", color = Color.White.copy(alpha = .91f), fontSize = 14.sp)
                    }
                    WorldIconButton(Icons.Default.Menu, "更多功能") { showMore = true }
                    Spacer(Modifier.width(8.dp))
                    WorldIconButton(Icons.Default.Person, "我的") { enter("profile") }
                }
                WorldArea("自习室", Modifier.align(Alignment.TopStart)
                    .offset(x = sceneWidth * .03f, y = sceneHeight * .27f)
                    .width(sceneWidth * .43f).height(sceneHeight * .25f)) { enter("focus") }
                WorldArea("图书馆", Modifier.align(Alignment.TopStart)
                    .offset(x = sceneWidth * .52f, y = sceneHeight * .24f)
                    .width(sceneWidth * .46f).height(sceneHeight * .29f)) { enter("courses") }
                WorldDestination("自习室", Icons.Default.Timer, StudyAmber,
                    Modifier.align(Alignment.TopStart).offset(x = sceneWidth * .06f, y = sceneHeight * .48f),
                    drift = drift, active = pendingRoute == "focus") { enter("focus") }
                WorldDestination("图书馆", Icons.Default.MenuBook, LibraryViolet,
                    Modifier.align(Alignment.TopStart).offset(x = sceneWidth * .53f, y = sceneHeight * .51f),
                    drift = drift, floatPhase = 1.3f, active = pendingRoute == "courses") { enter("courses") }
                Text("向上滑动 · 探索校园  ↓", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 22.dp)
                        .graphicsLayer { translationY = drift * 3.dp.toPx() }
                        .clip(CircleShape).background(Color(0xB0123038)).padding(horizontal = 15.dp, vertical = 8.dp))
            }
            Box(Modifier.fillMaxWidth().height(sceneHeight).clipToBounds()) {
                WorldSceneImage(R.drawable.campus_world_lower_v4, drift, arrival,
                    Modifier.fillMaxSize(), when (pendingRoute) {
                        "tasks" -> TransformOrigin(.24f, .30f)
                        "community" -> TransformOrigin(.75f, .34f)
                        "focus_history" -> TransformOrigin(.26f, .64f)
                        "profile" -> TransformOrigin(.78f, .64f)
                        else -> TransformOrigin(.5f, .5f)
                    })
                Box(Modifier.fillMaxWidth().height(sceneHeight * .08f).align(Alignment.TopCenter)
                    .background(Brush.verticalGradient(listOf(Color(0xAA102637), Color.Transparent))))
                if (!reduceMotion) {
                    CampusAmbientLight(lower = true)
                    CampusWalkers(lower = true)
                }
                WorldArea("待办", Modifier.align(Alignment.TopStart)
                    .offset(x = sceneWidth * .07f, y = sceneHeight * .18f)
                    .width(sceneWidth * .38f).height(sceneHeight * .27f)) { enter("tasks") }
                WorldArea("校园社区", Modifier.align(Alignment.TopStart)
                    .offset(x = sceneWidth * .52f, y = sceneHeight * .24f)
                    .width(sceneWidth * .45f).height(sceneHeight * .21f)) { enter("community") }
                WorldArea("学习足迹", Modifier.align(Alignment.TopStart)
                    .offset(x = sceneWidth * .04f, y = sceneHeight * .54f)
                    .width(sceneWidth * .44f).height(sceneHeight * .22f)) { enter("focus_history") }
                WorldArea("我的", Modifier.align(Alignment.TopStart)
                    .offset(x = sceneWidth * .55f, y = sceneHeight * .52f)
                    .width(sceneWidth * .43f).height(sceneHeight * .25f)) { enter("profile") }
                WorldDestination("待办", Icons.Default.AssignmentTurnedIn, StudyAmber,
                    Modifier.align(Alignment.TopStart).offset(x = sceneWidth * .07f, y = sceneHeight * .38f),
                    compact = true, drift = drift, active = pendingRoute == "tasks") { enter("tasks") }
                WorldDestination("校园社区", Icons.Default.Groups, LibraryViolet,
                    Modifier.align(Alignment.TopStart).offset(x = sceneWidth * .51f, y = sceneHeight * .42f),
                    compact = true, drift = drift, floatPhase = 1.1f, active = pendingRoute == "community") { enter("community") }
                WorldDestination("学习足迹", Icons.Default.History, GrowthGreen,
                    Modifier.align(Alignment.TopStart).offset(x = sceneWidth * .06f, y = sceneHeight * .67f),
                    compact = true, drift = drift, floatPhase = 2.2f, active = pendingRoute == "focus_history") { enter("focus_history") }
                WorldDestination("我的", Icons.Default.Person, LibraryViolet,
                    Modifier.align(Alignment.TopStart).offset(x = sceneWidth * .69f, y = sceneHeight * .70f),
                    compact = true, drift = drift, floatPhase = 3.3f, active = pendingRoute == "profile") { enter("profile") }
                WorldDestination("通知", Icons.Default.Notifications, StudyAmber,
                    Modifier.align(Alignment.TopStart).offset(x = sceneWidth * .37f, y = sceneHeight * .79f),
                    compact = true, drift = drift, floatPhase = 4.4f, active = pendingRoute == "notifications") { enter("notifications") }
            }
        }
    }

    if (showMore) {
        ModalBottomSheet(onDismissRequest = { showMore = false }, containerColor = Color(0xFFF9FBF6)) {
            Column(Modifier.fillMaxWidth().padding(start = 22.dp, end = 22.dp, bottom = 28.dp)) {
                Text("更多功能", color = WorldInk, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                Text("学习之外的校园事务，随时可以在这里找到", color = Color(0xFF637183), fontSize = 13.sp)
                Spacer(Modifier.size(18.dp))
                MoreDestination("待办事项", Icons.Default.AssignmentTurnedIn) { showMore = false; onNavigate("tasks") }
                HorizontalDivider()
                MoreDestination("校园社区", Icons.Default.Groups) { showMore = false; onNavigate("community") }
                HorizontalDivider()
                MoreDestination("校园通知", Icons.Default.Notifications) { showMore = false; onNavigate("notifications") }
                HorizontalDivider()
                MoreDestination("个人中心", Icons.Default.Person) { showMore = false; onNavigate("profile") }
            }
        }
    }
}

/** Independent scene layers keep camera drift separate from the tappable map landmarks. */
@Composable
private fun WorldSceneImage(
    drawable: Int,
    drift: Float,
    arrival: Float,
    modifier: Modifier,
    origin: TransformOrigin,
) {
    Image(
        painter = painterResource(drawable),
        contentDescription = null,
        contentScale = ContentScale.Crop,
        modifier = modifier.graphicsLayer {
            scaleX = 1.025f + arrival * .035f
            scaleY = 1.025f + arrival * .035f
            translationX = drift * 4.dp.toPx()
            translationY = drift * 2.dp.toPx()
            transformOrigin = origin
        },
    )
}

@Composable
private fun WorldArea(label: String, modifier: Modifier, onClick: () -> Unit) {
    Box(modifier.semantics { contentDescription = "进入$label" }.clickable(role = Role.Button, onClick = onClick))
}

@Composable
private fun WorldIconButton(icon: ImageVector, label: String, onClick: () -> Unit) {
    Box(
        Modifier.size(44.dp).shadow(9.dp, CircleShape).clip(CircleShape)
            .background(Brush.verticalGradient(listOf(Color(0xE9234550), Color(0xE813303D))))
            .border(1.dp, Color.White.copy(alpha = .42f), CircleShape)
            .semantics { contentDescription = label }
            .clickable(role = Role.Button, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, contentDescription = null, tint = Color.White, modifier = Modifier.size(23.dp))
    }
}

@Composable
private fun WorldDestination(
    label: String,
    icon: ImageVector,
    tint: Color,
    modifier: Modifier = Modifier,
    compact: Boolean = false,
    drift: Float = 0f,
    floatPhase: Float = 0f,
    active: Boolean = false,
    onClick: () -> Unit,
) {
    val approach by animateFloatAsState(if (active) 1f else 0f, tween(260), label = "marker-approach")
    Row(
        modifier.graphicsLayer {
            val bob = sin((drift + 1f) * PI.toFloat() + floatPhase) * 2.dp.toPx()
            translationY = bob - approach * 5.dp.toPx()
            scaleX = 1f + approach * .075f
            scaleY = 1f + approach * .075f
        }.shadow(12.dp, CircleShape).clip(CircleShape)
            .background(Brush.verticalGradient(listOf(Color(0xE81B3C46), Color(0xEB102B37))))
            .border(1.dp, tint.copy(alpha = if (active) .9f else .55f), CircleShape)
            .semantics { contentDescription = "进入$label" }
            .clickable(role = Role.Button, onClick = onClick)
            .padding(start = 5.dp, top = 5.dp, end = if (compact) 13.dp else 15.dp, bottom = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(if (compact) 32.dp else 39.dp).clip(CircleShape).background(tint.copy(alpha = .18f)), contentAlignment = Alignment.Center) {
            Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(if (compact) 17.dp else 21.dp))
        }
        Spacer(Modifier.width(if (compact) 7.dp else 10.dp))
        Text(label, color = Color.White, fontSize = if (compact) 13.sp else 16.sp, fontWeight = FontWeight.Bold)
        if (!compact) {
            Spacer(Modifier.width(7.dp))
            Icon(Icons.Default.ArrowForwardIos, null, tint = Color.White.copy(alpha = .75f), modifier = Modifier.size(12.dp))
        }
    }
}

/** One quiet pool of window light per destination, avoiding repeated decorative lamps. */
@Composable
private fun CampusAmbientLight(lower: Boolean = false) {
    val transition = rememberInfiniteTransition(label = "campus-window-light")
    val strength by transition.animateFloat(
        initialValue = .035f, targetValue = .065f,
        animationSpec = infiniteRepeatable(tween(4200, easing = LinearEasing), RepeatMode.Reverse),
        label = "window-breath",
    )
    Canvas(Modifier.fillMaxSize()) {
        val windows = if (lower) listOf(Offset(.22f, .30f), Offset(.82f, .62f))
            else listOf(Offset(.25f, .40f), Offset(.73f, .39f))
        windows.forEach { point ->
            val center = Offset(size.width * point.x, size.height * point.y)
            val radius = size.width * .16f
            drawCircle(
                brush = Brush.radialGradient(
                    listOf(Color(0xFFF7D79B).copy(alpha = strength), Color.Transparent),
                    center = center,
                    radius = radius,
                ),
                radius = radius,
                center = center,
            )
        }
    }
}

/** Tiny walkers follow the existing courtyard paths without shifting any controls. */
@Composable
private fun CampusWalkers(lower: Boolean = false) {
    val transition = rememberInfiniteTransition(label = "campus-walkers")
    val progress by transition.animateFloat(
        initialValue = 0f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(16000, easing = LinearEasing)),
        label = "walking-loop",
    )
    Canvas(Modifier.fillMaxSize()) {
        fun walker(from: Offset, to: Offset, phase: Float, coat: Color, curve: Float) {
            val p = (progress + phase) % 1f
            val opacity = (p / .08f).coerceAtMost(1f) * ((1f - p) / .12f).coerceAtMost(1f)
            val x = size.width * (from.x + (to.x - from.x) * p)
            val y = size.height * (from.y + (to.y - from.y) * p - curve * sin(PI.toFloat() * p))
            val step = sin(p * 72f) * 2.dp.toPx()
            val head = 3.dp.toPx()
            drawOval(Color.Black.copy(alpha = .22f * opacity), Offset(x - 6.dp.toPx(), y + 5.dp.toPx()), Size(12.dp.toPx(), 4.dp.toPx()))
            drawLine(Color(0xFF263841).copy(alpha = opacity), Offset(x - 2.dp.toPx(), y + 2.dp.toPx()), Offset(x - 2.dp.toPx() + step, y + 7.dp.toPx()), 2.dp.toPx(), cap = StrokeCap.Round)
            drawLine(Color(0xFF263841).copy(alpha = opacity), Offset(x + 2.dp.toPx(), y + 2.dp.toPx()), Offset(x + 2.dp.toPx() - step, y + 7.dp.toPx()), 2.dp.toPx(), cap = StrokeCap.Round)
            drawOval(coat.copy(alpha = opacity), Offset(x - 4.dp.toPx(), y - 6.dp.toPx()), Size(8.dp.toPx(), 10.dp.toPx()))
            drawCircle(Color(0xFFF0CAA6).copy(alpha = opacity), head, Offset(x, y - 8.dp.toPx()))
        }
        if (lower) {
            walker(Offset(.51f, .20f), Offset(.29f, .43f), .03f, Color(0xFF8298A4), .012f)
            walker(Offset(.48f, .42f), Offset(.72f, .67f), .51f, Color(0xFF987E72), -.018f)
        } else {
            walker(Offset(.48f, .83f), Offset(.43f, .57f), .04f, Color(0xFF6F91A0), .012f)
            walker(Offset(.53f, .76f), Offset(.74f, .49f), .47f, Color(0xFFB78365), .014f)
        }
    }
}

@Composable
private fun MoreDestination(label: String, icon: ImageVector, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).clickable(role = Role.Button, onClick = onClick)
            .padding(vertical = 15.dp, horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, null, tint = Color(0xFF677DE3), modifier = Modifier.size(22.dp))
        Spacer(Modifier.width(14.dp))
        Text(label, color = WorldInk, fontSize = 15.sp, fontWeight = FontWeight.Medium, modifier = Modifier.weight(1f))
        Icon(Icons.Default.ArrowForwardIos, null, tint = Color(0xFF8793A2), modifier = Modifier.size(13.dp))
    }
}

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
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AssignmentTurnedIn
import androidx.compose.material.icons.filled.ArrowForwardIos
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material3.Icon
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
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.imageResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
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
@Composable
fun ModernDashboardScreen(repository: AppRepository, onNavigate: (String) -> Unit) {
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
        val mapWidth = maxWidth
        val mapHeight = maxHeight * 1.52f
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
            Box(Modifier.fillMaxWidth().height(mapHeight).clipToBounds()) {
                WorldSceneImage(R.drawable.campus_world_continuous_v5, drift, arrival,
                    Modifier.fillMaxSize(), when (pendingRoute) {
                        "focus" -> TransformOrigin(.22f, .25f)
                        "courses" -> TransformOrigin(.78f, .24f)
                        "tasks" -> TransformOrigin(.20f, .43f)
                        "community" -> TransformOrigin(.78f, .48f)
                        "focus_history" -> TransformOrigin(.22f, .68f)
                        "profile" -> TransformOrigin(.79f, .72f)
                        else -> TransformOrigin.Center
                    })
                Box(Modifier.fillMaxWidth().height(mapHeight * .16f).align(Alignment.TopCenter)
                    .background(Brush.verticalGradient(listOf(Color(0xC80B2030), Color.Transparent))))
                CampusAmbientLight(enabled = !reduceMotion)
                CampusSpriteWalkers(animated = !reduceMotion)
                Row(
                    Modifier.fillMaxWidth().statusBarsPadding().padding(start = 22.dp, top = 20.dp, end = 18.dp),
                    verticalAlignment = Alignment.Top,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text("CampusMate", color = Color.White, fontSize = 30.sp, fontWeight = FontWeight.Bold)
                        Text("今天，学一点新东西", color = Color.White.copy(alpha = .91f), fontSize = 14.sp)
                    }
                    WorldIconButton(Icons.Default.Person, "我的") { enter("profile") }
                }
                WorldArea("自习室", Modifier.align(Alignment.TopStart)
                    .offset(x = mapWidth * .01f, y = mapHeight * .16f)
                    .width(mapWidth * .44f).height(mapHeight * .16f)) { enter("focus") }
                WorldArea("图书馆", Modifier.align(Alignment.TopStart)
                    .offset(x = mapWidth * .53f, y = mapHeight * .12f)
                    .width(mapWidth * .45f).height(mapHeight * .21f)) { enter("courses") }
                WorldArea("待办", Modifier.align(Alignment.TopStart)
                    .offset(x = mapWidth * .02f, y = mapHeight * .36f)
                    .width(mapWidth * .38f).height(mapHeight * .17f)) { enter("tasks") }
                WorldArea("校园社区", Modifier.align(Alignment.TopStart)
                    .offset(x = mapWidth * .58f, y = mapHeight * .43f)
                    .width(mapWidth * .40f).height(mapHeight * .14f)) { enter("community") }
                WorldArea("学习足迹", Modifier.align(Alignment.TopStart)
                    .offset(x = mapWidth * .02f, y = mapHeight * .58f)
                    .width(mapWidth * .40f).height(mapHeight * .16f)) { enter("focus_history") }
                WorldArea("我的", Modifier.align(Alignment.TopStart)
                    .offset(x = mapWidth * .61f, y = mapHeight * .62f)
                    .width(mapWidth * .37f).height(mapHeight * .18f)) { enter("profile") }
                WorldDestination("自习室", Icons.Default.Timer, StudyAmber,
                    Modifier.align(Alignment.TopStart).offset(x = mapWidth * .04f, y = mapHeight * .30f),
                    drift = drift, active = pendingRoute == "focus") { enter("focus") }
                WorldDestination("图书馆", Icons.Default.MenuBook, LibraryViolet,
                    Modifier.align(Alignment.TopStart).offset(x = mapWidth * .57f, y = mapHeight * .31f),
                    drift = drift, floatPhase = 1.3f, active = pendingRoute == "courses") { enter("courses") }
                WorldDestination("待办", Icons.Default.AssignmentTurnedIn, StudyAmber,
                    Modifier.align(Alignment.TopStart).offset(x = mapWidth * .04f, y = mapHeight * .50f),
                    compact = true, drift = drift, active = pendingRoute == "tasks") { enter("tasks") }
                WorldDestination("校园社区", Icons.Default.Groups, LibraryViolet,
                    Modifier.align(Alignment.TopStart).offset(x = mapWidth * .52f, y = mapHeight * .53f),
                    compact = true, drift = drift, floatPhase = 1.1f, active = pendingRoute == "community") { enter("community") }
                WorldDestination("学习足迹", Icons.Default.History, GrowthGreen,
                    Modifier.align(Alignment.TopStart).offset(x = mapWidth * .05f, y = mapHeight * .71f),
                    compact = true, drift = drift, floatPhase = 2.2f, active = pendingRoute == "focus_history") { enter("focus_history") }
                WorldDestination("通知", Icons.Default.Notifications, StudyAmber,
                    Modifier.align(Alignment.TopStart).offset(x = mapWidth * .40f, y = mapHeight * .65f),
                    compact = true, drift = drift, floatPhase = 4.4f, active = pendingRoute == "notifications") { enter("notifications") }
                WorldDestination("我的", Icons.Default.Person, LibraryViolet,
                    Modifier.align(Alignment.TopStart).offset(x = mapWidth * .72f, y = mapHeight * .77f),
                    compact = true, drift = drift, floatPhase = 3.3f, active = pendingRoute == "profile") { enter("profile") }
                Text("上滑探索校园  ↓", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.align(Alignment.TopCenter).offset(y = maxHeight * .86f)
                        .graphicsLayer { translationY = drift * 3.dp.toPx() }
                        .clip(CircleShape).background(Color(0xB0123038)).padding(horizontal = 15.dp, vertical = 8.dp))
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

/** Restrained window light stays separate from the map artwork. */
@Composable
private fun CampusAmbientLight(enabled: Boolean) {
    if (!enabled) return
    val transition = rememberInfiniteTransition(label = "campus-window-light")
    val strength by transition.animateFloat(
        initialValue = .035f, targetValue = .065f,
        animationSpec = infiniteRepeatable(tween(4200, easing = LinearEasing), RepeatMode.Reverse),
        label = "window-breath",
    )
    Canvas(Modifier.fillMaxSize()) {
        listOf(Offset(.25f, .24f), Offset(.75f, .23f)).forEach { point ->
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

/** Actual character frames move along the paths; the background contains no fixed people. */
@Composable
private fun CampusSpriteWalkers(animated: Boolean) {
    val studentA = ImageBitmap.imageResource(R.drawable.campus_walk_student_a)
    val studentB = ImageBitmap.imageResource(R.drawable.campus_walk_student_b)
    val progress = if (animated) {
        val transition = rememberInfiniteTransition(label = "campus-sprite-walkers")
        val position by transition.animateFloat(
            initialValue = 0f, targetValue = 1f,
            animationSpec = infiniteRepeatable(tween(14000, easing = LinearEasing)),
            label = "walking-loop",
        )
        position
    } else 0f
    Canvas(Modifier.fillMaxSize()) {
        fun walker(sprite: ImageBitmap, from: Offset, to: Offset, phase: Float, staticPosition: Float) {
            val p = if (animated) (progress + phase) % 1f else staticPosition
            val opacity = if (animated) minOf(1f, p / .08f, (1f - p) / .08f) else 1f
            val x = size.width * (from.x + (to.x - from.x) * p)
            val y = size.height * (from.y + (to.y - from.y) * p)
            val frame = if (animated) ((progress * 72).toInt() + (phase * 4).toInt()) % 4 else 0
            val frameWidth = sprite.width / 4
            val widthPx = 26.dp.toPx().toInt()
            val heightPx = 35.dp.toPx().toInt()
            drawOval(Color.Black.copy(alpha = .18f * opacity), Offset(x - 6.dp.toPx(), y - 2.dp.toPx()), Size(12.dp.toPx(), 4.dp.toPx()))
            drawImage(
                image = sprite,
                srcOffset = IntOffset(frame * frameWidth, 0),
                srcSize = IntSize(frameWidth, sprite.height),
                dstOffset = IntOffset(x.toInt() - widthPx / 2, y.toInt() - heightPx + 4.dp.toPx().toInt()),
                dstSize = IntSize(widthPx, heightPx),
                alpha = opacity,
            )
        }
        walker(studentA, Offset(.48f, .32f), Offset(.53f, .53f), .08f, .36f)
        walker(studentB, Offset(.49f, .55f), Offset(.60f, .76f), .52f, .59f)
    }
}

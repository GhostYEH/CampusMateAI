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
import androidx.compose.material.icons.filled.ArrowForwardIos
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.SmartToy
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
        Image(
            painter = painterResource(R.drawable.campus_world_scene_v2),
            contentDescription = null,
            contentScale = ContentScale.Crop,
            modifier = Modifier.fillMaxSize().graphicsLayer {
                scaleX = 1.045f + drift * .008f + arrival * .055f
                scaleY = 1.045f + drift * .008f + arrival * .055f
                translationX = drift * 6.dp.toPx()
                translationY = drift * 3.dp.toPx()
                transformOrigin = when (pendingRoute) {
                    "focus" -> TransformOrigin(.36f, .43f)
                    "courses" -> TransformOrigin(.79f, .52f)
                    "focus_history" -> TransformOrigin(.22f, .72f)
                    else -> TransformOrigin.Center
                }
            },
        )
        Box(
            Modifier.fillMaxWidth().height(maxHeight * .19f).align(Alignment.TopCenter)
                .background(Brush.verticalGradient(listOf(Color(0xB30B2334), Color.Transparent))),
        )
        Box(
            Modifier.fillMaxWidth().height(maxHeight * .23f).align(Alignment.BottomCenter)
                .background(Brush.verticalGradient(listOf(Color.Transparent, Color(0xB70A1F2A)))),
        )
        if (!reduceMotion) CampusWalkers()

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
            WorldIconButton(Icons.Default.Person, "我的") { onNavigate("profile") }
        }

        // Buildings are touch targets too; the visible chips are not the only way in.
        WorldArea(
            "自习室", Modifier.align(Alignment.TopStart)
                .offset(x = maxWidth * .04f, y = maxHeight * .29f)
                .width(maxWidth * .53f).height(maxHeight * .25f),
        ) { enter("focus") }
        WorldArea(
            "图书馆", Modifier.align(Alignment.TopStart)
                .offset(x = maxWidth * .59f, y = maxHeight * .43f)
                .width(maxWidth * .41f).height(maxHeight * .26f),
        ) { enter("courses") }
        WorldArea(
            "学习足迹", Modifier.align(Alignment.TopStart)
                .offset(x = 0.dp, y = maxHeight * .63f)
                .width(maxWidth * .47f).height(maxHeight * .18f),
        ) { enter("focus_history") }
        WorldArea(
            "问小伴", Modifier.align(Alignment.TopStart)
                .offset(x = maxWidth * .42f, y = maxHeight * .59f)
                .width(maxWidth * .18f).height(maxHeight * .11f),
        ) { enter("counselor") }

        WorldDestination(
            label = "自习室", icon = Icons.Default.Timer, tint = StudyAmber,
            modifier = Modifier.align(Alignment.TopStart)
                .offset(x = maxWidth * .13f, y = maxHeight * .335f),
        ) { enter("focus") }
        WorldDestination(
            label = "图书馆", icon = Icons.Default.MenuBook, tint = LibraryViolet,
            modifier = Modifier.align(Alignment.TopStart)
                .offset(x = maxWidth * .59f, y = maxHeight * .49f),
        ) { enter("courses") }
        WorldDestination(
            label = "学习足迹", icon = Icons.Default.History, tint = GrowthGreen,
            modifier = Modifier.align(Alignment.TopStart)
                .offset(x = 18.dp, y = maxHeight * .66f),
        ) { enter("focus_history") }
        WorldDestination(
            label = "问小伴", icon = Icons.Default.SmartToy, tint = LibraryViolet, compact = true,
            modifier = Modifier.align(Alignment.TopStart)
                .offset(x = maxWidth * .54f, y = maxHeight * .635f),
        ) { enter("counselor") }

        Row(
            Modifier.align(Alignment.BottomCenter).navigationBarsPadding()
                .padding(start = 34.dp, end = 34.dp, bottom = 30.dp)
                .fillMaxWidth()
                .shadow(18.dp, CircleShape).clip(CircleShape)
                .background(Brush.horizontalGradient(listOf(Color(0xFF285C65), Color(0xFF1A3849))))
                .border(1.dp, Color.White.copy(alpha = .34f), CircleShape)
                .clickable(role = Role.Button) { enter("focus") }
                .padding(vertical = 15.dp),
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(Icons.Default.AutoAwesome, null, tint = Color.White, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(10.dp))
            Text("开始学习", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.width(10.dp))
            Icon(Icons.Default.ArrowForwardIos, null, tint = Color.White, modifier = Modifier.size(14.dp))
        }
    }

    if (showMore) {
        ModalBottomSheet(onDismissRequest = { showMore = false }, containerColor = Color(0xFFF9FBF6)) {
            Column(Modifier.fillMaxWidth().padding(start = 22.dp, end = 22.dp, bottom = 28.dp)) {
                Text("更多功能", color = WorldInk, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                Text("学习之外的校园事务，随时可以在这里找到", color = Color(0xFF637183), fontSize = 13.sp)
                Spacer(Modifier.size(18.dp))
                MoreDestination("待办事项", Icons.Default.Timer) { showMore = false; onNavigate("tasks") }
                HorizontalDivider()
                MoreDestination("校园通知", Icons.Default.Notifications) { showMore = false; onNavigate("notifications") }
                HorizontalDivider()
                MoreDestination("个人中心", Icons.Default.Person) { showMore = false; onNavigate("profile") }
            }
        }
    }
}

@Composable
private fun WorldArea(label: String, modifier: Modifier, onClick: () -> Unit) {
    Box(modifier.semantics { contentDescription = "进入$label" }.clickable(role = Role.Button, onClick = onClick))
}

@Composable
private fun WorldIconButton(icon: ImageVector, label: String, onClick: () -> Unit) {
    Box(
        Modifier.size(44.dp).clip(CircleShape).background(Color(0xAA102C38))
            .border(1.dp, Color.White.copy(alpha = .32f), CircleShape)
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
    onClick: () -> Unit,
) {
    Row(
        modifier.shadow(10.dp, CircleShape).clip(CircleShape).background(Color(0xDA112F3A))
            .border(1.dp, Color.White.copy(alpha = .34f), CircleShape)
            .semantics { contentDescription = "进入$label" }
            .clickable(role = Role.Button, onClick = onClick)
            .padding(start = 5.dp, top = 5.dp, end = if (compact) 13.dp else 15.dp, bottom = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(if (compact) 32.dp else 39.dp).clip(CircleShape).background(Color.White.copy(alpha = .12f)), contentAlignment = Alignment.Center) {
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

/** Tiny walkers follow the existing courtyard paths without shifting any controls. */
@Composable
private fun CampusWalkers() {
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
        walker(Offset(.48f, .73f), Offset(.45f, .51f), .04f, Color(0xFF6F91A0), .02f)
        walker(Offset(.54f, .74f), Offset(.80f, .58f), .39f, Color(0xFFB78365), .025f)
        walker(Offset(.46f, .77f), Offset(.23f, .69f), .72f, Color(0xFF8C9F73), -.012f)
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

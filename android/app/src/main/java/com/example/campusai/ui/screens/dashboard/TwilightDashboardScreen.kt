package com.example.campusai.ui.screens.dashboard

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.Apps
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.campusai.R
import com.example.campusai.data.repository.AppRepository
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private val ink = Color(0xFF101F3F)
private val cream = Color(0xFFFFEBCB)
private val archDestinations = listOf(
    "社区" to "community",
    "学习足迹" to "focus_history",
    "待办" to "tasks",
    "CPM" to "counselor",
    "我的" to "profile",
)
private val campusDestinations = listOf(
    "图书馆" to "courses",
    "自习室" to "focus",
    "互动课堂" to "classroom-hub",
) + archDestinations

/** Keep the illustration intact; motion only introduces the scene and acknowledges taps. */
@Composable
fun TwilightDashboardScreen(repository: AppRepository, onNavigate: (String) -> Unit) {
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    var pendingRoute by remember { mutableStateOf<String?>(null) }
    var entrancePlayed by rememberSaveable { mutableStateOf(false) }
    var showDestinations by rememberSaveable { mutableStateOf(false) }
    val entrance = remember { Animatable(if (entrancePlayed || reduceMotion) 1f else 0f) }
    LaunchedEffect(reduceMotion) {
        if (reduceMotion || entrancePlayed) {
            entrance.snapTo(1f)
            entrancePlayed = true
        } else {
            entrance.snapTo(0f)
            delay(80)
            entrance.animateTo(1f, tween(850))
            entrancePlayed = true
        }
    }
    val entranceProgress = if (reduceMotion) 1f else entrance.value
    val titleReveal = ((entranceProgress - .12f) / .45f).coerceIn(0f, 1f)
    fun enter(route: String) {
        if (pendingRoute != null) return
        if (reduceMotion) { onNavigate(route); return }
        pendingRoute = route
        scope.launch { delay(170); onNavigate(route); pendingRoute = null }
    }

    BoxWithConstraints(Modifier.fillMaxSize().background(ink)) {
        val width = maxWidth
        val sceneHeight = width * (1870f / 841f)
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
            Box(Modifier.fillMaxWidth().height(sceneHeight).clipToBounds()) {
                SceneLayer(R.drawable.campus_twilight_original, Modifier.fillMaxSize().graphicsLayer {
                    val scale = 1f + .018f * (1f - entranceProgress)
                    scaleX = scale
                    scaleY = scale
                })
                Box(Modifier.fillMaxWidth().height(sceneHeight * .20f).align(Alignment.TopCenter)
                    .background(Brush.verticalGradient(listOf(Color(0xA5101E3A), Color.Transparent))))
                Column(Modifier.fillMaxWidth().statusBarsPadding().padding(start = 24.dp, end = 24.dp, top = 18.dp)
                    .graphicsLayer {
                        alpha = titleReveal
                        translationY = (1f - titleReveal) * 6.dp.toPx()
                    }) {
                    Text("CampusMate", color = Color.White, fontSize = 30.sp, fontWeight = FontWeight.Bold)
                    Text("沿着灯光，走进今天的学习", color = cream, fontSize = 14.sp)
                }
                LandmarkArea("二楼图书馆", x = width * .11f, y = sceneHeight * .19f,
                    width = width * .39f, height = sceneHeight * .20f,
                    signText = "图书馆", signAlignment = Alignment.BottomEnd,
                    active = pendingRoute == "courses", reduceMotion = reduceMotion) { enter("courses") }
                LandmarkArea("一楼自习室", x = width * .10f, y = sceneHeight * .39f,
                    width = width * .40f, height = sceneHeight * .15f,
                    signText = "自习室", signAlignment = Alignment.BottomStart,
                    active = pendingRoute == "focus", reduceMotion = reduceMotion) { enter("focus") }
                LandmarkArea("互动课堂", x = width * .58f, y = sceneHeight * .38f,
                    width = width * .42f, height = sceneHeight * .28f,
                    signText = "互动课堂", signAlignment = Alignment.TopStart,
                    active = pendingRoute == "classroom-hub", reduceMotion = reduceMotion) { enter("classroom-hub") }
                archDestinations.forEachIndexed { index, (label, route) ->
                    val x = width * (.065f + index * .19f)
                    ArchDestination(label, x = x, y = sceneHeight * .835f,
                        width = width * .18f, height = sceneHeight * .087f,
                        labelReveal = ((entranceProgress - (.42f + index * .07f)) / .22f).coerceIn(0f, 1f),
                        active = pendingRoute == route, reduceMotion = reduceMotion) {
                        enter(route)
                    }
                }
            }
        }
        val shortcutShape = RoundedCornerShape(12.dp)
        Row(
            Modifier.align(Alignment.BottomEnd).safeDrawingPadding().padding(16.dp)
                .heightIn(min = 48.dp).clip(shortcutShape)
                .background(ink.copy(alpha = .96f))
                .border(1.dp, cream.copy(alpha = .45f), shortcutShape)
                .clickable(enabled = pendingRoute == null, role = Role.Button) { showDestinations = true }
                .padding(horizontal = 14.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Icon(Icons.Default.Apps, contentDescription = null, tint = cream, modifier = Modifier.size(18.dp))
            Text("全部入口", color = cream, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
        }
    }
    if (showDestinations) {
        CampusDestinationsDialog(onClose = { showDestinations = false }) { route ->
            showDestinations = false
            enter(route)
        }
    }
}

@Composable
private fun CampusDestinationsDialog(onClose: () -> Unit, onNavigate: (String) -> Unit) {
    Dialog(onDismissRequest = onClose) {
        Surface(
            shape = RoundedCornerShape(20.dp),
            color = ink,
            contentColor = cream,
            border = BorderStroke(1.dp, cream.copy(alpha = .28f)),
        ) {
            Column(Modifier.fillMaxWidth().padding(14.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        "全部入口",
                        modifier = Modifier.weight(1f).padding(start = 10.dp),
                        fontSize = 20.sp,
                        fontWeight = FontWeight.Bold,
                    )
                    Box(
                        Modifier.size(48.dp).clip(CircleShape).background(cream.copy(alpha = .12f))
                            .clickable(role = Role.Button, onClick = onClose),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(Icons.Default.Close, contentDescription = "关闭", tint = cream)
                    }
                }
                Column(
                    Modifier.weight(1f, fill = false).verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    campusDestinations.forEach { (label, route) ->
                        Row(
                            Modifier.fillMaxWidth().heightIn(min = 48.dp)
                                .clip(RoundedCornerShape(10.dp))
                                .background(cream.copy(alpha = .08f))
                                .clickable(role = Role.Button) { onNavigate(route) }
                                .padding(horizontal = 12.dp, vertical = 9.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(label, modifier = Modifier.weight(1f), fontSize = 15.sp)
                            Icon(
                                Icons.AutoMirrored.Filled.ArrowForward,
                                contentDescription = null,
                                tint = cream.copy(alpha = .7f),
                                modifier = Modifier.size(18.dp),
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SceneLayer(drawable: Int, modifier: Modifier) {
    Image(painterResource(drawable), null, modifier = modifier, contentScale = ContentScale.FillBounds)
}

@Composable
private fun LandmarkArea(
    label: String, x: Dp, y: Dp, width: Dp, height: Dp,
    signText: String, signAlignment: Alignment,
    active: Boolean, reduceMotion: Boolean, onClick: () -> Unit,
) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val pop by animateFloatAsState(if (!reduceMotion && (pressed || active)) 1f else 0f,
        tween(220), label = "$label-touch")
    Box(Modifier.offset(x, y).width(width).height(height).clip(RoundedCornerShape(24.dp))
        .background(Brush.radialGradient(listOf(cream.copy(alpha = .18f * pop), Color.Transparent)))
        .border(1.dp, cream.copy(alpha = .65f * pop), RoundedCornerShape(24.dp))
        .semantics { contentDescription = "进入$label" }
        .clickable(interactionSource = interaction, indication = null, role = Role.Button, onClick = onClick)) {
        Text(signText, Modifier.align(signAlignment).padding(8.dp)
            .clip(RoundedCornerShape(3.dp))
            .background(ink.copy(alpha = .72f + .12f * pop))
            .border(.5.dp, cream.copy(alpha = .34f + .3f * pop), RoundedCornerShape(3.dp))
            .padding(horizontal = 7.dp, vertical = 3.dp),
            color = cream, fontSize = 11.sp, fontWeight = FontWeight.Medium,
            letterSpacing = .5.sp)
    }
}

@Composable
private fun ArchDestination(
    label: String, x: Dp, y: Dp, width: Dp, height: Dp,
    labelReveal: Float, active: Boolean, reduceMotion: Boolean, onClick: () -> Unit,
) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val pop by animateFloatAsState(if (!reduceMotion && (pressed || active)) 1f else 0f,
        tween(220), label = "$label-arch")
    val shape = RoundedCornerShape(topStart = 36.dp, topEnd = 36.dp, bottomStart = 8.dp, bottomEnd = 8.dp)
    Box(Modifier.offset(x, y).width(width).height(height)
        .clip(shape)
        .border(1.dp, cream.copy(alpha = .72f * pop), shape)
        .semantics { contentDescription = "打开$label" }
        .clickable(interactionSource = interaction, indication = null, role = Role.Button, onClick = onClick)) {
        Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(
            cream.copy(alpha = .12f * pop), Color.Transparent))))
        Text(label, Modifier.align(Alignment.BottomCenter).padding(bottom = 5.dp)
            .graphicsLayer {
                alpha = labelReveal
                translationY = (1f - labelReveal) * 4.dp.toPx()
            }.clip(RoundedCornerShape(8.dp)).background(ink.copy(alpha = .58f + .15f * pop))
            .padding(horizontal = 5.dp),
            color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Bold)
    }
}

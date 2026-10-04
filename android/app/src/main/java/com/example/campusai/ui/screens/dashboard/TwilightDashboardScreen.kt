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
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.TransformOrigin
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
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.campusai.R
import com.example.campusai.data.repository.AppRepository
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.random.Random

private val ink = Color(0xFF101F3F)
private val cream = Color(0xFFFFEBCB)

/** Separate sky, ground and architecture layers leave the destinations accessible. */
@Composable
fun TwilightDashboardScreen(repository: AppRepository, onNavigate: (String) -> Unit) {
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    var pendingRoute by remember { mutableStateOf<String?>(null) }
    val transition = rememberInfiniteTransition(label = "campus-breeze")
    val drift by transition.animateFloat(-1f, 1f,
        infiniteRepeatable(tween(8500, easing = LinearEasing), RepeatMode.Reverse), label = "cloud-drift")
    val leafSway by transition.animateFloat(-1f, 1f,
        infiniteRepeatable(tween(3400), RepeatMode.Reverse), label = "leaf-sway")
    var lampTarget by remember { mutableFloatStateOf(0f) }
    val lampSway by animateFloatAsState(lampTarget, tween(850), label = "pendant-sway")
    var dimPendant by remember { mutableStateOf(false) }
    var dimPath by remember { mutableStateOf(false) }
    val pendantShade by animateFloatAsState(if (dimPendant && !reduceMotion) .58f else 0f,
        tween(650), label = "pendant-dim")
    val pathShade by animateFloatAsState(if (dimPath && !reduceMotion) .55f else 0f,
        tween(800), label = "path-dim")
    LaunchedEffect(reduceMotion) {
        if (reduceMotion) return@LaunchedEffect
        while (true) {
            delay(Random.nextLong(11000, 21000)); dimPendant = true
            delay(Random.nextLong(1500, 2700)); dimPendant = false
            delay(Random.nextLong(8000, 17000)); dimPath = true
            delay(Random.nextLong(1300, 2200)); dimPath = false
        }
    }
    LaunchedEffect(reduceMotion) {
        if (reduceMotion) { lampTarget = 0f; return@LaunchedEffect }
        while (true) {
            delay(Random.nextLong(7000, 16000))
            lampTarget = -1f; delay(850)
            lampTarget = 1f; delay(850)
            lampTarget = -.45f; delay(850)
            lampTarget = 0f
        }
    }
    fun enter(route: String) {
        if (pendingRoute != null) return
        if (reduceMotion) { onNavigate(route); return }
        pendingRoute = route
        scope.launch { delay(330); onNavigate(route); pendingRoute = null }
    }

    BoxWithConstraints(Modifier.fillMaxSize().background(ink)) {
        val width = maxWidth
        val sceneHeight = width * (1870f / 841f)
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
            Box(Modifier.fillMaxWidth().height(sceneHeight).clipToBounds()) {
                if (reduceMotion) {
                    SceneLayer(R.drawable.campus_twilight_original, Modifier.fillMaxSize())
                } else {
                    SceneLayer(R.drawable.campus_twilight_sky, Modifier.fillMaxSize().graphicsLayer {
                        scaleX = 1.075f; scaleY = 1.02f
                        translationX = drift * 18.dp.toPx(); translationY = drift * 3.dp.toPx()
                    })
                    SceneLayer(R.drawable.campus_twilight_ground, Modifier.fillMaxSize())
                    SceneLayer(R.drawable.campus_twilight_buildings, Modifier.fillMaxSize())
                    SceneLayer(R.drawable.campus_twilight_lights, Modifier.fillMaxSize().graphicsLayer {
                        alpha = .12f + (drift + 1f) * .11f
                    })
                    SceneLayer(R.drawable.campus_twilight_pendants, Modifier.fillMaxSize().graphicsLayer {
                        transformOrigin = TransformOrigin(.25f, .19f)
                        rotationZ = lampSway * 2f
                    })
                    SceneLayer(R.drawable.campus_twilight_leaves, Modifier.fillMaxSize().graphicsLayer {
                        transformOrigin = TransformOrigin(.05f, .98f)
                        rotationZ = leafSway * .65f
                        translationX = leafSway * 1.5.dp.toPx()
                    })
                    LightShade(Modifier.offset(x = width * .12f, y = sceneHeight * .225f)
                        .width(width * .27f).height(sceneHeight * .11f), pendantShade)
                    LightShade(Modifier.offset(x = width * .235f, y = sceneHeight * .66f)
                        .width(width * .11f).height(sceneHeight * .07f), pathShade)
                }
                Box(Modifier.fillMaxWidth().height(sceneHeight * .20f).align(Alignment.TopCenter)
                    .background(Brush.verticalGradient(listOf(Color(0xA5101E3A), Color.Transparent))))
                Column(Modifier.fillMaxWidth().statusBarsPadding().padding(start = 24.dp, end = 24.dp, top = 18.dp)) {
                    Text("CampusMate", color = Color.White, fontSize = 30.sp, fontWeight = FontWeight.Bold)
                    Text("沿着灯光，走进今天的学习", color = cream, fontSize = 14.sp)
                }
                LandmarkArea("二楼图书馆", x = width * .11f, y = sceneHeight * .19f,
                    width = width * .39f, height = sceneHeight * .20f,
                    sceneWidth = width, sceneHeight = sceneHeight,
                    active = pendingRoute == "courses", reduceMotion = reduceMotion) { enter("courses") }
                LandmarkArea("一楼自习室", x = width * .10f, y = sceneHeight * .39f,
                    width = width * .40f, height = sceneHeight * .15f,
                    sceneWidth = width, sceneHeight = sceneHeight,
                    active = pendingRoute == "focus", reduceMotion = reduceMotion) { enter("focus") }
                LandmarkArea("互动课堂", x = width * .58f, y = sceneHeight * .38f,
                    width = width * .42f, height = sceneHeight * .28f,
                    sceneWidth = width, sceneHeight = sceneHeight,
                    active = pendingRoute == "classroom-hub", reduceMotion = reduceMotion) { enter("classroom-hub") }
                val archLabels = listOf("社区", "学习足迹", "待办", "CPM", "我的")
                val archRoutes = listOf("community", "focus_history", "tasks", "counselor", "profile")
                archLabels.forEachIndexed { index, label ->
                    val x = width * (.065f + index * .19f)
                    ArchDestination(label, x = x, y = sceneHeight * .835f,
                        width = width * .18f, height = sceneHeight * .087f,
                        sceneWidth = width, sceneHeight = sceneHeight,
                        active = pendingRoute == archRoutes[index], reduceMotion = reduceMotion) {
                        enter(archRoutes[index])
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
private fun LightShade(modifier: Modifier, alpha: Float) {
    Box(modifier.graphicsLayer { this.alpha = alpha }.background(Brush.radialGradient(
        listOf(Color(0xCC0C1B33), Color(0x770C1B33), Color.Transparent))))
}

@Composable
private fun LandmarkArea(
    label: String, x: Dp, y: Dp, width: Dp, height: Dp,
    sceneWidth: Dp, sceneHeight: Dp, active: Boolean, reduceMotion: Boolean, onClick: () -> Unit,
) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val pop by animateFloatAsState(if (!reduceMotion && (pressed || active)) 1f else 0f,
        tween(220), label = "$label-touch")
    Box(Modifier.offset(x, y).width(width).height(height).graphicsLayer {
        transformOrigin = TransformOrigin(.5f, 1f)
        translationY = -5.dp.toPx() * pop
        scaleX = 1f + .025f * pop
        scaleY = 1f + .025f * pop
        rotationY = 2.5f * pop
    }.clip(RoundedCornerShape(24.dp))
        .background(Brush.radialGradient(listOf(cream.copy(alpha = .35f * pop), Color.Transparent)))
        .border(2.dp, cream.copy(alpha = .72f * pop), RoundedCornerShape(24.dp))
        .semantics { contentDescription = "进入$label" }
        .clickable(interactionSource = interaction, indication = null, role = Role.Button, onClick = onClick)) {
        if (pop > .01f) Image(painterResource(R.drawable.campus_twilight_buildings), null,
            Modifier.wrapContentSize(unbounded = true, align = Alignment.TopStart)
                .offset(-x, -y).requiredWidth(sceneWidth).requiredHeight(sceneHeight)
                .graphicsLayer { alpha = pop }, contentScale = ContentScale.FillBounds)
        if (pop > .01f) Text(label, Modifier.align(Alignment.BottomCenter).padding(bottom = 12.dp)
            .clip(RoundedCornerShape(8.dp)).background(ink.copy(alpha = .8f)).padding(horizontal = 6.dp, vertical = 3.dp),
            color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun ArchDestination(
    label: String, x: Dp, y: Dp, width: Dp, height: Dp,
    sceneWidth: Dp, sceneHeight: Dp, active: Boolean, reduceMotion: Boolean, onClick: () -> Unit,
) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val pop by animateFloatAsState(if (!reduceMotion && (pressed || active)) 1f else 0f,
        tween(220), label = "$label-arch")
    val shape = RoundedCornerShape(topStart = 36.dp, topEnd = 36.dp, bottomStart = 8.dp, bottomEnd = 8.dp)
    Box(Modifier.offset(x, y).width(width).height(height)
        .graphicsLayer {
            transformOrigin = TransformOrigin(.5f, 1f)
            translationY = -6.dp.toPx() * pop
            scaleX = 1f + .045f * pop
            scaleY = 1f + .075f * pop
            rotationX = -4f * pop
        }
        .shadow(if (pop > .01f) 11.dp else 0.dp, shape)
        .clip(shape)
        .border(2.dp, cream.copy(alpha = .85f * pop), shape)
        .semantics { contentDescription = "打开$label" }
        .clickable(interactionSource = interaction, indication = null, role = Role.Button, onClick = onClick)) {
        // The exact segment is repainted above the original so only this arch rises.
        Image(painterResource(R.drawable.campus_twilight_original), null,
            Modifier.wrapContentSize(unbounded = true, align = Alignment.TopStart)
                .offset(-x, -y).requiredWidth(sceneWidth).requiredHeight(sceneHeight),
            contentScale = ContentScale.FillBounds)
        Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(
            cream.copy(alpha = .22f * pop), Color.Transparent))))
        Text(label, Modifier.align(Alignment.BottomCenter).padding(bottom = 5.dp)
            .clip(RoundedCornerShape(8.dp)).background(ink.copy(alpha = .58f + .25f * pop))
            .padding(horizontal = 5.dp),
            color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Bold)
    }
}

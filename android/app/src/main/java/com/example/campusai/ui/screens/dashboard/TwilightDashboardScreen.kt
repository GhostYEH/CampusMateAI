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
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AssignmentTurnedIn
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.School
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
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

private val ink = Color(0xFF101F3F)
private val cream = Color(0xFFFFEBCB)

/** Separate sky, ground and architecture layers leave the destinations accessible. */
@Composable
fun TwilightDashboardScreen(repository: AppRepository, onNavigate: (String) -> Unit) {
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    var pendingRoute by remember { mutableStateOf<String?>(null) }
    val drift = if (reduceMotion) 0f else {
        val transition = rememberInfiniteTransition(label = "twilight-sky")
        val value by transition.animateFloat(-1f, 1f,
            infiniteRepeatable(tween(18000, easing = LinearEasing), RepeatMode.Reverse), label = "cloud-drift")
        value
    }
    val arrival by animateFloatAsState(if (pendingRoute == null || reduceMotion) 0f else 1f,
        tween(280), label = "landmark-arrival")
    fun enter(route: String) {
        if (pendingRoute != null) return
        if (reduceMotion) { onNavigate(route); return }
        pendingRoute = route
        scope.launch { delay(290); onNavigate(route); pendingRoute = null }
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
                        scaleX = 1.025f; scaleY = 1.012f
                        translationX = drift * 5.dp.toPx(); translationY = drift * 2.dp.toPx()
                    })
                    SceneLayer(R.drawable.campus_twilight_ground, Modifier.fillMaxSize())
                    SceneLayer(R.drawable.campus_twilight_buildings, Modifier.fillMaxSize().graphicsLayer {
                        scaleX = 1f + arrival * .015f; scaleY = 1f + arrival * .015f
                        translationY = drift * .7.dp.toPx()
                    })
                    SceneLayer(R.drawable.campus_twilight_lights, Modifier.fillMaxSize().graphicsLayer {
                        alpha = .12f + (drift + 1f) * .11f
                    })
                }
                Box(Modifier.fillMaxWidth().height(sceneHeight * .20f).align(Alignment.TopCenter)
                    .background(Brush.verticalGradient(listOf(Color(0xA5101E3A), Color.Transparent))))
                Column(Modifier.fillMaxWidth().statusBarsPadding().padding(start = 24.dp, end = 24.dp, top = 18.dp)) {
                    Text("CampusMate", color = Color.White, fontSize = 30.sp, fontWeight = FontWeight.Bold)
                    Text("沿着灯光，走进今天的学习", color = cream, fontSize = 14.sp)
                }
                LandmarkArea("二楼图书馆", Modifier.offset(x = width * .11f, y = sceneHeight * .19f)
                    .width(width * .39f).height(sceneHeight * .20f)) { enter("courses") }
                LandmarkArea("一楼自习室", Modifier.offset(x = width * .10f, y = sceneHeight * .39f)
                    .width(width * .40f).height(sceneHeight * .15f)) { enter("focus") }
                LandmarkArea("互动课堂", Modifier.offset(x = width * .58f, y = sceneHeight * .38f)
                    .width(width * .42f).height(sceneHeight * .28f)) { enter("classroom-hub") }
                LandmarkChip("2F 图书馆", Icons.Default.MenuBook,
                    Modifier.offset(x = width * .10f, y = sceneHeight * .36f)) { enter("courses") }
                LandmarkChip("1F 自习室", Icons.Default.Timer,
                    Modifier.offset(x = width * .10f, y = sceneHeight * .51f)) { enter("focus") }
                LandmarkChip("互动课堂", Icons.Default.School,
                    Modifier.offset(x = width * .60f, y = sceneHeight * .64f)) { enter("classroom-hub") }
                Row(Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(horizontal = 16.dp, vertical = 20.dp)
                    .clip(RoundedCornerShape(22.dp)).background(Color(0xE9152947))
                    .border(1.dp, cream.copy(alpha = .36f), RoundedCornerShape(22.dp)).padding(vertical = 12.dp),
                    horizontalArrangement = Arrangement.SpaceEvenly) {
                    BottomDestination("待办", Icons.Default.AssignmentTurnedIn) { enter("tasks") }
                    BottomDestination("社区", Icons.Default.Groups) { enter("community") }
                    BottomDestination("通知", Icons.Default.Notifications) { enter("notifications") }
                    BottomDestination("我的", Icons.Default.Person) { enter("profile") }
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
private fun LandmarkArea(label: String, modifier: Modifier, onClick: () -> Unit) {
    Box(modifier.semantics { contentDescription = "进入$label" }.clickable(role = Role.Button, onClick = onClick))
}

@Composable
private fun LandmarkChip(label: String, icon: ImageVector, modifier: Modifier, onClick: () -> Unit) {
    Row(modifier.clip(RoundedCornerShape(18.dp)).background(Color(0xDA172D4C))
        .border(1.dp, cream.copy(alpha = .65f), RoundedCornerShape(18.dp))
        .semantics { contentDescription = "进入$label" }.clickable(role = Role.Button, onClick = onClick)
        .padding(horizontal = 11.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = cream, modifier = Modifier.size(17.dp))
        Spacer(Modifier.width(6.dp))
        Text(label, color = Color.White, fontWeight = FontWeight.SemiBold, fontSize = 12.sp)
    }
}

@Composable
private fun BottomDestination(label: String, icon: ImageVector, onClick: () -> Unit) {
    Column(Modifier.clip(RoundedCornerShape(12.dp)).clickable(role = Role.Button, onClick = onClick)
        .padding(horizontal = 8.dp, vertical = 3.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(icon, contentDescription = label, tint = cream, modifier = Modifier.size(20.dp))
        Spacer(Modifier.height(4.dp))
        Text(label, color = Color.White, fontSize = 11.sp)
    }
}

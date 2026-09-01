package com.example.campusai.ui.screens.focus

import androidx.annotation.DrawableRes
import androidx.compose.animation.Crossfade
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.VolumeOff
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Landscape
import androidx.compose.material3.Icon
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.R
import com.example.campusai.data.focus.scene.FocusAmbientAudioController
import com.example.campusai.data.focus.scene.FocusAmbientPolicy
import com.example.campusai.data.focus.scene.FocusScene
import com.example.campusai.data.focus.scene.FocusSceneSettings
import com.example.campusai.data.focus.voice.FocusVoicePhase
import com.example.campusai.ui.glass.CampusGlassRole
import com.example.campusai.ui.glass.CampusGlassScene
import com.example.campusai.ui.glass.campusGlass
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.TextPrimary

private data class FocusSceneVisuals(
    @param:DrawableRes val backgroundRes: Int,
    val scrim: Color,
)

private fun FocusScene.visuals(): FocusSceneVisuals = when (this) {
    FocusScene.RAINY_ROOM -> FocusSceneVisuals(
        backgroundRes = R.drawable.focus_scene_rainy_room,
        scrim = Color(0xFF132B46),
    )
    FocusScene.QUIET_LIBRARY -> FocusSceneVisuals(
        backgroundRes = R.drawable.focus_scene_quiet_library,
        scrim = Color(0xFF382A32),
    )
    FocusScene.FOREST_MORNING -> FocusSceneVisuals(
        backgroundRes = R.drawable.focus_scene_forest_morning,
        scrim = Color(0xFF163B32),
    )
}

/**
 * Keeps companion content outside the background transition. Changing scenes therefore never
 * recreates the robot's animation state or interrupts an in-flight voice status animation.
 */
@Composable
internal fun FocusSceneStage(
    scene: FocusScene,
    modifier: Modifier = Modifier,
    robotContent: @Composable BoxScope.() -> Unit,
    content: @Composable BoxScope.() -> Unit = {},
) {
    CampusGlassScene(
        darkMode = true,
        modifier = modifier,
        background = { FocusSceneBackdrop(scene) },
    ) {
        Box(Modifier.fillMaxSize()) {
            robotContent()
            content()
        }
    }
}

@Composable
private fun FocusSceneBackdrop(scene: FocusScene) {
    Crossfade(
        targetState = scene,
        animationSpec = tween(durationMillis = 520),
        label = "focus-scene-crossfade",
    ) { activeScene ->
        val visuals = activeScene.visuals()
        Box(Modifier.fillMaxSize()) {
            Image(
                painter = painterResource(visuals.backgroundRes),
                contentDescription = null,
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Crop,
            )
            Box(
                Modifier
                    .fillMaxSize()
                    .background(
                        Brush.verticalGradient(
                            0f to visuals.scrim.copy(alpha = .35f),
                            .34f to Color.Transparent,
                            .7f to Color.Black.copy(alpha = .12f),
                            1f to Color.Black.copy(alpha = .58f),
                        ),
                    ),
            )
        }
    }
}

@Composable
internal fun FocusGlassPanel(
    modifier: Modifier = Modifier,
    tint: Color = Color.White.copy(alpha = .48f),
    content: @Composable BoxScope.() -> Unit,
) {
    Box(
        modifier = modifier.campusGlass(
            shape = RoundedCornerShape(26.dp),
            role = CampusGlassRole.PANEL,
            tint = tint,
        ),
        content = content,
    )
}

@Composable
internal fun FocusSceneToolbar(
    settings: FocusSceneSettings,
    onSettingsChange: (FocusSceneSettings) -> Unit,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }
    FocusGlassPanel(
        modifier = modifier
            .fillMaxWidth()
            .animateContentSize(),
        tint = Color.White.copy(alpha = .54f),
    ) {
        Column(
            Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp)
                    .clip(RoundedCornerShape(16.dp))
                    .clickable { expanded = !expanded }
                    .padding(horizontal = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(
                    Modifier
                        .size(38.dp)
                        .background(Primary.copy(alpha = .12f), CircleShape),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(Icons.Default.Landscape, contentDescription = null, tint = Primary)
                }
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(settings.scene.title, color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                    Text(settings.scene.subtitle, color = Muted, fontSize = 11.sp)
                }
                Icon(
                    if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                    contentDescription = if (expanded) "收起场景选择" else "选择专注场景",
                    tint = Primary,
                )
            }

            if (expanded) {
                Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    FocusScene.entries.forEach { scene ->
                        val selected = scene == settings.scene
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(56.dp)
                                .clip(RoundedCornerShape(16.dp))
                                .background(if (selected) Primary.copy(alpha = .11f) else Color.Transparent)
                                .clickable {
                                    onSettingsChange(settings.copy(scene = scene))
                                    expanded = false
                                }
                                .padding(horizontal = 12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(scene.title, color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                                Text(scene.subtitle, color = Muted, fontSize = 11.sp)
                            }
                            if (selected) Icon(Icons.Default.Check, contentDescription = "当前场景", tint = Primary)
                        }
                    }
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    if (settings.ambientEnabled) Icons.AutoMirrored.Filled.VolumeUp else Icons.AutoMirrored.Filled.VolumeOff,
                    contentDescription = null,
                    tint = Primary,
                )
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text("环境声", color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                    Text(if (settings.ambientEnabled) "随场景播放，AI 说话时自动降低" else "默认关闭，可随时开启", color = Muted, fontSize = 11.sp)
                }
                Switch(
                    checked = settings.ambientEnabled,
                    onCheckedChange = { onSettingsChange(settings.copy(ambientEnabled = it)) },
                    modifier = Modifier.semantics { contentDescription = "环境声开关" },
                )
            }
            if (settings.ambientEnabled) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("音量", color = Muted, fontSize = 11.sp)
                    Spacer(Modifier.width(10.dp))
                    Slider(
                        value = settings.volume,
                        onValueChange = { onSettingsChange(settings.copy(volume = it)) },
                        valueRange = 0.08f..0.65f,
                        modifier = Modifier
                            .weight(1f)
                            .semantics { contentDescription = "环境声音量" },
                    )
                }
            }
        }
    }
}

@Composable
internal fun FocusAmbientPlaybackEffect(
    settings: FocusSceneSettings,
    sessionRunning: Boolean,
    appForeground: Boolean,
    phase: FocusVoicePhase,
) {
    val context = LocalContext.current
    val controller = remember(context) { FocusAmbientAudioController(context) }

    LaunchedEffect(controller, settings.scene) {
        controller.setScene(settings.scene)
    }
    LaunchedEffect(controller, settings, sessionRunning, appForeground, phase) {
        controller.setTargetVolume(
            FocusAmbientPolicy.targetVolume(
                settings = settings,
                sessionRunning = sessionRunning,
                appForeground = appForeground,
                phase = phase,
            ),
        )
    }
    DisposableEffect(controller) {
        onDispose(controller::release)
    }
}

package com.example.campusai.ui.components

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.unit.dp
import com.example.campusai.ui.theme.CampusMotion
import com.example.campusai.ui.theme.LocalReduceMotion
import com.example.campusai.ui.theme.Primary
import kotlin.math.cos
import kotlin.math.sin

private data class AmbientOrb(
    val x: Float,
    val y: Float,
    val radius: Float,
    val phase: Float,
    val color: Color,
)

private val ambientOrbs = listOf(
    AmbientOrb(.08f, .16f, 5f, .0f, Color(0xFF5B68F2)),
    AmbientOrb(.22f, .09f, 3f, 1.4f, Color(0xFF7DC8FF)),
    AmbientOrb(.84f, .13f, 6f, 2.1f, Color(0xFF8D84FF)),
    AmbientOrb(.94f, .30f, 3f, 3.2f, Color(0xFF5B68F2)),
    AmbientOrb(.06f, .54f, 4f, 4.3f, Color(0xFFFFB078)),
    AmbientOrb(.91f, .64f, 5f, 5.1f, Color(0xFF7DC8FF)),
    AmbientOrb(.16f, .82f, 3f, 6.0f, Color(0xFF8D84FF)),
    AmbientOrb(.82f, .88f, 4f, 6.8f, Color(0xFF5B68F2)),
)

/**
 * A low-contrast ambient constellation shared by every authenticated page.
 * It is deliberately drawn at the edge of the viewport so it adds depth
 * without competing with text, cards, or touch targets.
 */
@Composable
fun CampusAmbientField(
    modifier: Modifier = Modifier,
    darkMode: Boolean = false,
    enabled: Boolean = true,
) {
    val reduceMotion = LocalReduceMotion.current
    val primaryColor = Primary
    if (!enabled) return
    val motion = rememberInfiniteTransition(label = "ambient-field")
    val phase = motion.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(5200, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "ambient-phase",
    ).value
    Canvas(modifier = modifier) {
        val opacity = CampusMotion.ambientOpacity(reduceMotion)
        if (opacity <= 0f) return@Canvas
        val drift = CampusMotion.parallaxAmplitude(reduceMotion, size.minDimension * .012f)
        val points = ambientOrbs.map { orb ->
            val orbit = orb.phase + phase * 1.35f
            Offset(
                x = size.width * orb.x + cos(orbit.toDouble()).toFloat() * drift,
                y = size.height * orb.y + sin(orbit.toDouble()).toFloat() * drift,
            )
        }
        val lineColor = if (darkMode) Color.White else primaryColor
        drawConstellation(points, lineColor.copy(alpha = opacity * .32f))
        ambientOrbs.forEachIndexed { index, orb ->
            val pulse = .82f + .18f * sin((orb.phase + phase * 2.2f).toDouble()).toFloat()
            drawOrb(points[index], orb.radius * pulse, orb.color, opacity)
        }
    }
}

private fun DrawScope.drawConstellation(points: List<Offset>, color: Color) {
    listOf(0 to 1, 1 to 2, 2 to 3, 3 to 5, 4 to 6, 5 to 7, 6 to 7).forEach { (from, to) ->
        drawLine(color, points[from], points[to], strokeWidth = 1.dp.toPx())
    }
}

private fun DrawScope.drawOrb(center: Offset, radius: Float, color: Color, opacity: Float) {
    drawCircle(
        brush = Brush.radialGradient(
            colors = listOf(color.copy(alpha = opacity), color.copy(alpha = opacity * .18f), Color.Transparent),
            center = center,
            radius = radius * 5.5f,
        ),
        radius = radius * 5.5f,
        center = center,
    )
    drawCircle(color.copy(alpha = opacity * 1.5f), radius = radius, center = center)
    drawCircle(Color.White.copy(alpha = opacity * .62f), radius = radius * .24f, center = center)
}

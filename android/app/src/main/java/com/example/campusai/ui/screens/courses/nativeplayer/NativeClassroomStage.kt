package com.example.campusai.ui.screens.courses.nativeplayer

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Spacer
import androidx.compose.runtime.Composable
import androidx.compose.runtime.State
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.draw.drawWithCache
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.unit.dp
import com.example.campusai.ui.screens.courses.ClassroomAmber
import com.example.campusai.ui.screens.courses.ClassroomStageBackdrop
import com.example.campusai.ui.theme.CampusMotion
import com.example.campusai.ui.theme.LocalReduceMotion
import com.example.campusai.ui.theme.Primary
import kotlin.math.abs
import kotlin.math.sin

@Composable
internal fun NativeClassroomStage(
    pageTurn: State<Float>,
    teacherSpeaking: Boolean,
    landscape: Boolean,
    modifier: Modifier = Modifier,
) {
    val reduceMotion = LocalReduceMotion.current
    val light = animateFloatAsState(
        if (teacherSpeaking) 1f else 0f,
        animationSpec = if (reduceMotion) snap() else tween(420, easing = CampusMotion.settleEasing),
        label = "classroom light",
    )
    Box(modifier.clipToBounds()) {
        ClassroomStageBackdrop(Modifier.matchParentSize().graphicsLayer {
            val turn = if (reduceMotion) 0f else pageTurn.value
            val scale = 1f + abs(turn) * .025f
            scaleX = scale
            scaleY = scale
            translationX = -size.width * .011f * turn
        })
        Spacer(Modifier.matchParentSize().drawWithCache {
            val lamp = Offset(size.width * if (landscape) .38f else .66f, size.height * .11f)
            val stageCenter = Offset(size.width * if (landscape) .36f else .50f, size.height * .72f)
            val beams = List(8) { layer ->
                val spread = .5f + layer * .07f
                val crown = size.minDimension * .07f * spread
                val base = size.width * .4f * spread
                Path().apply {
                    moveTo(lamp.x - crown, lamp.y)
                    lineTo(lamp.x + crown, lamp.y)
                    lineTo(stageCenter.x + base, stageCenter.y)
                    lineTo(stageCenter.x - base, stageCenter.y)
                    close()
                }
            }
            val beamLight = Brush.verticalGradient(
                0f to Color.Transparent,
                .16f to ClassroomAmber.copy(alpha = .32f),
                .55f to ClassroomAmber.copy(alpha = .10f),
                1f to Color.Transparent,
                startY = lamp.y,
                endY = stageCenter.y,
            )
            val glowRadius = (size.minDimension * .64f).coerceAtLeast(1f)
            val lampGlow = Brush.radialGradient(
                colors = listOf(ClassroomAmber.copy(alpha = .38f), Color.Transparent),
                center = lamp,
                radius = glowRadius,
            )
            val floorShade = Brush.verticalGradient(
                colors = listOf(Color.Transparent, Color(0x96101B27)),
                startY = stageCenter.y,
                endY = size.height,
            )
            onDrawBehind {
                drawRect(floorShade)
                for (beam in beams) drawPath(beam, brush = beamLight, alpha = .073f + light.value * .047f)
                drawCircle(lampGlow, radius = glowRadius, center = lamp, alpha = .30f + light.value * .30f)
            }
        })
    }
}

internal fun Modifier.classroomPageTurn(progress: State<Float>): Modifier = graphicsLayer {
    val turn = progress.value
    val depth = abs(turn)
    cameraDistance = size.maxDimension.coerceAtLeast(1f) * 1.8f
    rotationY = -turn * 11f
    rotationX = depth * 3f
    translationX = turn * 14.dp.toPx()
    translationY = depth * 5.dp.toPx()
    scaleX = 1f - depth * .055f
    scaleY = scaleX
}

@Composable
internal fun ClassroomTeacherSignal(modifier: Modifier = Modifier) {
    val reduceMotion = LocalReduceMotion.current
    val pulse = if (reduceMotion) null else rememberInfiniteTransition(label = "classroom speech").animateFloat(
        initialValue = 0f,
        targetValue = 2f * Math.PI.toFloat(),
        animationSpec = infiniteRepeatable(tween(920, easing = LinearEasing)),
        label = "speech bars",
    )
    val color = Primary
    Canvas(modifier) {
        val phase = pulse?.value ?: 0f
        for (bar in 0..2) {
            val x = size.width * (.22f + .28f * bar)
            val height = size.height * (.25f + .22f * (1f + sin(phase + bar * 1.45f)))
            drawLine(
                color, Offset(x, center.y - height / 2f), Offset(x, center.y + height / 2f),
                strokeWidth = size.minDimension * .10f, cap = StrokeCap.Round,
            )
        }
    }
}

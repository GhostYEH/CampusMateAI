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
    speaking: Boolean,
    landscape: Boolean,
    modifier: Modifier,
) {
    val reduceMotion = LocalReduceMotion.current
    val lampPower = animateFloatAsState(
        targetValue = if (speaking) 1f else 0f,
        animationSpec = if (reduceMotion) snap() else tween(420, easing = CampusMotion.settleEasing),
        label = "classroom lamp",
    )
    Box(modifier.clipToBounds()) {
        ClassroomStageBackdrop(Modifier.matchParentSize().graphicsLayer {
            val turn = if (reduceMotion) 0f else pageTurn.value
            val scale = 1f + abs(turn) * .027f
            scaleX = scale
            scaleY = scale
            translationX = -size.width * .012f * turn
        })
        Spacer(Modifier.matchParentSize().drawWithCache {
            val lamp = Offset(size.width * (if (landscape) .57f else .67f), size.height * .12f)
            val radius = (size.minDimension * .7f).coerceAtLeast(1f)
            val lampGlow = Brush.radialGradient(
                colors = listOf(ClassroomAmber.copy(alpha = .56f), ClassroomAmber.copy(alpha = .12f), Color.Transparent),
                center = lamp,
                radius = radius,
            )
            val floorShade = Brush.verticalGradient(
                colors = listOf(Color.Transparent, Color(0x85101B27)),
                startY = size.height * .68f,
                endY = size.height,
            )
            onDrawBehind {
                drawRect(floorShade)
                drawCircle(lampGlow, radius, lamp, alpha = .35f + lampPower.value * .47f)
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
internal fun ClassroomTeacherSignal(modifier: Modifier) {
    val pulse = if (LocalReduceMotion.current) null else rememberInfiniteTransition(label = "classroom speech").animateFloat(
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
            val height = size.height * (.27f + .22f * (1f + sin(phase + bar * 1.45f)))
            drawLine(
                color, Offset(x, center.y - height / 2f), Offset(x, center.y + height / 2f),
                strokeWidth = size.minDimension * .10f, cap = StrokeCap.Round,
            )
        }
    }
}

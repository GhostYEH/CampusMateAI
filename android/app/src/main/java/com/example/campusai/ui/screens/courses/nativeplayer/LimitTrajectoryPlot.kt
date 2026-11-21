package com.example.campusai.ui.screens.courses.nativeplayer

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.classroom.nativeplayer.ClassroomLimitExperiment
import com.example.campusai.data.classroom.nativeplayer.SpatialRotation
import com.example.campusai.data.classroom.nativeplayer.SpatialVector
import com.example.campusai.ui.theme.Accent
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.TextPrimary
import kotlin.math.PI

@Composable
internal fun LimitTrajectoryPlot(
    preset: ClassroomLimitExperiment.Preset,
    epsilon: Double,
    delta: Double,
    elapsed: Float,
    duration: Float,
    yaw: Float,
    pitch: Float,
    onDrag: (Float, Float) -> Unit,
    modifier: Modifier,
) {
    val drag by rememberUpdatedState(onDrag)
    val grid = Line
    val cyan = Accent
    val gold = Primary
    val ink = TextPrimary
    val frame = RoundedCornerShape(10.dp)
    val labels = rememberTextMeasurer()
    val rotation = remember(pitch, yaw) {
        val radians = (PI / 180).toFloat()
        SpatialRotation(SpatialVector(pitch * radians, yaw * radians, 0f))
    }
    val amplitude = ClassroomLimitExperiment.approachAmplitude
    val projectedLeft = preset.center - amplitude
    val motionLeft = if (preset.function == ClassroomLimitExperiment.Function.SQUARE_ROOT) maxOf(0.0, projectedLeft) else projectedLeft
    val motionRight = preset.center + amplitude
    val argumentMin = minOf(preset.xMin, motionLeft)
    val argumentMax = maxOf(preset.xMax, motionRight)
    val leftValue = preset.function.evaluate(motionLeft)
    val rightValue = preset.function.evaluate(motionRight)
    val motionMin = if (preset.function == ClassroomLimitExperiment.Function.QUADRATIC && 0.0 in motionLeft..motionRight) {
        0.0
    } else minOf(leftValue, rightValue)
    val valueMax = maxOf(preset.yMax, leftValue, rightValue)
    val valueMin = minOf(preset.yMin, motionMin)
    fun x(argument: Double) = ((argument - argumentMin) / (argumentMax - argumentMin)).toFloat().coerceIn(0f, 1f)
    fun y(value: Double) = ((value - valueMin) / (valueMax - valueMin)).toFloat().coerceIn(0f, 1f)
    val trajectory = remember(preset, duration) {
        List(181) { index ->
            val sampleTime = index / 180f
            val argument = preset.approachX(sampleTime * duration)
            SpatialVector(x(argument), y(preset.function.evaluate(argument)), sampleTime)
        }
    }
    Canvas(modifier.clip(frame).background(Background).border(1.dp, grid, frame)
        .pointerInput(Unit) {
            detectDragGestures { change, movement ->
                change.consume()
                drag(movement.x / density * .45f, movement.y / density * .45f)
            }
        }
        .semantics { contentDescription = "可旋转的三维趋近轨迹，t 轴为时间" }) {
        val scale = size.minDimension * .33f
        fun point(x: Float, y: Float, t: Float): Offset {
            val p = rotation.apply(SpatialVector((x - .5f) * 2f, (y - .5f) * 1.45f, (t - .5f) * 1.8f))
            val perspective = 5f / (5f + p.z)
            return center + Offset(p.x * scale * perspective * 1.18f, -p.y * scale * perspective)
        }
        fun area(a: Offset, b: Offset, c: Offset, d: Offset) = Path().apply {
            moveTo(a.x, a.y)
            lineTo(b.x, b.y)
            lineTo(c.x, c.y)
            lineTo(d.x, d.y)
            close()
        }
        val origin = point(0f, 0f, 0f)
        val xAxis = point(1f, 0f, 0f)
        val yAxis = point(0f, 1f, 0f)
        val tAxis = point(0f, 0f, 1f)
        drawPath(area(origin, xAxis, point(1f, 0f, 1f), tAxis), grid.copy(alpha = .23f))
        drawPath(area(origin, yAxis, point(0f, 1f, 1f), tAxis), grid.copy(alpha = .15f))
        val left = x(preset.center - delta)
        val right = x(preset.center + delta)
        val low = y(preset.limit - epsilon)
        val high = y(preset.limit + epsilon)
        drawPath(area(point(left, 0f, 0f), point(right, 0f, 0f), point(right, 0f, 1f), point(left, 0f, 1f)), gold.copy(alpha = .25f))
        drawPath(area(point(0f, low, 0f), point(0f, high, 0f), point(0f, high, 1f), point(0f, low, 1f)), cyan.copy(alpha = .20f))
        for (step in 1..4) {
            val q = step / 4f
            drawLine(grid, point(q, 0f, 0f), point(q, 0f, 1f), .6.dp.toPx())
            drawLine(grid, point(0f, 0f, q), point(1f, 0f, q), .6.dp.toPx())
            drawLine(grid, point(0f, q, 0f), point(0f, q, 1f), .6.dp.toPx())
        }
        val axes = listOf(Triple("x", xAxis, gold), Triple("f(x)", yAxis, cyan), Triple("t", tAxis, ink))
        for ((label, tip, color) in axes) {
            drawLine(color, origin, tip, 1.2.dp.toPx())
            val text = labels.measure(label, TextStyle(color = color, fontSize = 11.sp))
            val position = Offset(
                (tip.x + 4.dp.toPx()).coerceIn(0f, (size.width - text.size.width).coerceAtLeast(0f)),
                (tip.y - text.size.height / 2f).coerceIn(0f, (size.height - text.size.height).coerceAtLeast(0f)),
            )
            drawText(text, topLeft = position)
        }
        val progress = (elapsed / duration).coerceIn(0f, 1f)
        val cursorArgument = preset.approachX(elapsed)
        val cursorX = x(cursorArgument)
        val cursorY = y(preset.function.evaluate(cursorArgument))
        val cursor = point(cursorX, cursorY, progress)
        val track = Path()
        val observed = Path()
        trajectory.forEachIndexed { index, sample ->
            val pixel = point(sample.x, sample.y, sample.z)
            if (index == 0) {
                track.moveTo(pixel.x, pixel.y)
                observed.moveTo(pixel.x, pixel.y)
            } else {
                track.lineTo(pixel.x, pixel.y)
                if (sample.z <= progress) observed.lineTo(pixel.x, pixel.y)
            }
        }
        drawPath(track, ink.copy(alpha = .45f), style = Stroke(1.5.dp.toPx(), cap = StrokeCap.Round))
        if (progress > 0f) {
            observed.lineTo(cursor.x, cursor.y)
            drawPath(observed, ink, style = Stroke(2.dp.toPx(), cap = StrokeCap.Round))
        }
        val dashed = PathEffect.dashPathEffect(floatArrayOf(4.dp.toPx(), 3.dp.toPx()))
        val targetX = x(preset.center)
        val targetY = y(preset.limit)
        drawLine(cyan.copy(alpha = .72f), point(targetX, targetY, 0f), point(targetX, targetY, 1f), 1.dp.toPx(), pathEffect = dashed)
        drawLine(ink.copy(alpha = .58f), point(cursorX, 0f, progress), cursor, 1.dp.toPx(), pathEffect = dashed)
        val marker = if (cursorX in left..right && cursorY in low..high) cyan else gold
        drawCircle(marker.copy(alpha = .26f), 8.dp.toPx(), cursor)
        drawCircle(marker, 4.dp.toPx(), cursor)
    }
}

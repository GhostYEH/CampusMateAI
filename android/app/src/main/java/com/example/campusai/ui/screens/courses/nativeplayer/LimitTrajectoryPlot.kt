package com.example.campusai.ui.screens.courses.nativeplayer

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithCache
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.CustomAccessibilityAction
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.customActions
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.classroom.nativeplayer.ClassroomLimitExperiment
import com.example.campusai.data.classroom.nativeplayer.LimitTrajectoryPoint
import com.example.campusai.data.classroom.nativeplayer.LimitTrajectoryProjection
import com.example.campusai.ui.theme.Accent
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.TextPrimary
import kotlin.math.roundToInt

@Composable
internal fun LimitTrajectoryPlot(
    preset: ClassroomLimitExperiment.Preset,
    epsilon: Double,
    delta: Double,
    time: Float,
    angle: ClassroomLimitExperiment.ViewAngle,
    onOrbit: (Float, Float) -> Unit,
    onOrbitFinished: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val orbit by rememberUpdatedState(onOrbit)
    val finishOrbit by rememberUpdatedState(onOrbitFinished)
    val currentTime = rememberUpdatedState(time)
    val bounds = remember(preset) { TrajectoryBounds(preset) }
    val trajectory = remember(bounds) {
        List(181) { step -> bounds.sample(ClassroomLimitExperiment.durationSeconds * step / 180f) }
    }
    val labels = rememberTextMeasurer()
    val floorColor = Line
    val epsilonColor = Accent
    val deltaColor = Primary
    val timeColor = Color(0xFF91BCF0)
    val traceColor = TextPrimary
    val frame = RoundedCornerShape(10.dp)
    Box(
        modifier.clip(frame)
            .background(Brush.verticalGradient(listOf(Background, Color(0xFF142937))))
            .border(1.dp, floorColor, frame)
            .pointerInput(Unit) {
                val degreesPerPixel = .46f / density
                detectDragGestures(onDragEnd = { finishOrbit() }, onDragCancel = { finishOrbit() }) { change, drag ->
                    change.consume()
                    orbit(drag.x * degreesPerPixel, -drag.y * degreesPerPixel)
                }
            }
            .semantics {
                contentDescription = "可旋转的三维趋近轨迹，t 轴为时间"
                stateDescription = "水平角 ${angle.yaw.roundToInt()} 度，俯视角 ${angle.pitch.roundToInt()} 度"
                customActions = listOf(
                    CustomAccessibilityAction("水平旋转") { orbit(20f, 0f); finishOrbit(); true },
                    CustomAccessibilityAction("向上倾斜") { orbit(0f, 12f); finishOrbit(); true },
                    CustomAccessibilityAction("向下倾斜") { orbit(0f, -12f); finishOrbit(); true },
                )
            }
            .drawWithCache {
                val plot = TrajectoryViewport(size, 20.dp.toPx(), angle)
                fun at(x: Float, y: Float, t: Float) = plot.project(LimitTrajectoryPoint(x, y, t))
                val origin = at(0f, 0f, 0f)
                val xTip = at(1f, 0f, 0f)
                val yTip = at(0f, 1f, 0f)
                val timeTip = at(0f, 0f, 1f)
                val floor = polygon(origin, xTip, at(1f, 0f, 1f), timeTip)
                val side = polygon(origin, timeTip, at(0f, 1f, 1f), yTip)
                val xLow = bounds.x(preset.center - delta)
                val xHigh = bounds.x(preset.center + delta)
                val yLow = bounds.y(preset.limit - epsilon)
                val yHigh = bounds.y(preset.limit + epsilon)
                val deltaBand = polygon(at(xLow, 0f, 0f), at(xHigh, 0f, 0f), at(xHigh, 0f, 1f), at(xLow, 0f, 1f))
                val epsilonBand = polygon(at(0f, yLow, 0f), at(0f, yHigh, 0f), at(0f, yHigh, 1f), at(0f, yLow, 1f))
                val grid = buildList {
                    for (step in 1..4) {
                        val fraction = step / 4f
                        add(at(fraction, 0f, 0f) to at(fraction, 0f, 1f))
                        add(at(0f, 0f, fraction) to at(1f, 0f, fraction))
                        add(at(0f, fraction, 0f) to at(0f, fraction, 1f))
                        add(at(0f, 0f, fraction) to at(0f, 1f, fraction))
                    }
                }
                val projectedTrack = trajectory.map(plot::project)
                val trackOutline = Path().apply {
                    moveTo(projectedTrack.first().x, projectedTrack.first().y)
                    projectedTrack.drop(1).forEach { lineTo(it.x, it.y) }
                }
                val dashed = PathEffect.dashPathEffect(floatArrayOf(4.dp.toPx(), 3.dp.toPx()))
                val centerX = bounds.x(preset.center)
                val limitY = bounds.y(preset.limit)
                val axes = listOf(
                    Triple("x", xTip, deltaColor),
                    Triple("f(x)", yTip, epsilonColor),
                    Triple("t", timeTip, timeColor),
                ).map { (label, tip, color) ->
                    val layout = labels.measure(label, TextStyle(color = color, fontSize = 11.sp, fontWeight = FontWeight.Bold))
                    val axis = tip - origin
                    val direction = axis / axis.getDistance().coerceAtLeast(1f)
                    val labelCenter = tip + direction * 11.dp.toPx()
                    val labelPosition = Offset(
                        (labelCenter.x - layout.size.width / 2f).coerceIn(4f, (size.width - layout.size.width - 4f).coerceAtLeast(4f)),
                        (labelCenter.y - layout.size.height / 2f).coerceIn(2f, (size.height - layout.size.height - 2f).coerceAtLeast(2f)),
                    )
                    val base = tip - direction * 5.dp.toPx()
                    val wing = Offset(-direction.y, direction.x) * 2.4.dp.toPx()
                    Triple(color, listOf(base + wing, tip, base - wing), layout to labelPosition)
                }
                onDrawBehind {
                    drawPath(floor, floorColor.copy(alpha = .28f))
                    drawPath(side, floorColor.copy(alpha = .19f))
                    drawPath(deltaBand, deltaColor.copy(alpha = .19f))
                    drawPath(epsilonBand, epsilonColor.copy(alpha = .16f))
                    grid.forEach { (start, end) -> drawLine(floorColor.copy(alpha = .72f), start, end, .7.dp.toPx()) }
                    drawPath(deltaBand, deltaColor.copy(alpha = .68f), style = Stroke(.9.dp.toPx()))
                    drawPath(epsilonBand, epsilonColor.copy(alpha = .58f), style = Stroke(.9.dp.toPx()))
                    for ((color, arrow, label) in axes) {
                        val (left, tip, right) = arrow
                        drawLine(color, origin, tip, 1.1.dp.toPx())
                        drawLine(color, left, tip, 1.1.dp.toPx())
                        drawLine(color, right, tip, 1.1.dp.toPx())
                        drawText(label.first, topLeft = label.second)
                    }
                    drawLine(epsilonColor.copy(alpha = .74f), at(centerX, limitY, 0f), at(centerX, limitY, 1f),
                        strokeWidth = 1.dp.toPx(), pathEffect = dashed)
                    drawPath(trackOutline, traceColor.copy(alpha = .54f), style = Stroke(1.6.dp.toPx(), cap = StrokeCap.Round))

                    val sample = bounds.sample(currentTime.value)
                    val tip = plot.project(sample)
                    val lastIndex = (sample.time * projectedTrack.lastIndex).toInt()
                    if (sample.time > 0f) {
                        val completed = Path().apply {
                            moveTo(projectedTrack.first().x, projectedTrack.first().y)
                            for (index in 1..lastIndex) lineTo(projectedTrack[index].x, projectedTrack[index].y)
                            lineTo(tip.x, tip.y)
                        }
                        drawPath(completed, traceColor, style = Stroke(2.2.dp.toPx(), cap = StrokeCap.Round))
                    }
                    drawLine(traceColor.copy(alpha = .45f), at(sample.x, 0f, sample.time), tip,
                        strokeWidth = 1.dp.toPx(), pathEffect = dashed)
                    val marker = if (sample.x in xLow..xHigh && sample.y in yLow..yHigh) epsilonColor else deltaColor
                    drawCircle(marker.copy(alpha = .20f), 8.dp.toPx(), tip)
                    drawCircle(marker, 4.dp.toPx(), tip)
                    drawCircle(traceColor, 1.8.dp.toPx(), tip)
                }
            },
    )
}

private class TrajectoryBounds(private val preset: ClassroomLimitExperiment.Preset) {
    private val motionLeft = (preset.center - ClassroomLimitExperiment.approachAmplitude).let {
        if (preset.function == ClassroomLimitExperiment.Function.SQUARE_ROOT) it.coerceAtLeast(0.0) else it
    }
    private val motionRight = preset.center + ClassroomLimitExperiment.approachAmplitude
    private val leftValue = preset.function.evaluate(motionLeft)
    private val rightValue = preset.function.evaluate(motionRight)
    private val vertexValue = if (preset.function == ClassroomLimitExperiment.Function.QUADRATIC && 0.0 in motionLeft..motionRight) 0.0
        else minOf(leftValue, rightValue)
    private val minX = minOf(preset.xMin, motionLeft)
    private val maxX = maxOf(preset.xMax, motionRight)
    private val minY = minOf(preset.yMin, vertexValue)
    private val maxY = maxOf(preset.yMax, leftValue, rightValue)

    fun x(value: Double) = ((value - minX) / (maxX - minX)).toFloat().coerceIn(0f, 1f)
    fun y(value: Double) = ((value - minY) / (maxY - minY)).toFloat().coerceIn(0f, 1f)

    fun sample(time: Float): LimitTrajectoryPoint {
        val argument = preset.approachX(time)
        return LimitTrajectoryPoint(x(argument), y(preset.function.evaluate(argument)),
            (time / ClassroomLimitExperiment.durationSeconds).coerceIn(0f, 1f))
    }
}

private class TrajectoryViewport(size: Size, inset: Float, angle: ClassroomLimitExperiment.ViewAngle) {
    private val camera = LimitTrajectoryProjection(angle)
    private val corners = buildList {
        for (x in listOf(0f, 1f)) for (y in listOf(0f, 1f)) for (t in listOf(0f, 1f)) {
            add(camera.project(LimitTrajectoryPoint(x, y, t)))
        }
    }
    private val left = corners.minOf { it.x }
    private val right = corners.maxOf { it.x }
    private val top = corners.minOf { it.y }
    private val bottom = corners.maxOf { it.y }
    private val widthScale = ((size.width - 2f * inset) / (right - left)).coerceAtLeast(0f)
    private val heightScale = ((size.height - 2f * inset) / (bottom - top)).coerceIn(0f, widthScale)
    private val horizontalScale = minOf(widthScale, heightScale * 1.25f)
    private val origin = Offset(
        (size.width - (left + right) * horizontalScale) / 2f,
        (size.height - (top + bottom) * heightScale) / 2f,
    )

    fun project(point: LimitTrajectoryPoint): Offset {
        val projected = camera.project(point)
        return origin + Offset(projected.x * horizontalScale, projected.y * heightScale)
    }
}

private fun polygon(a: Offset, b: Offset, c: Offset, d: Offset) = Path().apply {
    moveTo(a.x, a.y)
    lineTo(b.x, b.y)
    lineTo(c.x, c.y)
    lineTo(d.x, d.y)
    close()
}

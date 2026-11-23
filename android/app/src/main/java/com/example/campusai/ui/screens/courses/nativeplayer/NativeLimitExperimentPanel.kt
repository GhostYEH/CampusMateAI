package com.example.campusai.ui.screens.courses.nativeplayer

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipRect
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.example.campusai.data.classroom.nativeplayer.ClassroomLimitExperiment
import com.example.campusai.ui.theme.Accent
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import java.util.Locale
import kotlin.math.abs

private const val DurationSeconds = ClassroomLimitExperiment.durationSeconds

@Composable
internal fun NativeLimitExperimentPanel(
    experiment: ClassroomLimitExperiment,
    initial: ClassroomLimitExperiment.Controls,
    highlighted: ClassroomLimitExperiment.Highlight?,
    onControlsChanged: (ClassroomLimitExperiment.Controls) -> Unit,
    modifier: Modifier = Modifier,
) {
    var presetId by remember(experiment) { mutableStateOf(initial.presetId) }
    var epsilon by remember(experiment) { mutableFloatStateOf(initial.epsilon) }
    var speed by remember(experiment) { mutableFloatStateOf(initial.speed) }
    var time by remember(experiment) { mutableFloatStateOf(initial.time) }
    var showTrajectory by remember(experiment) { mutableStateOf(initial.showTrajectory) }
    var viewAngle by remember(experiment) { mutableStateOf(initial.viewAngle) }
    var running by remember { mutableStateOf(false) }
    val preset = experiment.presets.firstOrNull { it.id == presetId }
        ?: experiment.presets.firstOrNull()
        ?: return
    val delta = remember(preset, epsilon) { preset.delta(epsilon.toDouble()) }
    val sampleX = preset.approachX(time)
    val sampleY = preset.function.evaluate(sampleX)
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val saveControls by rememberUpdatedState(onControlsChanged)
    fun saveProgress() = saveControls(
        ClassroomLimitExperiment.Controls(presetId, epsilon, speed, time, showTrajectory, viewAngle),
    )
    DisposableEffect(lifecycle, experiment) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_PAUSE) {
                running = false
                saveProgress()
            }
        }
        lifecycle.addObserver(observer)
        onDispose {
            lifecycle.removeObserver(observer)
            saveProgress()
        }
    }
    LaunchedEffect(running) {
        if (!running) return@LaunchedEffect
        var frame = withFrameNanos { it }
        while (time < DurationSeconds) {
            val next = withFrameNanos { it }
            val elapsed = ((next - frame) / 1_000_000_000f).coerceIn(0f, 0.1f)
            time = (time + elapsed * speed).coerceAtMost(DurationSeconds)
            frame = next
        }
        running = false
        saveProgress()
    }

    val frame = RoundedCornerShape(14.dp)
    val chipColors = FilterChipDefaults.filterChipColors(
        labelColor = TextPrimary,
        selectedContainerColor = Primary,
        selectedLabelColor = Background,
    )
    val orientation = LocalConfiguration.current.orientation
    val scroll = key(orientation) { rememberScrollState() }
    BoxWithConstraints(modifier.clip(frame).background(Surface, frame).border(1.dp, Line, frame).padding(12.dp)) {
        val wide = maxWidth >= 480.dp
        val chartHeight = if (wide) (maxHeight - 76.dp).coerceIn(104.dp, 260.dp) else 156.dp
        val description: @Composable () -> Unit = {
            if (experiment.description.isNotBlank()) {
                Text(experiment.description, color = Muted, fontSize = 13.sp, lineHeight = 19.sp)
            }
        }
        val presets: @Composable () -> Unit = {
            Row(
                Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(7.dp),
            ) {
                experiment.presets.forEach { option ->
                    FilterChip(
                        selected = option.id == preset.id,
                        onClick = {
                            if (option.id != preset.id) {
                                running = false
                                time = 0f
                                presetId = option.id
                                saveProgress()
                            }
                        },
                        label = { Text(option.label.substringBefore("f(x)").trim()) },
                        colors = chipColors,
                    )
                }
            }
        }
        val formula: @Composable () -> Unit = {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(preset.label, Modifier.weight(1f), color = TextPrimary,
                    fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                Text(
                    "δ = ${decimal(delta, 3)}",
                    Modifier.limitHighlight(highlighted, ClassroomLimitExperiment.Highlight.DELTA),
                    color = Primary, fontSize = 14.sp, fontWeight = FontWeight.Bold,
                )
            }
        }
        val observations: @Composable () -> Unit = {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("c = ${decimal(preset.center)}   L = ${decimal(preset.limit)}", color = Muted, fontSize = 12.sp)
                Text(
                    "|x − c| = ${decimal(abs(sampleX - preset.center), 3)}   |f(x) − L| = ${decimal(abs(sampleY - preset.limit), 3)}",
                    color = TextPrimary, fontSize = 12.sp,
                )
            }
        }
        val plot: @Composable (Modifier) -> Unit = { plotModifier ->
            Column(plotModifier, verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Row(
                    Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(5.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    FilterChip(
                        selected = !showTrajectory,
                        onClick = {
                            showTrajectory = false
                            saveProgress()
                        },
                        label = { Text("二维曲线") },
                        colors = chipColors,
                    )
                    FilterChip(
                        selected = showTrajectory,
                        onClick = {
                            showTrajectory = true
                            saveProgress()
                        },
                        label = { Text("三维轨迹") },
                        colors = chipColors,
                    )
                    if (showTrajectory) {
                        IconButton(onClick = {
                            viewAngle = ClassroomLimitExperiment.ViewAngle()
                            saveProgress()
                        }) { Icon(Icons.Default.Refresh, "重置视角", tint = Accent) }
                    }
                    Button(onClick = {
                        if (time >= DurationSeconds) time = 0f
                        running = !running
                        if (!running) saveProgress()
                    }, contentPadding = ButtonDefaults.ButtonWithIconContentPadding) {
                        Text(when {
                            running -> "暂停"
                            time >= DurationSeconds -> "重播"
                            time > 0f -> "继续"
                            else -> "启动"
                        })
                    }
                }
                if (showTrajectory) {
                    LimitTrajectoryPlot(
                        preset, epsilon.toDouble(), delta, time, viewAngle,
                        onOrbit = { yaw, pitch -> viewAngle = viewAngle.orbit(yaw, pitch) },
                        onOrbitFinished = ::saveProgress,
                        modifier = Modifier.fillMaxWidth().height(chartHeight),
                    )
                } else {
                    LimitPlot(preset, epsilon.toDouble(), delta, sampleX, sampleY, chartHeight)
                }
                Text(
                    if (showTrajectory) "拖动旋转 · t 为时间 · 青色 ε 带 · 金色 δ 区间"
                    else "青色为 ε 带，金色为 δ 区间",
                    color = Muted,
                    fontSize = 11.sp,
                )
            }
        }
        val epsilonControl: @Composable () -> Unit = {
            Row(
                Modifier.fillMaxWidth().limitHighlight(highlighted, ClassroomLimitExperiment.Highlight.EPSILON),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("ε", color = TextPrimary, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                Slider(
                    value = epsilon,
                    onValueChange = {
                        epsilon = it
                        saveProgress()
                    },
                    valueRange = ClassroomLimitExperiment.epsilonRange,
                    steps = 28,
                    modifier = Modifier.weight(1f).semantics { contentDescription = "ε" },
                )
                Text(decimal(epsilon.toDouble()), color = Primary, fontSize = 13.sp)
            }
        }
        val controls: @Composable (Modifier) -> Unit = { controlsModifier ->
            Column(controlsModifier, verticalArrangement = Arrangement.spacedBy(4.dp)) {
                LimitSlider("速度", "${decimal(speed.toDouble(), 1)}×", speed, ClassroomLimitExperiment.speedRange, 27) {
                    speed = it
                    saveProgress()
                }
                OutlinedButton(onClick = {
                    time = 0f
                    running = true
                    saveProgress()
                }) { Text("重新开始") }
                LimitSlider("趋近进度", "${decimal(time.toDouble(), 1)} 秒", time, 0f..DurationSeconds) {
                    running = false
                    time = it
                    saveProgress()
                }
                if (time >= DurationSeconds) {
                    Text(
                        "趋近演示已完成。观察 x 进入 δ 区间时，f(x) 如何落在 ε 带内。",
                        color = Accent, fontSize = 12.sp, lineHeight = 17.sp,
                    )
                }
            }
        }
        if (wide) {
            Row(Modifier.fillMaxSize(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                plot(Modifier.weight(1.2f).fillMaxHeight().verticalScroll(rememberScrollState()))
                Column(
                    Modifier.weight(1f).fillMaxHeight().verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(7.dp),
                ) {
                    presets()
                    epsilonControl()
                    formula()
                    observations()
                    controls(Modifier.fillMaxWidth())
                    description()
                }
            }
        } else {
            Column(Modifier.fillMaxSize().verticalScroll(scroll), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                presets()
                epsilonControl()
                formula()
                plot(Modifier.fillMaxWidth())
                observations()
                controls(Modifier.fillMaxWidth())
                description()
            }
        }
    }
}

@Composable
private fun Modifier.limitHighlight(
    highlighted: ClassroomLimitExperiment.Highlight?,
    target: ClassroomLimitExperiment.Highlight,
): Modifier {
    val requester = remember { BringIntoViewRequester() }
    val selected = highlighted == target
    LaunchedEffect(selected) { if (selected) requester.bringIntoView() }
    val frame = RoundedCornerShape(8.dp)
    return bringIntoViewRequester(requester)
        .then(if (selected) {
            Modifier.background(Primary.copy(alpha = 0.14f), frame)
                .border(2.dp, Primary, frame)
                .semantics { stateDescription = "老师正在指示" }
        } else Modifier)
        .padding(horizontal = 8.dp, vertical = 5.dp)
}

@Composable
private fun LimitSlider(
    label: String,
    valueText: String,
    value: Float,
    range: ClosedFloatingPointRange<Float>,
    steps: Int = 0,
    change: (Float) -> Unit,
) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
        Text(valueText, color = Primary, fontSize = 13.sp)
    }
    Slider(value = value, onValueChange = change, valueRange = range, steps = steps,
        modifier = Modifier.fillMaxWidth().semantics { contentDescription = label })
}

@Composable
private fun LimitPlot(
    preset: ClassroomLimitExperiment.Preset,
    epsilon: Double,
    delta: Double,
    sampleX: Double,
    sampleY: Double,
    chartHeight: Dp,
) {
    val ink = Accent
    val gold = Primary
    val grid = Line
    val shape = RoundedCornerShape(10.dp)
    val curvePoints = remember(preset) { preset.normalizedCurve() }
    Canvas(Modifier.fillMaxWidth().height(chartHeight).clip(shape).background(Background)
        .border(1.dp, grid, shape).padding(8.dp).semantics {
            contentDescription = "函数曲线、ε 带和 δ 区间"
        }) {
        fun x(value: Double): Float = ((value - preset.xMin) / (preset.xMax - preset.xMin) * size.width).toFloat()
        fun y(value: Double): Float = ((preset.yMax - value) / (preset.yMax - preset.yMin) * size.height).toFloat()
        val xStart = x(preset.center - delta)
        val xEnd = x(preset.center + delta)
        val yTop = y(preset.limit + epsilon)
        val yBottom = y(preset.limit - epsilon)
        val dashed = PathEffect.dashPathEffect(floatArrayOf(5.dp.toPx(), 3.dp.toPx()))
        clipRect {
            for (step in 1..5) {
                val gx = size.width * step / 6f
                val gy = size.height * step / 6f
                drawLine(grid.copy(alpha = 0.55f), Offset(gx, 0f), Offset(gx, size.height))
                drawLine(grid.copy(alpha = 0.55f), Offset(0f, gy), Offset(size.width, gy))
            }
            drawRect(ink.copy(alpha = 0.15f), topLeft = Offset(0f, yTop), size = Size(size.width, yBottom - yTop))
            drawRect(gold.copy(alpha = 0.15f), topLeft = Offset(xStart, 0f), size = Size(xEnd - xStart, size.height))
            for (edge in listOf(yTop, yBottom)) {
                drawLine(ink.copy(alpha = 0.8f), Offset(0f, edge), Offset(size.width, edge), pathEffect = dashed)
            }
            for (edge in listOf(xStart, xEnd)) {
                drawLine(gold.copy(alpha = 0.8f), Offset(edge, 0f), Offset(edge, size.height), pathEffect = dashed)
            }
            val center = Offset(x(preset.center), y(preset.limit))
            drawLine(grid, Offset(center.x, 0f), Offset(center.x, size.height))
            drawLine(grid, Offset(0f, center.y), Offset(size.width, center.y))
            val curve = Path()
            var started = false
            for (point in curvePoints) {
                val px = point.x * size.width
                val py = point.y * size.height
                if (started) curve.lineTo(px, py) else {
                    curve.moveTo(px, py)
                    started = true
                }
            }
            drawPath(curve, ink, style = Stroke(2.dp.toPx()))
            drawCircle(gold, 4.dp.toPx(), center)
            drawCircle(gold, 6.dp.toPx(), Offset(x(sampleX), y(sampleY)))
        }
    }
}

private fun decimal(value: Double, digits: Int = 2): String =
    String.format(Locale.ROOT, "%.${digits}f", value)

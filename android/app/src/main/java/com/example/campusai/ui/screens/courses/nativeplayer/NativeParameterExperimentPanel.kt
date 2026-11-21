package com.example.campusai.ui.screens.courses.nativeplayer

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
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
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.classroom.nativeplayer.ClassroomParameterExperiment
import com.example.campusai.ui.theme.Accent
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import java.text.DecimalFormat
import java.text.DecimalFormatSymbols
import java.util.Locale
import kotlin.math.abs
import kotlin.math.roundToInt

@Composable
internal fun NativeParameterExperimentPanel(
    experiment: ClassroomParameterExperiment,
    values: Map<String, Double>,
    highlighted: String?,
    onValuesChanged: (Map<String, Double>) -> Unit,
    modifier: Modifier = Modifier,
) {
    val result = remember(experiment, values) { experiment.calculate(values) }
    val numberFormat = remember { DecimalFormat("0.######", DecimalFormatSymbols.getInstance(Locale.ROOT)) }
    fun valueText(value: Double, unit: String): String {
        val number = if (value != 0.0 && (abs(value) < .00001 || abs(value) >= 1e8)) {
            String.format(Locale.ROOT, "%.4e", value)
        } else numberFormat.format(if (value == 0.0) 0.0 else value)
        return if (unit.isBlank()) number else "$number $unit"
    }

    val frame = RoundedCornerShape(14.dp)
    BoxWithConstraints(modifier.clip(frame).background(Surface).border(1.dp, Line, frame).padding(12.dp)) {
        val wide = maxWidth >= 435.dp && maxHeight < 340.dp
        val chartHeight = if (wide) (maxHeight - 81.dp).coerceIn(60.dp, 155.dp) else 126.dp
        val resultCard: @Composable () -> Unit = {
            Row(
                Modifier.fillMaxWidth().background(Background, RoundedCornerShape(9.dp))
                    .highlightedParameter(highlighted == ClassroomParameterExperiment.ResultTarget)
                    .padding(horizontal = 10.dp, vertical = 9.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(experiment.resultLabel, Modifier.weight(1f), color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                Text(
                    result?.let { valueText(it, experiment.resultUnit) } ?: "当前参数下无定义",
                    color = if (result == null) Muted else Primary,
                    fontSize = if (result == null) 12.sp else 20.sp,
                    fontWeight = FontWeight.Bold,
                )
            }
        }
        val inputs: @Composable () -> Unit = {
            experiment.controls.forEach { control ->
                val value = values[control.id] ?: control.initial
                val printable = valueText(value, control.unit)
                val input: @Composable (Modifier) -> Unit = { inputModifier ->
                    Slider(
                        value = ((value - control.min) / control.step).toFloat().coerceIn(0f, control.increments.toFloat()),
                        onValueChange = { position ->
                            val next = control.snap(control.min + position.roundToInt() * control.step)
                            onValuesChanged(mapOf(control.id to next))
                        },
                        valueRange = 0f..control.increments.toFloat(),
                        steps = if (control.increments <= 24) control.increments - 1 else 0,
                        modifier = inputModifier.semantics {
                            contentDescription = control.label
                            stateDescription = printable
                        },
                    )
                }
                val controlModifier = Modifier.fillMaxWidth().highlightedParameter(highlighted == control.target)
                    .padding(horizontal = 6.dp)
                if (wide) {
                    Row(controlModifier, horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(.45f)) {
                            Text(control.label, color = TextPrimary, fontSize = 13.sp)
                            Text(printable, color = Primary, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                        }
                        input(Modifier.weight(1f))
                    }
                } else {
                    Column(controlModifier) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(control.label, modifier = Modifier.weight(1f), color = TextPrimary, fontSize = 13.sp)
                            Text(printable, color = Primary, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                        }
                        input(Modifier.fillMaxWidth())
                    }
                }
            }
            Row(
                Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(7.dp),
            ) {
                val buttonPadding = PaddingValues(horizontal = if (wide) 10.dp else 19.dp, vertical = 7.dp)
                experiment.presets.forEach { preset ->
                    OutlinedButton(
                        onClick = { onValuesChanged(experiment.initialValues + preset.values) },
                        contentPadding = buttonPadding,
                    ) { Text(preset.label, fontSize = 12.sp) }
                }
                OutlinedButton(
                    onClick = { onValuesChanged(experiment.initialValues) },
                    contentPadding = buttonPadding,
                ) { Text("重置实验", fontSize = 12.sp) }
            }
        }
        val chart: @Composable () -> Unit = {
            experiment.chartParameter?.let { control ->
                Column(Modifier.highlightedParameter(highlighted == ClassroomParameterExperiment.CurveTarget)) {
                    Text(
                        experiment.resultLabel + "随" + control.label + "变化",
                        Modifier.padding(bottom = 3.dp),
                        color = Muted, fontSize = 11.sp,
                    )
                    ExperimentCurve(experiment, control, values, result, chartHeight)
                }
            }
        }
        if (wide) {
            Row(Modifier.fillMaxSize(), horizontalArrangement = Arrangement.spacedBy(13.dp)) {
                Column(
                    Modifier.weight(1.14f).fillMaxHeight().verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    resultCard()
                    chart()
                    Text(experiment.description, color = Muted, fontSize = 12.sp, lineHeight = 18.sp)
                }
                Column(
                    Modifier.weight(1f).fillMaxHeight().verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(3.dp),
                ) { inputs() }
            }
        } else {
            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                resultCard()
                inputs()
                chart()
                Text(experiment.description, color = Muted, fontSize = 12.sp, lineHeight = 18.sp)
            }
        }
    }
}

@Composable
private fun Modifier.highlightedParameter(selected: Boolean): Modifier {
    val requester = remember { BringIntoViewRequester() }
    LaunchedEffect(selected) { if (selected) requester.bringIntoView() }
    val shape = RoundedCornerShape(8.dp)
    return bringIntoViewRequester(requester).then(
        if (selected) Modifier.background(Primary.copy(alpha = .14f), shape).border(2.dp, Primary, shape)
            .semantics { stateDescription = "老师正在指示" }
        else Modifier,
    )
}

@Composable
private fun ExperimentCurve(
    experiment: ClassroomParameterExperiment,
    control: ClassroomParameterExperiment.Control,
    values: Map<String, Double>,
    result: Double?,
    height: Dp,
) {
    val fixed = values - control.id
    val samples = remember(experiment, control, fixed) {
        List(81) { index ->
            val passed = control.min + (control.max - control.min) * index / 80
            experiment.calculate(fixed + (control.id to passed))
        }
    }
    val chartShape = RoundedCornerShape(8.dp)
    val grid = Line
    val ink = Accent
    val marker = Primary
    Canvas(
        Modifier.fillMaxWidth().height(height).clip(chartShape).background(Background)
            .border(1.dp, grid, chartShape).padding(8.dp)
            .semantics { contentDescription = "实验结果曲线" },
    ) {
        val finite = samples.filterNotNull() + listOfNotNull(result)
        val low = finite.minOrNull() ?: return@Canvas
        val high = finite.maxOrNull() ?: return@Canvas
        // Normalize by the largest magnitude before subtracting to avoid overflow.
        val divisor = maxOf(abs(low), abs(high)).takeUnless { it == 0.0 } ?: 1.0
        val scaledLow = low / divisor
        val scaledHigh = high / divisor
        fun y(value: Double): Float = if (scaledLow == scaledHigh) size.height * .5f
            else ((scaledHigh - value / divisor) / (scaledHigh - scaledLow)).toFloat() * size.height
        for (step in 0..4) {
            val horizontal = size.height * step / 4
            val vertical = size.width * step / 4
            drawLine(grid, Offset(0f, horizontal), Offset(size.width, horizontal), .6.dp.toPx())
            drawLine(grid, Offset(vertical, 0f), Offset(vertical, size.height), .6.dp.toPx())
        }
        val path = Path()
        var joined = false
        samples.forEachIndexed { index, sample ->
            if (sample == null) {
                joined = false
            } else {
                val point = size.width * index / samples.lastIndex
                if (joined) path.lineTo(point, y(sample)) else path.moveTo(point, y(sample))
                joined = true
            }
        }
        drawPath(path, ink, style = Stroke(2.dp.toPx()))
        if (result != null) {
            val selected = values[control.id] ?: control.initial
            val x = ((selected - control.min) / (control.max - control.min)).toFloat() * size.width
            drawCircle(marker, 4.dp.toPx(), Offset(x, y(result)))
        }
    }
}

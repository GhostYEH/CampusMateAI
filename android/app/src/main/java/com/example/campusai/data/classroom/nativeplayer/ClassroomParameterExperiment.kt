package com.example.campusai.data.classroom.nativeplayer

import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.pow
import kotlin.math.round
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt

class ClassroomParameterExperiment private constructor(
    val description: String,
    val controls: List<Control>,
    val resultLabel: String,
    val resultUnit: String,
    val chartParameter: Control?,
    val presets: List<Preset>,
    private val expression: List<Instruction>,
) {
    data class Control(
        val id: String,
        val label: String,
        val unit: String,
        val min: Double,
        val max: Double,
        val step: Double,
        val initial: Double,
    ) {
        val increments: Int get() = ((max - min) / step).roundToInt()
        val target: String get() = "#parameter-$id"

        fun snap(value: Double): Double =
            (min + ((value.coerceIn(min, max) - min) / step).roundToInt() * step).coerceAtMost(max)
    }

    data class Preset(val label: String, val values: Map<String, Double>)

    val initialValues: Map<String, Double> = controls.associate { it.id to it.initial }

    fun calculate(values: Map<String, Double>): Double? {
        val stack = DoubleArray(expression.size)
        var size = 0
        for (instruction in expression) {
            when (instruction) {
                is Instruction.Number -> stack[size++] = instruction.value
                is Instruction.Parameter -> stack[size++] = values[instruction.id] ?: return null
                is Instruction.Apply -> {
                    val right = stack[--size]
                    val result = if (instruction.operator.operands == 2) {
                        instruction.operator.apply(stack[--size], right)
                    } else instruction.operator.apply(0.0, right)
                    if (!result.isFinite()) return null
                    stack[size++] = result
                }
            }
        }
        return stack[0].takeIf(Double::isFinite)
    }

    internal fun validatedChanges(raw: Map<String, Any?>?): Map<String, Double>? {
        if (raw.isNullOrEmpty() || raw.size > controls.size) return null
        return raw.mapValues { (id, rawValue) ->
            val control = controls.firstOrNull { it.id == id } ?: return null
            val value = boundedNumber(rawValue)?.takeIf { it in control.min..control.max } ?: return null
            control.snap(value)
        }
    }

    internal fun supportsActions(actions: List<NativeAction>): Boolean = actions.all {
        when (it.type) {
            "widget_highlight" -> it.widgetTarget == ResultTarget ||
                (it.widgetTarget == CurveTarget && chartParameter != null) ||
                controls.any { control -> control.target == it.widgetTarget }
            "widget_setState", "widget_set_state" -> validatedChanges(it.widgetState) != null
            else -> !it.type.startsWith("widget_")
        }
    }

    private sealed interface Instruction {
        data class Number(val value: Double) : Instruction
        data class Parameter(val id: String) : Instruction
        data class Apply(val operator: Operator) : Instruction
    }

    private enum class Operator(val token: String, val operands: Int) {
        ADD("+", 2), SUBTRACT("-", 2), MULTIPLY("*", 2), DIVIDE("/", 2), POWER("^", 2),
        SQRT("sqrt", 1), ABS("abs", 1), SIN("sin", 1), COS("cos", 1);

        fun apply(left: Double, right: Double): Double = when (this) {
            ADD -> left + right
            SUBTRACT -> left - right
            MULTIPLY -> left * right
            DIVIDE -> left / right
            POWER -> left.pow(right)
            SQRT -> sqrt(right)
            ABS -> abs(right)
            SIN -> sin(right)
            COS -> cos(right)
        }
    }

    companion object {
        internal const val ResultTarget = "#experiment-result"
        internal const val CurveTarget = "#experiment-curve"
        private const val Profile = "classroom-parameter-experiment/1"
        private val validId = Regex("[A-Za-z][A-Za-z0-9_-]{0,31}")
        private val operators = Operator.entries.associateBy(Operator::token)

        internal fun fromWidgetConfig(raw: Any?): ClassroomParameterExperiment? {
            val config = raw.asMap() ?: return null
            if (config["type"] != "simulation" || config["nativeRenderer"] != Profile) return null
            val description = text(config["description"], 960)?.takeIf(String::isNotEmpty) ?: return null
            val resultLabel = text(config["resultLabel"], 64)?.takeIf(String::isNotEmpty) ?: return null
            val resultUnit = text(config["resultUnit"], 24) ?: return null
            val variables = config["controls"].asList()?.takeIf { it.size in 1..6 } ?: return null
            val controls = variables.map { control(it.asMap() ?: return null) ?: return null }
            val ids = controls.map(Control::id).toSet()
            if (ids.size != controls.size) return null
            val tokens = config["expression"].asList()?.takeIf { it.size in 1..32 } ?: return null
            val calculation = compile(tokens, ids) ?: return null
            val chartParameter = config["chartParameter"]?.let { id -> controls.firstOrNull { it.id == id } ?: return null }
            val draft = ClassroomParameterExperiment(description, controls, resultLabel, resultUnit, chartParameter, emptyList(), calculation)
            if (draft.calculate(draft.initialValues) == null) return null
            val presets = config["presets"]?.let { rawPresets ->
                val list = rawPresets.asList()?.takeIf { it.size <= 6 } ?: return null
                list.map { candidate ->
                    val preset = candidate.asMap() ?: return null
                    val name = text(preset["label"], 38)?.takeIf(String::isNotEmpty) ?: return null
                    val values = draft.validatedChanges(preset["values"].asMap()) ?: return null
                    Preset(name, values)
                }
            }.orEmpty()
            return ClassroomParameterExperiment(description, controls, resultLabel, resultUnit, chartParameter, presets, calculation)
        }

        private fun compile(raw: List<*>, ids: Set<String>): List<Instruction>? {
            var operands = 0
            var hasParameter = false
            val expression = ArrayList<Instruction>(raw.size)
            for (token in raw) {
                val value = boundedNumber(token)
                if (value != null) {
                    expression.add(Instruction.Number(value))
                    operands++
                    continue
                }
                if (token !is String) return null
                if (token in ids) {
                    expression.add(Instruction.Parameter(token))
                    operands++
                    hasParameter = true
                } else {
                    val operator = operators[token] ?: return null
                    if (operands < operator.operands) return null
                    operands += 1 - operator.operands
                    expression.add(Instruction.Apply(operator))
                }
            }
            return expression.takeIf { operands == 1 && hasParameter }
        }

        private fun control(raw: Map<String, Any?>): Control? {
            val id = (raw["id"] as? String)?.takeIf { validId.matches(it) && it !in operators && it != "constructor" } ?: return null
            val name = text(raw["label"], 64)?.takeIf(String::isNotEmpty) ?: return null
            val unit = text(raw["unit"], 24) ?: return null
            val min = boundedNumber(raw["min"]) ?: return null
            val max = boundedNumber(raw["max"])?.takeIf { it > min } ?: return null
            val step = boundedNumber(raw["step"])?.takeIf { it > 0 } ?: return null
            val initial = boundedNumber(raw["value"])?.takeIf { it in min..max } ?: return null
            val count = (max - min) / step
            if (count < 1 - 1e-7 || count > 2000 + 1e-7 || abs(count - round(count)) > 1e-7) return null
            val parameter = Control(id, name, unit, min, max, step, initial)
            return parameter.copy(initial = parameter.snap(initial))
        }

        private fun boundedNumber(raw: Any?): Double? =
            (raw as? Number)?.toDouble()?.takeIf { it.isFinite() && abs(it) <= 1e8 }

        private fun text(raw: Any?, max: Int): String? = (raw as? String)?.trim()?.takeIf { it.length <= max }
    }
}

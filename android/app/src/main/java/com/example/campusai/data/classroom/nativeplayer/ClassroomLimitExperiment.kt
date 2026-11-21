package com.example.campusai.data.classroom.nativeplayer

import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

data class ClassroomLimitExperiment(
    val description: String,
    val presets: List<Preset>,
    val initialPresetId: String,
    val initialEpsilon: Float,
    val initialSpeed: Float,
) {
    data class Controls(
        val presetId: String,
        val epsilon: Float,
        val speed: Float,
        val time: Float = 0f,
        val showTrajectory: Boolean = false,
        val viewAngle: ViewAngle = ViewAngle(),
    )

    data class ViewAngle(val yaw: Float = 36f, val pitch: Float = 24f) {
        internal fun orbit(yawChange: Float, pitchChange: Float): ViewAngle {
            val wrappedYaw = ((yaw + yawChange) % 360f + 360f) % 360f
            return ViewAngle(wrappedYaw, (pitch + pitchChange).coerceIn(8f, 70f))
        }
    }

    fun initialControls() = Controls(initialPresetId, initialEpsilon, initialSpeed)

    data class Preset(
        val function: Function,
        val label: String,
        val center: Double,
        val limit: Double,
        val xMin: Double,
        val xMax: Double,
        val yMin: Double,
        val yMax: Double,
    ) {
        val id get() = function.id

        fun delta(epsilon: Double): Double = min(3.0, when (function) {
            Function.LINEAR -> epsilon / 2.0
            Function.QUADRATIC -> 2.0 * epsilon / (abs(center) + sqrt(center * center + 2.0 * epsilon))
            Function.SQUARE_ROOT -> if (epsilon < limit) epsilon * (2.0 * limit - epsilon) else center
        })

        internal fun approachX(time: Float): Double {
            val x = center + approachAmplitude * exp(-0.4 * time) * cos(4.0 * time)
            return if (function == Function.SQUARE_ROOT) max(0.0, x) else x
        }
    }

    enum class Function(val id: String, val labelSuffix: String) {
        LINEAR("linear", "f(x)=2x"),
        QUADRATIC("quadratic", "f(x)=x²/2"),
        SQUARE_ROOT("sqrt", "f(x)=√x");

        fun evaluate(x: Double): Double = when (this) {
            LINEAR -> 2.0 * x
            QUADRATIC -> x * x / 2.0
            SQUARE_ROOT -> sqrt(x)
        }
    }

    enum class Highlight(val selector: String) {
        EPSILON("#slider-eps"),
        DELTA("#stat-delta");

        companion object {
            fun fromSelector(selector: String?) = entries.firstOrNull { it.selector == selector }
        }
    }

    companion object {
        internal const val durationSeconds = 15f
        internal const val approachAmplitude = 1.8
        val epsilonRange = 0.1f..3.0f
        val speedRange = 0.2f..3.0f

        // The existing limit experiment attaches its three formula presets as data.
        // Recognize their exact formulas so other simulation widgets keep their HTML renderer.
        internal fun fromWidgetConfig(raw: Any?): ClassroomLimitExperiment? {
            val config = raw.asMap() ?: return null
            if (config["type"] != "simulation") return null
            val presets = config["presets"].asList()?.takeIf { it.isNotEmpty() && it.size <= Function.entries.size }
                ?: return null
            val parsed = presets.map { parsePreset(it) ?: return null }
            if (parsed.map(Preset::id).distinct().size != parsed.size) return null

            val initial = config["initial"].asMap() ?: return null
            val presetId = initial["presetId"] as? String ?: return null
            if (parsed.none { it.id == presetId }) return null
            val epsilon = initial["epsilon"].finiteDouble()?.toFloat()?.takeIf { it in epsilonRange } ?: return null
            val speed = initial["speed"].finiteDouble()?.toFloat()?.takeIf { it in speedRange } ?: return null
            val description = config["description"].asText()
            return ClassroomLimitExperiment(description, parsed, presetId, epsilon, speed)
        }

        private fun parsePreset(raw: Any?): Preset? {
            val preset = raw.asMap() ?: return null
            val label = preset["name"] as? String ?: return null
            val formula = label.filterNot(Char::isWhitespace)
            val function = Function.entries.firstOrNull { it.id == preset["id"] && formula.endsWith(it.labelSuffix) }
                ?: return null
            val center = preset["c"].finiteDouble() ?: return null
            val limit = preset["L"].finiteDouble() ?: return null
            val xMin = preset["xMin"].finiteDouble() ?: return null
            val xMax = preset["xMax"].finiteDouble() ?: return null
            val yMin = preset["yMin"].finiteDouble() ?: return null
            val yMax = preset["yMax"].finiteDouble() ?: return null
            if (xMin >= xMax || yMin >= yMax || center !in xMin..xMax || limit !in yMin..yMax) return null
            if (function == Function.SQUARE_ROOT && center <= 0.0) return null
            if (abs(function.evaluate(center) - limit) > 1e-6) return null
            return Preset(function, label, center, limit, xMin, xMax, yMin, yMax)
        }

        private fun Any?.finiteDouble() = asDouble()?.takeIf { it.isFinite() && abs(it) < 1e6 }
    }
}

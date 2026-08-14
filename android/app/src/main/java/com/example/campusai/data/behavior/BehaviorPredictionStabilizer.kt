package com.example.campusai.data.behavior

/** Runtime-only guardrails for the two-class RGB V1 model. */
data class BehaviorStabilityConfig(
    val emaAlpha: Float = 0.35f,
    val minimumConfidence: Float = 0.60f,
    val minimumMargin: Float = 0.15f,
    val stableFramesForSwitch: Int = 2,
)

data class StabilizedBehaviorPrediction(
    val probabilities: Map<StudyBehavior, Float>,
    val stableBehavior: StudyBehavior,
)

class BehaviorPredictionStabilizer(
    private val config: BehaviorStabilityConfig = BehaviorStabilityConfig(),
) {
    private var smoothedRead: Float? = null
    private var smoothedWrite: Float? = null
    private var stableBehavior = StudyBehavior.UNCERTAIN
    private var pendingBehavior = StudyBehavior.UNCERTAIN
    private var pendingFrames = 0

    fun stabilize(raw: BehaviorPrediction): StabilizedBehaviorPrediction {
        val read = raw.probabilities[StudyBehavior.READING] ?: 0f
        val write = raw.probabilities[StudyBehavior.WRITING] ?: 0f
        val alpha = config.emaAlpha.coerceIn(0f, 1f)

        smoothedRead = smoothedRead?.let { it + alpha * (read - it) } ?: read
        smoothedWrite = smoothedWrite?.let { it + alpha * (write - it) } ?: write

        val probabilities = mapOf(
            StudyBehavior.READING to smoothedRead!!,
            StudyBehavior.WRITING to smoothedWrite!!,
        )
        val candidate = reliableCandidate(smoothedRead!!, smoothedWrite!!)
        updateStableBehavior(candidate)

        return StabilizedBehaviorPrediction(probabilities, stableBehavior)
    }

    fun reset() {
        smoothedRead = null
        smoothedWrite = null
        stableBehavior = StudyBehavior.UNCERTAIN
        pendingBehavior = StudyBehavior.UNCERTAIN
        pendingFrames = 0
    }

    private fun reliableCandidate(read: Float, write: Float): StudyBehavior {
        val top = maxOf(read, write)
        val margin = kotlin.math.abs(read - write)
        if (top < config.minimumConfidence || margin < config.minimumMargin) {
            return StudyBehavior.UNCERTAIN
        }
        return if (read >= write) StudyBehavior.READING else StudyBehavior.WRITING
    }

    private fun updateStableBehavior(candidate: StudyBehavior) {
        if (candidate == StudyBehavior.UNCERTAIN) {
            stableBehavior = StudyBehavior.UNCERTAIN
            pendingBehavior = StudyBehavior.UNCERTAIN
            pendingFrames = 0
            return
        }
        if (candidate == stableBehavior) {
            pendingBehavior = StudyBehavior.UNCERTAIN
            pendingFrames = 0
            return
        }
        if (candidate == pendingBehavior) {
            pendingFrames++
        } else {
            pendingBehavior = candidate
            pendingFrames = 1
        }
        if (pendingFrames >= config.stableFramesForSwitch.coerceAtLeast(1)) {
            stableBehavior = candidate
            pendingBehavior = StudyBehavior.UNCERTAIN
            pendingFrames = 0
        }
    }
}

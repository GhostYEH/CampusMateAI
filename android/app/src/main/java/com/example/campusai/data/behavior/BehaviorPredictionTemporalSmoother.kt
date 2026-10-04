package com.example.campusai.data.behavior

/**
 * Applies EMA smoothing to model probabilities before product-level temporal rules.
 *
 * The smoother deliberately does not add a warm-up period: the first prediction is
 * returned unchanged so a focus session can begin observing immediately.
 */
data class BehaviorSmoothingConfig(
    val emaAlpha: Float = 0.35f,
)

class BehaviorPredictionTemporalSmoother(
    private val config: BehaviorSmoothingConfig = BehaviorSmoothingConfig(),
) {
    private var previousModelState: String? = null
    private var smoothedProbabilities: Map<StudyBehavior, Float> = emptyMap()

    fun smooth(raw: BehaviorPrediction): BehaviorPrediction {
        if (raw.probabilities.isEmpty()) {
            reset()
            return raw
        }

        if (previousModelState != null && previousModelState != raw.modelState) {
            smoothedProbabilities = emptyMap()
        }

        val alpha = config.emaAlpha.coerceIn(0f, 1f)
        val keys = smoothedProbabilities.keys + raw.probabilities.keys
        val next = keys.associateWith { behavior ->
            val current = raw.probabilities[behavior] ?: 0f
            val previous = smoothedProbabilities[behavior]
            previous?.let { it + alpha * (current - it) } ?: current
        }

        previousModelState = raw.modelState
        smoothedProbabilities = next
        val minimumConfidence = when (raw.modelState) {
            BehaviorV34Contract.MODEL_STATE -> BehaviorV34Contract.MINIMUM_CONFIDENCE
            BehaviorHybridPolicy.MODEL_STATE -> BehaviorHybridPolicy.MINIMUM_CONFIDENCE
            else -> return raw.copy(probabilities = next)
        }
        val ranked = next.entries.sortedByDescending { it.value }
        val top = ranked.first()
        val margin = top.value - (ranked.getOrNull(1)?.value ?: 0f)
        // Require agreement with the accepted runtime decision. This also preserves
        // hybrid restrictions such as writing eligibility and computer confirmation.
        val accepted = raw.stableBehavior != StudyBehavior.UNCERTAIN &&
            top.key == raw.stableBehavior &&
            top.value >= minimumConfidence && margin >= BehaviorV34Contract.MINIMUM_MARGIN
        return raw.copy(
            probabilities = next,
            stableBehavior = if (accepted) top.key else StudyBehavior.UNCERTAIN,
        )
    }

    fun reset() {
        previousModelState = null
        smoothedProbabilities = emptyMap()
    }
}

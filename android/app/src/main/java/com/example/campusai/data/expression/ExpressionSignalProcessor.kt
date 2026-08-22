package com.example.campusai.data.expression

import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.ExpressionResult

data class ExpressionSignalConfig(
    val emaAlpha: Double = 0.35,
    val minimumConfidence: Double,
    val classThresholds: Map<ExpressionLabel, Double> = emptyMap(),
    val minimumStableFrames: Int = 4,
    val minimumStableDurationMs: Long = 700,
    val suggestionCooldownMs: Long = 10 * 60 * 1000L,
)

class ExpressionSignalProcessor(
    private val config: ExpressionSignalConfig,
    private val modelVersion: String,
) {
    private var ema: Map<ExpressionLabel, Double>? = null
    private var candidate: ExpressionLabel? = null
    private var candidateFrames = 0
    private var candidateSince = 0L
    private var lastSuggestionAt = Long.MIN_VALUE

    fun process(
        rawProbabilities: Map<ExpressionLabel, Double>,
        timestamp: Long,
        hasFace: Boolean = true,
    ): ExpressionResult {
        if (!hasFace) {
            resetStability()
            ema = null
            return ExpressionResult(
                label = ExpressionLabel.NO_FACE,
                confidence = 0.0,
                probabilities = emptyMap(),
                timestamp = timestamp,
                isStable = false,
                modelVersion = modelVersion,
            )
        }
        val smoothed = ExpressionMath.modelLabels.associateWith { label ->
            val current = rawProbabilities[label] ?: 0.0
            val previous = ema?.get(label) ?: current
            config.emaAlpha * current + (1.0 - config.emaAlpha) * previous
        }.normalizeProbabilities()
        ema = smoothed
        val (topLabel, confidence) = smoothed.maxBy { it.value }
        val threshold = config.classThresholds[topLabel] ?: config.minimumConfidence
        if (confidence < threshold) {
            resetStability()
            return ExpressionResult(
                label = ExpressionLabel.UNKNOWN,
                confidence = confidence,
                probabilities = smoothed,
                timestamp = timestamp,
                isStable = false,
                modelVersion = modelVersion,
            )
        }
        if (candidate != topLabel) {
            candidate = topLabel
            candidateFrames = 1
            candidateSince = timestamp
        } else {
            candidateFrames += 1
        }
        val stable = candidateFrames >= config.minimumStableFrames &&
            timestamp - candidateSince >= config.minimumStableDurationMs
        return ExpressionResult(
            label = topLabel,
            confidence = confidence,
            probabilities = smoothed,
            timestamp = timestamp,
            isStable = stable,
            modelVersion = modelVersion,
        )
    }

    fun shouldOfferNeutralSuggestion(result: ExpressionResult, timestamp: Long): Boolean {
        if (!result.isStable || result.label in setOf(
                ExpressionLabel.UNKNOWN,
                ExpressionLabel.NO_FACE,
            )
        ) {
            return false
        }
        if (lastSuggestionAt != Long.MIN_VALUE &&
            timestamp - lastSuggestionAt < config.suggestionCooldownMs
        ) {
            return false
        }
        lastSuggestionAt = timestamp
        return true
    }

    fun reset() {
        ema = null
        resetStability()
    }

    private fun resetStability() {
        candidate = null
        candidateFrames = 0
        candidateSince = 0L
    }

    private fun Map<ExpressionLabel, Double>.normalizeProbabilities(): Map<ExpressionLabel, Double> {
        val sum = values.sum().takeIf { it > 0.0 } ?: 1.0
        return mapValues { (_, value) -> value / sum }
    }
}

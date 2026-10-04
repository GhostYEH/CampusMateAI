package com.example.campusai.data.expression

import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.LearningStateLabel
import kotlin.math.exp

object ExpressionMath {
    val modelLabels = listOf(
        ExpressionLabel.ANGRY,
        ExpressionLabel.DISGUST,
        ExpressionLabel.FEAR,
        ExpressionLabel.HAPPY,
        ExpressionLabel.NEUTRAL,
        ExpressionLabel.SAD,
        ExpressionLabel.SURPRISE,
    )

    val learningStateLabels = listOf(
        LearningStateLabel.BOREDOM,
        LearningStateLabel.CONFUSION,
        LearningStateLabel.FRUSTRATION,
    )

    fun softmax(logits: FloatArray): DoubleArray {
        require(logits.isNotEmpty())
        val maximum = logits.max()
        val exponentials = logits.map { exp((it - maximum).toDouble()) }
        val total = exponentials.sum()
        return exponentials.map { it / total }.toDoubleArray()
    }

    fun calibratedExpressionProbabilities(logits: FloatArray, temperature: Double): DoubleArray {
        require(logits.size == modelLabels.size)
        require(temperature.isFinite() && temperature > 0.0)
        return softmax(FloatArray(logits.size) { (logits[it] / temperature).toFloat() })
    }

    fun sigmoid(value: Double): Double = when {
        value >= 0.0 -> 1.0 / (1.0 + kotlin.math.exp(-value))
        else -> {
            val exponential = kotlin.math.exp(value)
            exponential / (1.0 + exponential)
        }
    }

    fun normalizePixel(value: Int, mean: Double, std: Double): Float {
        require(std > 0.0)
        return (((value.coerceIn(0, 255) / 255.0) - mean) / std).toFloat()
    }

    fun toProbabilityMap(probabilities: DoubleArray): Map<ExpressionLabel, Double> {
        require(probabilities.size == modelLabels.size)
        return modelLabels.zip(probabilities.toList()).toMap()
    }
}

package com.example.campusai.data.expression

import com.example.campusai.data.model.ExpressionLabel
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

    fun softmax(logits: FloatArray): DoubleArray {
        require(logits.isNotEmpty())
        val maximum = logits.max()
        val exponentials = logits.map { exp((it - maximum).toDouble()) }
        val total = exponentials.sum()
        return exponentials.map { it / total }.toDoubleArray()
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

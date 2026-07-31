package com.example.campusai.data.model

enum class ExpressionLabel {
    HAPPY,
    NEUTRAL,
    SAD,
    ANGRY,
    FEAR,
    SURPRISE,
    DISGUST,
    UNKNOWN,
    NO_FACE,
}

data class ExpressionResult(
    val label: ExpressionLabel,
    val confidence: Double,
    val probabilities: Map<ExpressionLabel, Double>,
    val timestamp: Long,
    val isStable: Boolean,
    val modelVersion: String,
)

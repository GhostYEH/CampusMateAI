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
    /** ML Kit 本机人脸检测信号，仅用于学习状态辅助，不保存画面。 */
    val facePresent: Boolean = false,
    val headEulerAngleX: Double? = null,
    val headEulerAngleY: Double? = null,
    val headEulerAngleZ: Double? = null,
    val leftEyeOpenProbability: Double? = null,
    val rightEyeOpenProbability: Double? = null,
)

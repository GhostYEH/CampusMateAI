package com.example.campusai.data.behavior

enum class StudyBehavior {
    READING,
    WRITING,
    TYPING,
    PAGE_TURNING,
    DRINKING,
    STRETCHING,

    PEN_SPINNING,
    PEN_FIDGETING,
    FACE_TOUCHING,
    OBJECT_FIDGETING,
    LOOKING_AWAY,
    HAIR_PLAYING,

    PHONE_USE,
    PHONE_PICKUP,
    TALKING,
    EATING,

    HEAD_DOWN,
    DROWSY,
    SLEEPING,

    ABSENT,
    UNKNOWN
}

data class BehaviorPrediction(
    val probabilities: Map<StudyBehavior, Float>,
    val timestampMs: Long,
    val modelState: String
)

package com.example.campusai.data.behavior

enum class StudyBehavior {
    /** V3.1/V3.2: no clearly observable study action in the current image. */
    IDLE,
    /** V3.1/V3.2: a clearly observable reading, writing, or material interaction action. */
    VISIBLE_STUDY,

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

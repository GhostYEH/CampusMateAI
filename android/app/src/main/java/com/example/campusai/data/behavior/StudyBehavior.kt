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
    UNKNOWN,

    /** Runtime decision only; the V1 ONNX model has no third output class. */
    UNCERTAIN,
}

data class BehaviorPrediction(
    val probabilities: Map<StudyBehavior, Float>,
    val timestampMs: Long,
    val modelState: String,
    /**
     * The runtime-stabilized V1 result. UNCERTAIN means the frame sequence is
     * not reliable enough to present as reading or writing.
     */
    val stableBehavior: StudyBehavior = StudyBehavior.UNCERTAIN,
)

package com.example.campusai.data.behavior

enum class StudyBehavior {
    /** V3.1: no clearly observable study action in the current image. */
    IDLE,
    /** V3.1: a clearly observable reading, writing, or material interaction action. */
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
    
    // Performance baseline metrics (V3.1.1)
    val debugInferenceLatencyMs: Long = -1L,
    val debugPreprocessingLatencyMs: Long = -1L,
)

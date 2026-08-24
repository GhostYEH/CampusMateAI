package com.example.campusai.data.behavior

data class BehaviorV34DecodedOutput(
    val probabilities: Map<StudyBehavior, Float>,
    val acceptedBehavior: StudyBehavior,
) {
    val isAccepted: Boolean
        get() = acceptedBehavior != StudyBehavior.UNCERTAIN
}

/** Exact runtime contract recorded in the V3.4 model card. */
object BehaviorV34Contract {
    const val MODEL_STATE = "READY_BEHAVIOR_V34"
    const val TEMPERATURE = 4.841172366232762f
    const val MINIMUM_CONFIDENCE = 0.30f
    const val MINIMUM_MARGIN = 0.05f

    val outputBehaviors = arrayOf(
        StudyBehavior.READING,
        StudyBehavior.WRITING,
        StudyBehavior.PHONE_USE,
        StudyBehavior.IDLE,
    )

    fun decode(logits: FloatArray): BehaviorV34DecodedOutput {
        require(logits.size == outputBehaviors.size) {
            "Expected ${outputBehaviors.size} V3.4 logits, got ${logits.size}"
        }
        val calibrated = FloatArray(logits.size) { logits[it] / TEMPERATURE }
        val values = BehaviorModelMath.softmax(calibrated)
        val probabilities = outputBehaviors.indices.associate { index ->
            outputBehaviors[index] to values[index]
        }
        val ranked = values.indices.sortedByDescending { values[it] }
        val topIndex = ranked[0]
        val top = values[topIndex]
        val margin = top - values[ranked[1]]
        val accepted = if (top >= MINIMUM_CONFIDENCE && margin >= MINIMUM_MARGIN) {
            outputBehaviors[topIndex]
        } else {
            StudyBehavior.UNCERTAIN
        }
        return BehaviorV34DecodedOutput(probabilities, accepted)
    }
}


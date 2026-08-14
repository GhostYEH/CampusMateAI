package com.example.campusai.data.behavior

enum class StableBehaviorEvent {
    PHONE_DISTRACTION,
    LONG_LOOK_AWAY,
    PEN_FIDGETING,
    DROWSINESS,
    SLEEPING,
    STUDENT_ABSENT,
    FOCUS_RECOVERED,
    POSSIBLE_DISTRACTION,
    STABLE_LEARNING
}

class BehaviorSignalProcessor {

    fun process(prediction: BehaviorPrediction): List<StableBehaviorEvent> {
        if (prediction.modelState != "READY_RGB_V1") return emptyList()

        // V1 only knows READ/WRITE. It must never manufacture distraction,
        // absence, or fatigue evidence from probabilities it cannot produce.
        return if (
            prediction.stableBehavior == StudyBehavior.READING ||
            prediction.stableBehavior == StudyBehavior.WRITING
        ) {
            listOf(StableBehaviorEvent.STABLE_LEARNING)
        } else {
            emptyList()
        }
    }

    fun reset() {
        // V1 has no temporal state beyond BehaviorPredictionStabilizer.
    }
}

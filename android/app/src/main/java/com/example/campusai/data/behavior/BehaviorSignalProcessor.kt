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

data class BehaviorSignalConfig(
    val phoneUseThresholdMs: Long = 3000L,
    val lookAwayThresholdMs: Long = 5000L,
    val penFidgetingThresholdMs: Long = 10000L,
    val absentThresholdMs: Long = 10000L,
    val learningRecoveryThresholdMs: Long = 5000L,
    val confidenceThreshold: Float = 0.5f,
    val startupWarmupMs: Long = 1500L,
    val stableBehaviorWindowMs: Long = 2000L,
    val stableBehaviorDominantRatio: Float = 0.70f,
    val stableBehaviorAverageConfidence: Float = 0.65f,
)

sealed class BehaviorDisplayState {
    object Observing : BehaviorDisplayState()
    object NoStableBehavior : BehaviorDisplayState()
    data class Stable(
        val behavior: StudyBehavior,
        val confidence: Float,
    ) : BehaviorDisplayState()
}

class BehaviorSignalProcessor(
    private val config: BehaviorSignalConfig = BehaviorSignalConfig()
) {
    private var lastPhoneUseStart = 0L
    private var lastLookAwayStart = 0L
    private var lastPenFidgetingStart = 0L
    private var lastAbsentStart = 0L
    private var lastLearningStart = 0L

    private var currentlyAbsent = false
    private var currentlyPhoneDistracted = false
    private var currentlyFidgeting = false
    private var currentlyLookingAway = false
    private var behaviorObservationStartedAt = 0L
    private val behaviorSamples = ArrayDeque<BehaviorSample>()

    /** Starts the UI-only observation window for the current focus session. */
    fun beginBehaviorObservation(startedAtMs: Long) {
        behaviorObservationStartedAt = startedAtMs
        behaviorSamples.clear()
    }

    /**
     * Converts raw V3.1 predictions into the state shown by Focus.
     */
    fun processDisplayState(prediction: BehaviorPrediction): BehaviorDisplayState {
        if (prediction.modelState !in SUPPORTED_MODEL_STATES || prediction.probabilities.isEmpty()) {
            return BehaviorDisplayState.Observing
        }

        if (behaviorObservationStartedAt == 0L) {
            beginBehaviorObservation(prediction.timestampMs)
        }

        val top = prediction.probabilities
            .filterKeys { it in UI_BEHAVIORS }
            .maxByOrNull { it.value }
            ?: return BehaviorDisplayState.NoStableBehavior
        behaviorSamples.addLast(
            BehaviorSample(
                behavior = top.key,
                confidence = top.value,
                timestampMs = prediction.timestampMs,
            ),
        )
        val windowStart = prediction.timestampMs - config.stableBehaviorWindowMs
        while ((behaviorSamples.firstOrNull()?.timestampMs ?: Long.MAX_VALUE) < windowStart) {
            behaviorSamples.removeFirst()
        }

        if (prediction.timestampMs - behaviorObservationStartedAt < config.startupWarmupMs) {
            return BehaviorDisplayState.Observing
        }

        val samples = behaviorSamples.toList()
        if (samples.isEmpty()) return BehaviorDisplayState.NoStableBehavior
        val dominant = samples.groupBy { it.behavior }
            .maxByOrNull { (_, values) -> values.size }
            ?: return BehaviorDisplayState.NoStableBehavior
        val dominantRatio = dominant.value.size.toFloat() / samples.size
        val averageConfidence = dominant.value.map { it.confidence }.average().toFloat()
        return if (
            dominantRatio >= config.stableBehaviorDominantRatio &&
            averageConfidence >= config.stableBehaviorAverageConfidence
        ) {
            BehaviorDisplayState.Stable(dominant.key, averageConfidence)
        } else {
            BehaviorDisplayState.NoStableBehavior
        }
    }

    fun process(prediction: BehaviorPrediction): List<StableBehaviorEvent> {
        val now = prediction.timestampMs
        val events = mutableListOf<StableBehaviorEvent>()
        
        if (prediction.modelState == "MODEL_NOT_AVAILABLE" || prediction.probabilities.isEmpty()) {
            return events
        }

        val probs = prediction.probabilities

        // Check Absent
        if (probs[StudyBehavior.ABSENT] ?: 0f > config.confidenceThreshold) {
            if (lastAbsentStart == 0L) lastAbsentStart = now
            if (!currentlyAbsent && now - lastAbsentStart >= config.absentThresholdMs) {
                currentlyAbsent = true
                events.add(StableBehaviorEvent.STUDENT_ABSENT)
            }
        } else {
            if (currentlyAbsent) {
                if (lastLearningStart == 0L) lastLearningStart = now
                if (now - lastLearningStart >= config.learningRecoveryThresholdMs) {
                    currentlyAbsent = false
                    events.add(StableBehaviorEvent.FOCUS_RECOVERED)
                    lastAbsentStart = 0L
                }
            } else {
                lastAbsentStart = 0L
            }
        }

        // Check Phone Use
        val phoneProb = (probs[StudyBehavior.PHONE_USE] ?: 0f) + (probs[StudyBehavior.PHONE_PICKUP] ?: 0f)
        if (phoneProb > config.confidenceThreshold) {
            if (lastPhoneUseStart == 0L) lastPhoneUseStart = now
            if (!currentlyPhoneDistracted && now - lastPhoneUseStart >= config.phoneUseThresholdMs) {
                currentlyPhoneDistracted = true
                events.add(StableBehaviorEvent.PHONE_DISTRACTION)
            }
        } else {
            lastPhoneUseStart = 0L
            currentlyPhoneDistracted = false
        }

        // Check Look Away
        if (probs[StudyBehavior.LOOKING_AWAY] ?: 0f > config.confidenceThreshold) {
            if (lastLookAwayStart == 0L) lastLookAwayStart = now
            if (!currentlyLookingAway && now - lastLookAwayStart >= config.lookAwayThresholdMs) {
                currentlyLookingAway = true
                events.add(StableBehaviorEvent.LONG_LOOK_AWAY)
            }
        } else {
            lastLookAwayStart = 0L
            currentlyLookingAway = false
        }

        // Check Pen Fidgeting
        val penProb = (probs[StudyBehavior.PEN_SPINNING] ?: 0f) + (probs[StudyBehavior.PEN_FIDGETING] ?: 0f)
        val writingProb = probs[StudyBehavior.WRITING] ?: 0f
        if (penProb > config.confidenceThreshold) {
            if (lastPenFidgetingStart == 0L) lastPenFidgetingStart = now
            if (!currentlyFidgeting && now - lastPenFidgetingStart >= config.penFidgetingThresholdMs) {
                currentlyFidgeting = true
                if (writingProb < 0.3f && currentlyLookingAway) {
                    events.add(StableBehaviorEvent.POSSIBLE_DISTRACTION)
                } else {
                    events.add(StableBehaviorEvent.PEN_FIDGETING)
                }
            }
        } else {
            lastPenFidgetingStart = 0L
            currentlyFidgeting = false
        }

        // Check Learning
        val learningProb = (probs[StudyBehavior.READING] ?: 0f) + (probs[StudyBehavior.WRITING] ?: 0f) + (probs[StudyBehavior.TYPING] ?: 0f)
        if (learningProb > config.confidenceThreshold && !currentlyAbsent && !currentlyPhoneDistracted) {
            events.add(StableBehaviorEvent.STABLE_LEARNING)
            lastLearningStart = now
        }

        return events
    }

    fun reset() {
        lastPhoneUseStart = 0L
        lastLookAwayStart = 0L
        lastPenFidgetingStart = 0L
        lastAbsentStart = 0L
        lastLearningStart = 0L
        currentlyAbsent = false
        currentlyPhoneDistracted = false
        currentlyFidgeting = false
        currentlyLookingAway = false
        behaviorObservationStartedAt = 0L
        behaviorSamples.clear()
    }

    private data class BehaviorSample(
        val behavior: StudyBehavior,
        val confidence: Float,
        val timestampMs: Long,
    )

    private companion object {
        val UI_BEHAVIORS = setOf(
            StudyBehavior.IDLE,
            StudyBehavior.VISIBLE_STUDY,
            StudyBehavior.READING,
            StudyBehavior.WRITING,
            StudyBehavior.PHONE_USE,
        )
        val SUPPORTED_MODEL_STATES = setOf("READY_VISIBLE_STUDY_V31", "READY_RGB_V2")
    }
}

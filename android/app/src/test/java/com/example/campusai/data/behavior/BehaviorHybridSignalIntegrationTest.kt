package com.example.campusai.data.behavior

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BehaviorHybridSignalIntegrationTest {
    @Test
    fun confirmedComputerIsShownAndCountsAsLearningEvidence() {
        val processor = BehaviorSignalProcessor(
            BehaviorSignalConfig(
                startupWarmupMs = 0L,
                stableBehaviorWindowMs = 2_000L,
                stableBehaviorDominantRatio = 0.5f,
                stableBehaviorAverageConfidence = 0.5f,
            ),
        )
        val prediction = BehaviorPrediction(
            probabilities = mapOf(StudyBehavior.COMPUTER to 0.85f, StudyBehavior.IDLE to 0.15f),
            timestampMs = 1_000L,
            modelState = BehaviorHybridPolicy.MODEL_STATE,
            stableBehavior = StudyBehavior.COMPUTER,
        )

        assertEquals(
            BehaviorDisplayState.Stable(StudyBehavior.COMPUTER, 0.85f),
            processor.processDisplayState(prediction),
        )
        assertTrue(StableBehaviorEvent.STABLE_LEARNING in processor.process(prediction))
    }

    @Test
    fun uncertainHybridPhoneEvidenceDoesNotTriggerDistraction() {
        val processor = BehaviorSignalProcessor(BehaviorSignalConfig(phoneUseThresholdMs = 0L))
        val prediction = BehaviorPrediction(
            probabilities = mapOf(StudyBehavior.PHONE_USE to 0.80f, StudyBehavior.IDLE to 0.20f),
            timestampMs = 1_000L,
            modelState = BehaviorHybridPolicy.MODEL_STATE,
            stableBehavior = StudyBehavior.UNCERTAIN,
        )

        assertTrue(StableBehaviorEvent.PHONE_DISTRACTION !in processor.process(prediction))
    }
}

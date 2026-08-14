package com.example.campusai.data.behavior

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BehaviorSignalProcessorTest {
    @Test
    fun stableReadOrWriteIsLearningEvidenceOnly() {
        val events = BehaviorSignalProcessor().process(
            BehaviorPrediction(
                probabilities = mapOf(StudyBehavior.READING to .9f, StudyBehavior.WRITING to .1f),
                timestampMs = 1L,
                modelState = "READY_RGB_V1",
                stableBehavior = StudyBehavior.READING,
            ),
        )

        assertEquals(listOf(StableBehaviorEvent.STABLE_LEARNING), events)
    }

    @Test
    fun uncertainV1ResultNeverCreatesUnsupportedBehaviorEvent() {
        val events = BehaviorSignalProcessor().process(
            BehaviorPrediction(
                probabilities = mapOf(StudyBehavior.READING to .52f, StudyBehavior.WRITING to .48f),
                timestampMs = 1L,
                modelState = "READY_RGB_V1",
                stableBehavior = StudyBehavior.UNCERTAIN,
            ),
        )

        assertTrue(events.isEmpty())
    }
}

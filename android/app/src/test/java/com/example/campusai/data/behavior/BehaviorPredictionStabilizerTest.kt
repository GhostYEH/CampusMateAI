package com.example.campusai.data.behavior

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BehaviorPredictionStabilizerTest {
    @Test
    fun continuousReadingBecomesStable() {
        val stabilizer = BehaviorPredictionStabilizer()
        stabilizer.stabilize(prediction(read = .9f, write = .1f))
        val result = stabilizer.stabilize(prediction(read = .9f, write = .1f))
        assertEquals(StudyBehavior.READING, result.stableBehavior)
    }

    @Test
    fun continuousWritingBecomesStable() {
        val stabilizer = BehaviorPredictionStabilizer()
        stabilizer.stabilize(prediction(read = .1f, write = .9f))
        val result = stabilizer.stabilize(prediction(read = .1f, write = .9f))
        assertEquals(StudyBehavior.WRITING, result.stableBehavior)
    }

    @Test
    fun singleOppositeFrameDoesNotSwitchStableResult() {
        val stabilizer = BehaviorPredictionStabilizer()
        repeat(2) { stabilizer.stabilize(prediction(read = .9f, write = .1f)) }
        val result = stabilizer.stabilize(prediction(read = .1f, write = .9f))
        assertEquals(StudyBehavior.READING, result.stableBehavior)
    }

    @Test
    fun sustainedChangeEventuallySwitchesResult() {
        val stabilizer = BehaviorPredictionStabilizer()
        repeat(2) { stabilizer.stabilize(prediction(read = .9f, write = .1f)) }
        repeat(5) { stabilizer.stabilize(prediction(read = .1f, write = .9f)) }
        val result = stabilizer.stabilize(prediction(read = .1f, write = .9f))
        assertEquals(StudyBehavior.WRITING, result.stableBehavior)
    }

    @Test
    fun lowConfidenceAndSmallMarginAreUncertain() {
        val lowConfidence = BehaviorPredictionStabilizer()
            .stabilize(prediction(read = .55f, write = .45f))
        assertEquals(StudyBehavior.UNCERTAIN, lowConfidence.stableBehavior)

        val smallMargin = BehaviorPredictionStabilizer(
            BehaviorStabilityConfig(minimumConfidence = .5f, minimumMargin = .15f),
        ).stabilize(prediction(read = .55f, write = .45f))
        assertEquals(StudyBehavior.UNCERTAIN, smallMargin.stableBehavior)
    }

    @Test
    fun resetClearsStabilityHistory() {
        val stabilizer = BehaviorPredictionStabilizer()
        repeat(2) { stabilizer.stabilize(prediction(read = .9f, write = .1f)) }
        stabilizer.reset()
        val result = stabilizer.stabilize(prediction(read = .9f, write = .1f))
        assertEquals(StudyBehavior.UNCERTAIN, result.stableBehavior)
        assertTrue(result.probabilities[StudyBehavior.READING]!! > .8f)
    }

    private fun prediction(read: Float, write: Float) = BehaviorPrediction(
        probabilities = mapOf(
            StudyBehavior.READING to read,
            StudyBehavior.WRITING to write,
        ),
        timestampMs = 1L,
        modelState = "READY_RGB_V1",
    )
}

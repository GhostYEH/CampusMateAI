package com.example.campusai.data.behavior

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BehaviorHybridPolicyTest {
    @Test
    fun tsmOutputUsesExportedFiveClassOrder() {
        val decoded = BehaviorTsmContract.decode(floatArrayOf(0f, 0f, 0f, 10f, 0f))

        assertEquals(StudyBehavior.COMPUTER, decoded.maxByOrNull { it.value }?.key)
        assertEquals(1f, decoded.values.sum(), 0.0001f)
    }

    @Test
    fun temporalPhoneEvidenceCanCorrectSingleFrameReading() {
        val result = BehaviorHybridPolicy.fuse(
            single = mapOf(
                StudyBehavior.READING to 0.55f,
                StudyBehavior.WRITING to 0.03f,
                StudyBehavior.PHONE_USE to 0.40f,
                StudyBehavior.IDLE to 0.02f,
            ),
            temporal = mapOf(
                StudyBehavior.READING to 0.05f,
                StudyBehavior.WRITING to 0.02f,
                StudyBehavior.PHONE_USE to 0.90f,
                StudyBehavior.COMPUTER to 0.01f,
                StudyBehavior.IDLE to 0.02f,
            ),
            computerConfirmed = false,
        )

        assertEquals(StudyBehavior.PHONE_USE, result.acceptedBehavior)
    }

    @Test
    fun weakTemporalWritingCannotOverrideStrongSingleFramePhone() {
        val result = BehaviorHybridPolicy.fuse(
            single = mapOf(
                StudyBehavior.READING to 0.05f,
                StudyBehavior.WRITING to 0.10f,
                StudyBehavior.PHONE_USE to 0.80f,
                StudyBehavior.IDLE to 0.05f,
            ),
            temporal = mapOf(
                StudyBehavior.READING to 0.02f,
                StudyBehavior.WRITING to 0.90f,
                StudyBehavior.PHONE_USE to 0.03f,
                StudyBehavior.COMPUTER to 0.02f,
                StudyBehavior.IDLE to 0.03f,
            ),
            computerConfirmed = false,
        )

        assertEquals(StudyBehavior.PHONE_USE, result.acceptedBehavior)
    }

    @Test
    fun temporalWritingCannotTipANearTieAwayFromSingleFrameReading() {
        val result = BehaviorHybridPolicy.fuse(
            single = mapOf(
                StudyBehavior.READING to 0.42f,
                StudyBehavior.WRITING to 0.40f,
                StudyBehavior.PHONE_USE to 0.10f,
                StudyBehavior.IDLE to 0.08f,
            ),
            temporal = mapOf(
                StudyBehavior.READING to 0.03f,
                StudyBehavior.WRITING to 0.90f,
                StudyBehavior.PHONE_USE to 0.02f,
                StudyBehavior.COMPUTER to 0.02f,
                StudyBehavior.IDLE to 0.03f,
            ),
            computerConfirmed = false,
        )

        assertFalse(result.acceptedBehavior == StudyBehavior.WRITING)
    }

    @Test
    fun computerNeedsTwoTemporalConfirmations() {
        val single = mapOf(
            StudyBehavior.READING to 0.10f,
            StudyBehavior.WRITING to 0.05f,
            StudyBehavior.PHONE_USE to 0.05f,
            StudyBehavior.IDLE to 0.80f,
        )
        val temporal = mapOf(
            StudyBehavior.READING to 0.02f,
            StudyBehavior.WRITING to 0.02f,
            StudyBehavior.PHONE_USE to 0.02f,
            StudyBehavior.COMPUTER to 0.90f,
            StudyBehavior.IDLE to 0.04f,
        )

        assertFalse(
            BehaviorHybridPolicy.fuse(single, temporal, computerConfirmed = false)
                .acceptedBehavior == StudyBehavior.COMPUTER,
        )
        assertEquals(
            StudyBehavior.COMPUTER,
            BehaviorHybridPolicy.fuse(single, temporal, computerConfirmed = true).acceptedBehavior,
        )
    }

    @Test
    fun bothModelsAmbiguousProducesUncertain() {
        val result = BehaviorHybridPolicy.fuse(
            single = mapOf(
                StudyBehavior.READING to 0.28f,
                StudyBehavior.WRITING to 0.25f,
                StudyBehavior.PHONE_USE to 0.24f,
                StudyBehavior.IDLE to 0.23f,
            ),
            temporal = mapOf(
                StudyBehavior.READING to 0.24f,
                StudyBehavior.WRITING to 0.23f,
                StudyBehavior.PHONE_USE to 0.27f,
                StudyBehavior.COMPUTER to 0.02f,
                StudyBehavior.IDLE to 0.24f,
            ),
            computerConfirmed = false,
        )

        assertEquals(StudyBehavior.UNCERTAIN, result.acceptedBehavior)
    }

    @Test
    fun temporalTriggerRequiresEightFramesAndTwoSecondCooldown() {
        val uncertain = prediction(
            StudyBehavior.READING to 0.34f,
            StudyBehavior.WRITING to 0.31f,
            StudyBehavior.PHONE_USE to 0.20f,
            StudyBehavior.IDLE to 0.15f,
        )

        assertFalse(BehaviorHybridPolicy.shouldRunTemporal(uncertain, null, 5_000L, 0L, 7))
        assertFalse(BehaviorHybridPolicy.shouldRunTemporal(uncertain, null, 5_000L, 4_000L, 16))
        assertTrue(BehaviorHybridPolicy.shouldRunTemporal(uncertain, null, 5_000L, 2_000L, 16))
    }

    @Test
    fun stableHighConfidenceResultStillGetsPeriodicTemporalCheck() {
        val reading = prediction(
            StudyBehavior.READING to 0.85f,
            StudyBehavior.WRITING to 0.05f,
            StudyBehavior.PHONE_USE to 0.05f,
            StudyBehavior.IDLE to 0.05f,
        )

        assertFalse(BehaviorHybridPolicy.shouldRunTemporal(reading, StudyBehavior.READING, 4_500L, 2_000L, 16))
        assertTrue(BehaviorHybridPolicy.shouldRunTemporal(reading, StudyBehavior.READING, 5_000L, 2_000L, 16))
    }

    private fun prediction(vararg probabilities: Pair<StudyBehavior, Float>) = BehaviorPrediction(
        probabilities = mapOf(*probabilities),
        timestampMs = 0L,
        modelState = BehaviorV34Contract.MODEL_STATE,
        stableBehavior = probabilities.maxByOrNull { it.second }?.first ?: StudyBehavior.UNCERTAIN,
    )
}

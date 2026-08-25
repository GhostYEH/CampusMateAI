package com.example.campusai.data.behavior

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BehaviorEventAggregatorTest {
    @Test
    fun singlePhoneFrameDoesNotCreateEvent() {
        val aggregator = BehaviorEventAggregator(phoneEnterMs = 2_000L, exitMs = 1_000L)

        assertTrue(aggregator.update(BehaviorFramePrediction(0L, BehaviorProductLabel.PHONE_INTERACTION, 0.9f, true)).isEmpty())
    }

    @Test
    fun sustainedPhoneCreatesEventAndUncertainDoesNotResetIt() {
        val aggregator = BehaviorEventAggregator(phoneEnterMs = 2_000L, exitMs = 1_000L)
        aggregator.update(BehaviorFramePrediction(0L, BehaviorProductLabel.PHONE_INTERACTION, 0.9f, true))
        aggregator.update(BehaviorFramePrediction(1_000L, BehaviorProductLabel.UNCERTAIN, 0f, false))

        val event = aggregator.update(BehaviorFramePrediction(2_000L, BehaviorProductLabel.PHONE_INTERACTION, 0.9f, true)).single()

        assertTrue(event.active)
        assertTrue(event.reminderAllowed)
    }

    @Test
    fun exitNeedsHysteresisAndRestartRespectsCooldown() {
        val aggregator = BehaviorEventAggregator(
            phoneEnterMs = 2_000L,
            exitMs = 1_000L,
            reminderCooldownMs = 600_000L,
        )
        aggregator.update(BehaviorFramePrediction(0L, BehaviorProductLabel.PHONE_INTERACTION, 0.9f, true))
        aggregator.update(BehaviorFramePrediction(2_000L, BehaviorProductLabel.PHONE_INTERACTION, 0.9f, true))
        assertTrue(aggregator.update(BehaviorFramePrediction(2_500L, BehaviorProductLabel.STUDY_ACTIVITY, 0.9f, true)).isEmpty())
        assertFalse(aggregator.update(BehaviorFramePrediction(3_500L, BehaviorProductLabel.STUDY_ACTIVITY, 0.9f, true)).single().active)
        aggregator.update(BehaviorFramePrediction(4_000L, BehaviorProductLabel.PHONE_INTERACTION, 0.9f, true))

        val restarted = aggregator.update(BehaviorFramePrediction(6_000L, BehaviorProductLabel.PHONE_INTERACTION, 0.9f, true)).single()

        assertTrue(restarted.active)
        assertFalse(restarted.reminderAllowed)
    }
}

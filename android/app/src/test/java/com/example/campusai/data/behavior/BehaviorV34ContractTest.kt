package com.example.campusai.data.behavior

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BehaviorV34ContractTest {

    @Test
    fun decodesCalibratedFourClassOutputInPackagedOrder() {
        val result = BehaviorV34Contract.decode(floatArrayOf(10f, 0f, 0f, 0f))

        assertEquals(StudyBehavior.READING, result.acceptedBehavior)
        assertTrue(result.probabilities.getValue(StudyBehavior.READING) in 0.70f..0.75f)
        assertEquals(1f, result.probabilities.values.sum(), 0.0001f)
    }

    @Test
    fun rejectsPredictionWhenTopTwoClassesHaveInsufficientMargin() {
        val result = BehaviorV34Contract.decode(floatArrayOf(1f, 1f, 0f, 0f))

        assertEquals(StudyBehavior.UNCERTAIN, result.acceptedBehavior)
        assertFalse(result.isAccepted)
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsWrongOutputSizeBeforeMappingLabels() {
        BehaviorV34Contract.decode(floatArrayOf(1f, 2f))
    }
}


package com.example.campusai.data.expression

import com.example.campusai.data.model.LearningStateLabel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LearningStateWindowTest {
    @Test
    fun averagesRawLogitsThenAppliesPerStateCalibration() {
        val window = LearningStateWindow(
            requiredFrames = 4,
            scales = doubleArrayOf(2.0, 0.5, 1.0),
            biases = doubleArrayOf(-1.0, 1.0, 0.0),
        )
        repeat(3) { index ->
            val pending = window.add(floatArrayOf(0f, 2f, -1f), 9, 1_000L + index * 200L)
            assertTrue(pending.probabilities.isEmpty())
            assertEquals(index + 1, pending.frameCount)
        }
        val ready = window.add(floatArrayOf(0f, 2f, -1f), 9, 1_600L)
        assertEquals(4, ready.frameCount)
        assertEquals(ExpressionMath.sigmoid(-1.0), ready.probabilities.getValue(LearningStateLabel.BOREDOM), 1e-9)
        assertEquals(ExpressionMath.sigmoid(2.0), ready.probabilities.getValue(LearningStateLabel.CONFUSION), 1e-9)
        assertEquals(ExpressionMath.sigmoid(-1.0), ready.probabilities.getValue(LearningStateLabel.FRUSTRATION), 1e-9)
    }

    @Test
    fun identityChangesInvalidFramesAndLongGapsClearTheWindow() {
        val window = LearningStateWindow(requiredFrames = 4, maxAgeMs = 1_000)
        repeat(3) { index -> window.add(floatArrayOf(0f, 0f, 0f), 9, 1_000L + index * 200L) }
        assertEquals(1, window.add(floatArrayOf(0f, 0f, 0f), 10, 1_600L).frameCount)
        assertEquals(0, window.add(floatArrayOf(0f, Float.NaN, 0f), 10, 1_800L).frameCount)
        repeat(3) { index -> window.add(floatArrayOf(0f, 0f, 0f), 10, 2_000L + index * 200L) }
        assertEquals(1, window.add(floatArrayOf(0f, 0f, 0f), 10, 7_000L).frameCount)
        assertEquals(0, window.add(floatArrayOf(0f, 0f, 0f), null, 7_200L).frameCount)
    }
}

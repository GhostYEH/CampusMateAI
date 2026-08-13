package com.example.campusai.data.behavior

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BehaviorModelMathTest {

    @Test
    fun softmax2ReturnsNormalizedProbabilities() {
        val probs = BehaviorModelMath.softmax2(2.0f, 1.0f)

        assertEquals(1.0f, probs[0] + probs[1], 1e-6f)
        assertTrue(probs[0] > probs[1])
    }

    @Test
    fun softmax2IsStableForLargeLogits() {
        val probs = BehaviorModelMath.softmax2(1000.0f, 999.0f)

        assertEquals(1.0f, probs[0] + probs[1], 1e-6f)
        assertTrue(probs[0].isFinite())
        assertTrue(probs[1].isFinite())
    }
}

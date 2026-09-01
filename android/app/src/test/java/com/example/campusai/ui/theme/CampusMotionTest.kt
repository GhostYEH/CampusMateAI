package com.example.campusai.ui.theme

import org.junit.Assert.assertEquals
import org.junit.Test

class CampusMotionTest {
    @Test
    fun ambientLayerUsesSubtleDetailWithoutMotionReduction() {
        assertEquals(8, CampusMotion.ambientOrbCount)
        assertEquals(0.18f, CampusMotion.ambientOpacity(false))
        assertEquals(6f, CampusMotion.parallaxAmplitude(false, 6f))
        assertEquals(-2.5f, CampusMotion.enterTilt(false, -2.5f))
    }

    @Test
    fun ambientLayerBecomesStaticAndNonDistractingWhenMotionIsReduced() {
        assertEquals(0f, CampusMotion.ambientOpacity(true))
        assertEquals(0f, CampusMotion.parallaxAmplitude(true, 6f))
        assertEquals(0f, CampusMotion.enterTilt(true, 0f))
    }
}

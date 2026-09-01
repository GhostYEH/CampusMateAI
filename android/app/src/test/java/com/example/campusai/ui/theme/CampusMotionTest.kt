package com.example.campusai.ui.theme

import org.junit.Assert.assertEquals
import org.junit.Test

class CampusMotionTest {
    @Test
    fun `stagger delay is lively but capped for long lists`() {
        assertEquals(0, CampusMotion.staggerDelay(0))
        assertEquals(42, CampusMotion.staggerDelay(1))
        assertEquals(252, CampusMotion.staggerDelay(20))
    }

    @Test
    fun `negative item indices never produce negative delays`() {
        assertEquals(0, CampusMotion.staggerDelay(-4))
    }
}

package com.example.campusai.features.gamification

import org.junit.Assert.assertEquals
import org.junit.Test

class LevelCalculatorTest {
    @Test
    fun levelProgressUsesIncreasingThresholdsAndClampsNegativeXp() {
        assertEquals(LevelProgress(1, 0, 0, 100, 0f), LevelCalculator.calculate(-20))
        assertEquals(LevelProgress(1, 99, 99, 100, .99f), LevelCalculator.calculate(99))
        assertEquals(LevelProgress(2, 100, 0, 125, 0f), LevelCalculator.calculate(100))
        assertEquals(LevelProgress(2, 224, 124, 125, .992f), LevelCalculator.calculate(224))
        assertEquals(LevelProgress(3, 225, 0, 150, 0f), LevelCalculator.calculate(225))
    }

    @Test
    fun titleTracksMeaningfulLevelBands() {
        assertEquals("校园新旅人", LevelCalculator.titleFor(1))
        assertEquals("校园探索者", LevelCalculator.titleFor(5))
        assertEquals("成长先锋", LevelCalculator.titleFor(10))
        assertEquals("校园领航者", LevelCalculator.titleFor(20))
    }
}

package com.example.campusai.ui.screens.counselor

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CpmHeroLayoutTest {
    @Test
    fun `narrow phone keeps the portrait dominant without oversized card padding`() {
        val metrics = cpmHeroMetrics(360)

        assertEquals(240, metrics.cardHeightDp)
        assertTrue(metrics.avatarSizeDp.toFloat() / metrics.cardHeightDp in 0.58f..0.62f)
        assertTrue(metrics.contentPaddingDp >= 16)
        assertTrue(metrics.avatarScale in 1.66f..1.70f)
        assertTrue(metrics.avatarVerticalOffsetFraction in 0.33f..0.35f)
        assertTrue(metrics.avatarContainerScale in 0.99f..1.01f)
        assertTrue(metrics.alignAvatarToTop)
    }

    @Test
    fun `regular phone gives the avatar room while keeping copy close`() {
        val metrics = cpmHeroMetrics(412)

        assertEquals(240, metrics.cardHeightDp)
        assertEquals(148, metrics.avatarSizeDp)
        assertEquals(18, metrics.contentPaddingDp)
        assertTrue(metrics.itemGapDp in 16..18)
        assertEquals(34, metrics.sparkleBadgeSizeDp)
        assertEquals(64, CPM_RECOMMENDATION_CARD_HEIGHT_DP)
        assertEquals(60, CPM_COMPOSER_MIN_HEIGHT_DP)
    }
}

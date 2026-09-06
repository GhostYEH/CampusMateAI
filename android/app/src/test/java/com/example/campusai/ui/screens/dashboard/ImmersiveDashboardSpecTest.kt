package com.example.campusai.ui.screens.dashboard

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import androidx.compose.ui.unit.dp

class ImmersiveDashboardSpecTest {
    @Test
    fun fixedFeatureCardsPrioritizeCommunityAndFocus() {
        val cards = dashboardFeatureCards()

        assertEquals(listOf("community", "focus"), cards.map { it.route })
        assertEquals("校园社区", cards[0].title)
        assertEquals("#FFA43A", cards[0].accentHex)
        assertEquals("#5B68F2", cards[1].accentHex)
    }

    @Test
    fun fixedUtilityActionsExposeNotificationsAndScanWithoutLostFound() {
        val routes = dashboardUtilityActions().map { it.route }

        assertTrue(routes.contains("notifications"))
        assertTrue(routes.contains("qr_scanner"))
        assertFalse(routes.contains("lostfound"))
    }

    @Test
    fun overviewCustomizationKeepsSelectionsValidAndNeverEmptiesTheCard() {
        val defaults = defaultOverviewMetricIds()

        assertEquals(listOf("courses", "tasks", "focus", "notifications"), defaults)
        assertEquals(defaults, normalizeOverviewMetricIds(defaults, defaults))
        assertEquals(listOf("courses"), normalizeOverviewMetricIds(emptyList(), defaults))
        assertEquals(listOf("courses", "notifications"), normalizeOverviewMetricIds(listOf("courses", "unknown", "notifications"), defaults))
    }

    @Test
    fun todayCoursesSectionUsesTheCoursesTabRoute() {
        assertEquals("courses", dashboardCourseSectionRoute())
    }

    @Test
    fun unreadNotificationMetricUsesTheTasksRoute() {
        assertEquals("tasks", dashboardUnreadNotificationRoute())
    }

    @Test
    fun focusFeatureCardShowsNonNegativeTodayDuration() {
        assertEquals("95 分钟", dashboardFocusDurationValue(95))
        assertEquals("0 分钟", dashboardFocusDurationValue(-4))
    }

    @Test
    fun immersiveHeaderAddsStatusBarInsetToContentSpacing() {
        assertEquals(14.dp, dashboardHeaderContentTopPadding(0.dp))
        assertEquals(38.dp, dashboardHeaderContentTopPadding(24.dp))
    }
}

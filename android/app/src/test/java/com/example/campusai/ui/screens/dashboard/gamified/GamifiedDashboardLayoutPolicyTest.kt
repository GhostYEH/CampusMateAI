package com.example.campusai.ui.screens.dashboard.gamified

import org.junit.Assert.assertEquals
import org.junit.Test

class GamifiedDashboardLayoutPolicyTest {
    @Test
    fun smallPhoneKeepsCardsReadableWithTwoColumns() {
        assertEquals(
            DashboardLayoutPolicy(SizeClass.COMPACT, sideQuestColumns = 2, growthColumns = 2),
            DashboardLayoutPolicy.forWidthDp(320),
        )
    }

    @Test
    fun normalPhoneUsesTwoSideQuestColumnsAndFourGrowthColumns() {
        assertEquals(
            DashboardLayoutPolicy(SizeClass.NORMAL, sideQuestColumns = 2, growthColumns = 4),
            DashboardLayoutPolicy.forWidthDp(390),
        )
    }

    @Test
    fun largePhoneUsesThreeSideQuestColumnsWithoutBecomingTabletNavigation() {
        assertEquals(
            DashboardLayoutPolicy(SizeClass.WIDE, sideQuestColumns = 3, growthColumns = 4),
            DashboardLayoutPolicy.forWidthDp(600),
        )
    }
}

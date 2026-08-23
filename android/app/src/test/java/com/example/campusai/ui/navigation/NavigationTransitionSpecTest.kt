package com.example.campusai.ui.navigation

import org.junit.Assert.assertEquals
import org.junit.Test

class NavigationTransitionSpecTest {
    @Test
    fun openingSecondaryPageSlidesWholeDestinationFromRightToLeft() {
        assertEquals(
            HorizontalNavigationMotion(enterDirection = 1, exitDirection = -1),
            forwardNavigationMotion(initialRoute = "profile", targetRoute = "edu_system"),
        )
    }

    @Test
    fun openingNestedSecondaryPageKeepsForwardDirection() {
        assertEquals(
            HorizontalNavigationMotion(enterDirection = 1, exitDirection = -1),
            forwardNavigationMotion(initialRoute = "edu_system", targetRoute = "edu_schedule"),
        )
    }

    @Test
    fun switchingMainTabsFollowsTheirVisualOrder() {
        assertEquals(
            HorizontalNavigationMotion(enterDirection = -1, exitDirection = 1),
            forwardNavigationMotion(initialRoute = "profile", targetRoute = "home"),
        )
    }
}

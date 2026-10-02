package com.example.campusai.ui.system

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SystemBarPolicyTest {
    @Test
    fun unauthenticatedLoginUsesLightIconsOnBothTransparentBars() {
        val policy = systemBarPolicy(route = null, darkTheme = false, authenticated = false)

        assertFalse(policy.darkStatusBarIcons)
        assertFalse(policy.darkNavigationBarIcons)
    }

    @Test
    fun lightPagesUseDarkIconsOnTransparentBars() {
        val policy = systemBarPolicy(route = "tasks", darkTheme = false, authenticated = true)

        assertTrue(policy.darkStatusBarIcons)
        assertTrue(policy.darkNavigationBarIcons)
    }

    @Test
    fun profileKeepsLightStatusIconsButDarkGestureNavigationIcons() {
        val policy = systemBarPolicy(route = "profile", darkTheme = false, authenticated = true)

        assertFalse(policy.darkStatusBarIcons)
        assertTrue(policy.darkNavigationBarIcons)
    }

    @Test
    fun campusHomeKeepsSystemIconsLegibleOverTheScene() {
        val policy = systemBarPolicy(route = "home", darkTheme = false, authenticated = true)

        assertFalse(policy.darkStatusBarIcons)
        assertFalse(policy.darkNavigationBarIcons)
    }

    @Test
    fun focusFlowUsesLightSystemIconsOverFullBleedScenes() {
        listOf("focus", "focus_session", "focus_summary", "focus_history").forEach { route ->
            val policy = systemBarPolicy(route = route, darkTheme = false, authenticated = true)
            assertFalse(policy.darkStatusBarIcons)
            assertFalse(policy.darkNavigationBarIcons)
            assertTrue(routeOwnsStatusBarInset(route))
        }
    }

    @Test
    fun darkThemeUsesLightIconsOnThemeColoredPages() {
        val policy = systemBarPolicy(route = "tasks", darkTheme = true, authenticated = true)

        assertFalse(policy.darkStatusBarIcons)
        assertFalse(policy.darkNavigationBarIcons)
    }

    @Test
    fun fullBleedAndSelfInsetRoutesAreExplicit() {
        assertTrue(routeOwnsStatusBarInset("home"))
        assertTrue(routeOwnsStatusBarInset("profile"))
        assertTrue(routeOwnsStatusBarInset("courses"))
        assertTrue(routeOwnsStatusBarInset("focus"))
        assertFalse(routeOwnsStatusBarInset("task_detail/{taskId}"))
    }
}

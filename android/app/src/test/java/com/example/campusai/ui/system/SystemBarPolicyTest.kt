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
    fun darkThemeUsesLightIconsOnThemeColoredPages() {
        val policy = systemBarPolicy(route = "tasks", darkTheme = true, authenticated = true)

        assertFalse(policy.darkStatusBarIcons)
        assertFalse(policy.darkNavigationBarIcons)
    }

    @Test
    fun fullBleedAndSelfInsetRoutesAreExplicit() {
        assertTrue(routeOwnsStatusBarInset("home"))
        assertTrue(routeOwnsStatusBarInset("profile"))
        assertFalse(routeOwnsStatusBarInset("courses"))
        assertFalse(routeOwnsStatusBarInset("task_detail/{taskId}"))
    }
}

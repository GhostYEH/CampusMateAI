package com.example.campusai.ui.screens.shell

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LiquidGlassDockProfileTest {
    @Test
    fun api33EnablesTheFullGlassProfile() {
        val profile = liquidGlassDockProfile(apiLevel = 33, darkMode = false)

        assertTrue(profile.blurEnabled)
        assertTrue(profile.lensEnabled)
        assertTrue(profile.vibrancyEnabled)
        assertEquals(8f, profile.blurRadiusDp)
        assertEquals(0.40f, profile.surfaceAlpha)
    }

    @Test
    fun api31KeepsBlurButDisablesShaderOnlyEffects() {
        val profile = liquidGlassDockProfile(apiLevel = 31, darkMode = false)

        assertTrue(profile.blurEnabled)
        assertFalse(profile.lensEnabled)
        assertFalse(profile.vibrancyEnabled)
        assertEquals(12f, profile.blurRadiusDp)
        assertEquals(0.52f, profile.surfaceAlpha)
    }

    @Test
    fun api28UsesOpaqueEnoughSurfacesWithoutBlur() {
        val lightProfile = liquidGlassDockProfile(apiLevel = 28, darkMode = false)
        val darkProfile = liquidGlassDockProfile(apiLevel = 28, darkMode = true)

        assertFalse(lightProfile.blurEnabled)
        assertFalse(lightProfile.lensEnabled)
        assertEquals(0.82f, lightProfile.surfaceAlpha)
        assertEquals(0.74f, darkProfile.surfaceAlpha)
    }
}

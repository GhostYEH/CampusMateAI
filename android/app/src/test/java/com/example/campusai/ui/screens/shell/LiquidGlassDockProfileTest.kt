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
        assertEquals(0.16f, profile.chromaticEdgeAlpha)
        assertEquals(0x260B1830L, profile.shadowColorArgb)
    }

    @Test
    fun api31KeepsBlurButDisablesShaderOnlyEffects() {
        val profile = liquidGlassDockProfile(apiLevel = 31, darkMode = false)

        assertTrue(profile.blurEnabled)
        assertFalse(profile.lensEnabled)
        assertFalse(profile.vibrancyEnabled)
        assertEquals(12f, profile.blurRadiusDp)
        assertEquals(0.52f, profile.surfaceAlpha)
        assertEquals(0.09f, profile.chromaticEdgeAlpha)
    }

    @Test
    fun api28UsesOpaqueEnoughSurfacesWithoutBlur() {
        val lightProfile = liquidGlassDockProfile(apiLevel = 28, darkMode = false)
        val darkProfile = liquidGlassDockProfile(apiLevel = 28, darkMode = true)

        assertFalse(lightProfile.blurEnabled)
        assertFalse(lightProfile.lensEnabled)
        assertEquals(0.82f, lightProfile.surfaceAlpha)
        assertEquals(0.74f, darkProfile.surfaceAlpha)
        assertEquals(0.05f, lightProfile.chromaticEdgeAlpha)
        assertEquals(0.08f, darkProfile.chromaticEdgeAlpha)
        assertEquals(0x260B1830L, lightProfile.shadowColorArgb)
        assertEquals(0x80000000L, darkProfile.shadowColorArgb)
    }

    @Test
    fun clickFeedbackUsesANonBlockingGlowWhenMotionIsEnabled() {
        val profile = liquidGlassDockInteractionProfile(reduceMotion = false)

        assertTrue(profile.clickGlowEnabled)
        assertEquals(300, profile.clickGlowDurationMillis)
        assertEquals(30f, profile.clickGlowRadiusDp)
    }

    @Test
    fun reducedMotionKeepsAStaticGlowWithoutExpansion() {
        val profile = liquidGlassDockInteractionProfile(reduceMotion = true)

        assertFalse(profile.clickGlowEnabled)
        assertEquals(0, profile.clickGlowDurationMillis)
    }
}

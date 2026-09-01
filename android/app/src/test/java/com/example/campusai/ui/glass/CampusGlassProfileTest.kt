package com.example.campusai.ui.glass

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CampusGlassProfileTest {
    @Test
    fun api33UsesFullLiquidGlass() {
        val profile = campusGlassProfile(apiLevel = 33, reduceMotion = false)

        assertEquals(CampusGlassQuality.FULL, profile.quality)
        assertTrue(profile.blurEnabled)
        assertTrue(profile.lensEnabled)
        assertTrue(profile.glowAnimationEnabled)
    }

    @Test
    fun api31UsesBlurWithoutRuntimeShaderEffects() {
        val profile = campusGlassProfile(apiLevel = 31, reduceMotion = false)

        assertEquals(CampusGlassQuality.BLUR, profile.quality)
        assertTrue(profile.blurEnabled)
        assertFalse(profile.lensEnabled)
    }

    @Test
    fun legacyAndroidUsesPaintedFallback() {
        val profile = campusGlassProfile(apiLevel = 30, reduceMotion = false)

        assertEquals(CampusGlassQuality.PAINTED, profile.quality)
        assertFalse(profile.blurEnabled)
        assertFalse(profile.lensEnabled)
    }

    @Test
    fun reduceMotionKeepsMaterialButDisablesAnimatedGlow() {
        val profile = campusGlassProfile(apiLevel = 35, reduceMotion = true)

        assertEquals(CampusGlassQuality.FULL, profile.quality)
        assertTrue(profile.lensEnabled)
        assertFalse(profile.glowAnimationEnabled)
    }

    @Test
    fun denseScrollingGlassNeverUsesContinuousLens() {
        val profile = campusGlassProfile(apiLevel = 35, reduceMotion = false)

        assertFalse(profile.effectsFor(CampusGlassRole.DENSE).lensAtRest)
        assertTrue(profile.effectsFor(CampusGlassRole.NAVIGATION).lensAtRest)
        assertTrue(profile.effectsFor(CampusGlassRole.CONTROL).lensOnPress)
    }
}

package com.example.campusai.data.focus.scene

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class FocusScenePreferencesTest {
    @Test
    fun defaultsToRainyRoomWithSoundOff() {
        assertEquals(FocusScene.RAINY_ROOM, FocusScene.fromStoredId(null))
        assertFalse(FocusSceneSettings.DEFAULT.ambientEnabled)
        assertEquals(0.32f, FocusSceneSettings.DEFAULT.volume)
    }

    @Test
    fun unknownSceneAndInvalidVolumeAreNormalized() {
        val tooLoud = FocusSceneSettings.normalized("missing", ambientEnabled = true, volume = 4.2f)
        val belowZero = FocusSceneSettings.normalized("forest_morning", ambientEnabled = true, volume = -0.8f)

        assertEquals(FocusScene.RAINY_ROOM, tooLoud.scene)
        assertEquals(1f, tooLoud.volume)
        assertEquals(FocusScene.FOREST_MORNING, belowZero.scene)
        assertEquals(0f, belowZero.volume)
    }
}

package com.example.campusai.data.focus.scene

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class FocusSceneAudioResourcesTest {
    @Test
    fun eachSceneUsesItsOwnAmbientTrack() {
        val tracks = FocusScene.entries.map(FocusSceneAudioResources::resourceId)

        assertEquals(3, tracks.distinct().size)
        tracks.forEach { assertNotEquals(0, it) }
    }
}

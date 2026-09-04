package com.example.campusai.ui.screens.focus

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FocusHallWallpaperPickerTest {
    @Test
    fun `wallpaper catalog contains five distinct scenes`() {
        assertEquals(5, focusHallWallpaperResources.size)
        assertEquals(5, focusHallWallpaperResources.distinct().size)
    }

    @Test
    fun `next wallpaper never immediately repeats previous scene`() {
        focusHallWallpaperResources.forEach { previous ->
            repeat(20) { randomIndex ->
                val next = chooseFocusHallWallpaper(
                    previousResource = previous,
                    randomIndex = randomIndex,
                )

                assertNotEquals(previous, next)
                assertTrue(next in focusHallWallpaperResources)
            }
        }
    }

    @Test
    fun `first wallpaper selection can reach every scene`() {
        val selected = focusHallWallpaperResources.indices.map { randomIndex ->
            chooseFocusHallWallpaper(previousResource = null, randomIndex = randomIndex)
        }

        assertEquals(focusHallWallpaperResources.toSet(), selected.toSet())
    }
}

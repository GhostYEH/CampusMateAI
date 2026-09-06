package com.example.campusai.data.wallpaper

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BingDailyWallpaperRepositoryTest {
    @Test
    fun prefersThe1080ImageForTheHomeBackground() = runBlocking {
        val repository = BingDailyWallpaperRepository {
            BingDailyWallpaperResponse(
                image_url = "https://example.com/fallback.jpg",
                image_url_1080 = "https://example.com/1080.jpg",
                image_url_4k = "https://example.com/4k.jpg",
            )
        }

        repository.refresh()

        assertEquals("https://example.com/1080.jpg", repository.state.value.wallpaper?.imageUrl)
        assertTrue(!repository.state.value.unavailable)
    }

    @Test
    fun fallsBackToAnotherImageUrlWhen1080IsMissing() = runBlocking {
        val repository = BingDailyWallpaperRepository {
            BingDailyWallpaperResponse(image_url = "https://example.com/fallback.jpg")
        }

        repository.refresh()

        assertEquals("https://example.com/fallback.jpg", repository.state.value.wallpaper?.imageUrl)
    }

    @Test
    fun marksWallpaperUnavailableWhenTheResponseHasNoUsableImage() = runBlocking {
        val repository = BingDailyWallpaperRepository {
            BingDailyWallpaperResponse(image_url_1080 = " ", image_url_4k = null)
        }

        repository.refresh()

        assertTrue(repository.state.value.unavailable)
        assertEquals(null, repository.state.value.wallpaper)
    }
}

package com.example.campusai.data.news

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import com.example.campusai.data.repository.AppRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class CampusNewsPreferencesTest {

    @Test
    fun markingTheSameNewsReadTwicePersistsItsIdOnce() = runBlocking {
        val storage = FakeCampusNewsPreferences()
        val repository = AppRepository(application(), storage)

        repository.markCampusNewsRead("news-42")
        waitUntil { repository.newsReadIds.value == setOf("news-42") }
        repository.markCampusNewsRead("news-42")

        assertEquals(listOf(setOf("news-42")), storage.savedReadIds)
    }

    @Test
    fun togglingFavoriteAddsThenRemovesTheNewsId() = runBlocking {
        val storage = FakeCampusNewsPreferences()
        val repository = AppRepository(application(), storage)

        repository.toggleCampusNewsFavorite("news-42")
        waitUntil { repository.newsFavoriteIds.value == setOf("news-42") }
        repository.toggleCampusNewsFavorite("news-42")

        assertEquals(listOf(setOf("news-42"), emptySet()), storage.savedFavoriteIds)
    }

    @Test
    fun concurrentFavoriteTogglesPersistBothTransitionsAndEndEmpty() = runBlocking {
        val storage = FakeCampusNewsPreferences(delayFavoriteUpdate = true)
        val repository = AppRepository(application(), storage)

        awaitAll(
            async(Dispatchers.Default) { repository.toggleCampusNewsFavorite("news-42") },
            async(Dispatchers.Default) { repository.toggleCampusNewsFavorite("news-42") },
        )

        assertEquals(listOf(setOf("news-42"), emptySet()), storage.savedFavoriteIds)
        assertEquals(emptySet<String>(), repository.newsFavoriteIds.value)
    }

    private fun application(): Application = ApplicationProvider.getApplicationContext()

    private suspend fun waitUntil(predicate: () -> Boolean) {
        repeat(100) {
            if (predicate()) return
            kotlinx.coroutines.delay(10)
        }
        throw AssertionError("Timed out waiting for campus-news preference state")
    }

    private class FakeCampusNewsPreferences(
        private val delayFavoriteUpdate: Boolean = false,
    ) : CampusNewsPreferences {
        private val readIds = MutableStateFlow<Set<String>>(emptySet())
        private val favoriteIds = MutableStateFlow<Set<String>>(emptySet())

        val savedReadIds = mutableListOf<Set<String>>()
        val savedFavoriteIds = mutableListOf<Set<String>>()

        override val campusNewsReadIds: Flow<Set<String>> = readIds
        override val campusNewsFavoriteIds: Flow<Set<String>> = favoriteIds

        override suspend fun setCampusNewsReadIds(ids: Set<String>) {
            savedReadIds += ids
            readIds.value = ids
        }

        override suspend fun setCampusNewsFavoriteIds(ids: Set<String>) {
            synchronized(this) { savedFavoriteIds += ids }
            if (delayFavoriteUpdate) delay(100)
            favoriteIds.value = ids
        }
    }
}

package com.example.campusai.data.hitokoto

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class HitokotoRepositoryTest {
    @Test
    fun refreshPublishesTheSentenceReturnedByHitokoto() = runBlocking {
        val repository = HitokotoRepository {
            HitokotoResponse(
                hitokoto = "用代码表达言语的魅力。",
                from = "一言开发者中心",
                uuid = "quote-1",
            )
        }

        repository.refresh()

        assertEquals("用代码表达言语的魅力。", repository.state.value.quote?.text)
        assertEquals("一言开发者中心", repository.state.value.quote?.source)
        assertFalse(repository.state.value.isLoading)
        assertFalse(repository.state.value.unavailable)
    }

    @Test
    fun failedRefreshUsesUnavailableStateWithoutTheOldSparkleCopy() = runBlocking {
        val repository = HitokotoRepository { error("network down") }

        repository.refresh()

        assertTrue(repository.state.value.unavailable)
        assertEquals("暂时无法获取一言", repository.state.value.displayText())
        assertFalse(repository.state.value.displayText().contains("闪闪发光"))
    }

    @Test
    fun refreshDoesNotRefetchAnAlreadyLoadedSentence() = runBlocking {
        var requests = 0
        val repository = HitokotoRepository {
            requests += 1
            HitokotoResponse(hitokoto = "只请求一次。")
        }

        repository.refresh()
        repository.refresh()

        assertEquals(1, requests)
    }
}

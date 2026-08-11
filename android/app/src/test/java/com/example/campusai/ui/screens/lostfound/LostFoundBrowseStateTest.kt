package com.example.campusai.ui.screens.lostfound

import com.example.campusai.data.model.LostFoundKind
import com.example.campusai.data.repository.LocalLostFoundRepository
import com.example.campusai.data.local.InMemoryKeyValueStorage
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlinx.coroutines.runBlocking

class LostFoundBrowseStateTest {

    @Test
    fun `all locations normalize to repository all value`() {
        val state = LostFoundBrowseState(location = "全部地点")

        assertEquals("全部", state.repositoryLocation())
    }

    @Test
    fun `specific location is preserved for repository filtering`() {
        val state = LostFoundBrowseState(location = "图书馆三楼")

        assertEquals("图书馆三楼", state.repositoryLocation())
    }

    @Test
    fun `found filters keep selected kind and oldest ordering`() {
        val state = LostFoundBrowseState(kind = LostFoundKind.FOUND, newestFirst = false)

        assertEquals(LostFoundKind.FOUND, state.kind)
        assertFalse(state.newestFirst)
    }

    @Test
    fun `location options each match at least one demo post`() = runBlocking {
        val repository = LocalLostFoundRepository(storage = InMemoryKeyValueStorage())
        repository.refresh()
        val expectedKinds = mapOf(
            "图书馆三楼" to LostFoundKind.LOST,
            "教学楼 2-305" to LostFoundKind.LOST,
            "第二食堂" to LostFoundKind.FOUND,
            "东操场看台" to LostFoundKind.FOUND,
        )

        expectedKinds.forEach { (location, kind) ->
            assertTrue(LostFoundBrowseOptions.locations.contains(location))
            assertTrue(
                LocalLostFoundRepository.filter(
                    items = repository.items.value,
                    kind = kind,
                    keyword = "",
                    category = "全部",
                    location = location,
                    newestFirst = true,
                ).isNotEmpty(),
            )
        }
    }
}

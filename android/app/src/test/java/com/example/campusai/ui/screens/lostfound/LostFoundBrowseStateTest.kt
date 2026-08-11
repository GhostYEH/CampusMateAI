package com.example.campusai.ui.screens.lostfound

import com.example.campusai.data.model.LostFoundKind
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

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
}

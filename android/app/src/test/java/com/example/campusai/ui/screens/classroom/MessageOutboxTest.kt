package com.example.campusai.ui.screens.classroom

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class MessageOutboxTest {
    @Test
    fun `uncertain send keeps its original id until explicitly resolved`() {
        val outbox = MessageOutbox()
        val first = outbox.begin("room", " message ", "id-1")!!
        assertNull(outbox.begin("room", "another", "id-2"))
        assertEquals(first, outbox.get("room"))
        assertEquals("id-1", outbox.get("room")?.clientId)
        outbox.remove(first)
        assertEquals("id-2", outbox.begin("room", "another", "id-2")?.clientId)
    }

    @Test
    fun `room isolation and stale completion preserve newer attempt`() {
        val outbox = MessageOutbox()
        val old = outbox.begin("room", "first", "id-1")!!
        val other = outbox.begin("other", "second", "id-2")!!
        outbox.remove(old)
        val newer = outbox.begin("room", "third", "id-3")!!
        outbox.remove(old)
        assertEquals(newer, outbox.get("room"))
        assertEquals(other, outbox.get("other"))
    }
}

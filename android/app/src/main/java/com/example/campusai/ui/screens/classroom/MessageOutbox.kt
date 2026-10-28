package com.example.campusai.ui.screens.classroom

/** A failed request may already have been committed by the server. */
data class PendingRoomMessage(val roomId: String, val draft: String, val clientId: String)

internal class MessageOutbox {
    private val pending = mutableMapOf<String, PendingRoomMessage>()

    fun get(roomId: String): PendingRoomMessage? = pending[roomId]

    fun begin(roomId: String, draft: String, clientId: String): PendingRoomMessage? {
        if (pending.containsKey(roomId)) return null
        return PendingRoomMessage(roomId, draft, clientId).also { pending[roomId] = it }
    }

    fun remove(attempt: PendingRoomMessage) {
        if (pending[attempt.roomId] == attempt) pending.remove(attempt.roomId)
    }

    fun clear() = pending.clear()
}

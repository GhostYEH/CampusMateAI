package com.example.campusai.ui.screens.classroom

/** A failed request may already have been committed by the server. */
data class PendingRoomMessage(
    val roomId: String,
    val draft: String,
    val clientId: String,
    /** 用户输入框里的原始文本；请求仍发送标准化后的 [draft]。 */
    val rawDraft: String = draft,
)

internal class MessageOutbox {
    private val pending = mutableMapOf<String, PendingRoomMessage>()

    fun get(roomId: String): PendingRoomMessage? = pending[roomId]

    fun begin(roomId: String, draft: String, clientId: String, rawDraft: String = draft): PendingRoomMessage? {
        if (pending.containsKey(roomId)) return null
        return PendingRoomMessage(roomId, draft, clientId, rawDraft).also { pending[roomId] = it }
    }

    fun remove(attempt: PendingRoomMessage) {
        if (pending[attempt.roomId] == attempt) pending.remove(attempt.roomId)
    }

    fun clear() = pending.clear()
}

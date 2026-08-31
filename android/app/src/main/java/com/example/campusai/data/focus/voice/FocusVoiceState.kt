package com.example.campusai.data.focus.voice

enum class FocusVoicePhase {
    IDLE,
    CONNECTING,
    LISTENING,
    THINKING,
    SPEAKING,
    RECONNECTING,
    ERROR,
}

enum class FocusVoiceMessageRole { USER, ASSISTANT }

data class FocusVoiceMessage(
    val id: Long,
    val turnId: Long,
    val role: FocusVoiceMessageRole,
    val text: String,
    val upstreamEventId: String? = null,
    val responseId: String? = null,
    val itemId: String? = null,
)

data class FocusVoiceState(
    val phase: FocusVoicePhase = FocusVoicePhase.IDLE,
    val messages: List<FocusVoiceMessage> = emptyList(),
    val liveTranscript: String? = null,
    val liveAnswer: String? = null,
    val errorMessage: String? = null,
)

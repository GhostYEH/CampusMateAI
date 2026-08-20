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

data class FocusVoiceState(
    val phase: FocusVoicePhase = FocusVoicePhase.IDLE,
    val transcript: String? = null,
    val answer: String? = null,
    val errorMessage: String? = null,
)

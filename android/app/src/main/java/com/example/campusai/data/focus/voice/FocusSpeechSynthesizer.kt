package com.example.campusai.data.focus.voice

interface FocusSpeechSynthesizer {
    fun speak(text: String, onDone: () -> Unit, onError: (String) -> Unit)
    fun stop()
    fun shutdown()
}

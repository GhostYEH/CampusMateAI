package com.example.campusai.data.focus.voice

interface SpeechTranscriber {
    fun start(onResult: (String) -> Unit, onError: (String) -> Unit)
    fun stop()
    fun cancel()
    fun release()
}

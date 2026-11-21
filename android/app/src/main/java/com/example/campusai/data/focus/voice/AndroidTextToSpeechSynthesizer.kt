package com.example.campusai.data.focus.voice

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.util.Locale
import java.util.UUID

class AndroidTextToSpeechSynthesizer(context: Context) : FocusSpeechSynthesizer {
    private enum class EngineState { INITIALIZING, READY, UNAVAILABLE, CLOSED }

    private class SpeechRequest(
        val text: String,
        val onDone: () -> Unit,
        val onError: (String) -> Unit,
        val id: String = UUID.randomUUID().toString(),
    )

    private val mainHandler = Handler(Looper.getMainLooper())
    private var state = EngineState.INITIALIZING
    private var pending: SpeechRequest? = null
    private var speaking: SpeechRequest? = null

    private val tts = TextToSpeech(context.applicationContext) { status ->
        mainHandler.post {
            if (state != EngineState.CLOSED) {
                state = if (status == TextToSpeech.SUCCESS) EngineState.READY else EngineState.UNAVAILABLE
                val request = pending
                pending = null
                if (request != null) submit(request)
            }
        }
    }.apply {
        setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String) = Unit
            override fun onDone(utteranceId: String) = finish(utteranceId)
            @Deprecated("Deprecated in Java")
            override fun onError(utteranceId: String) = finish(utteranceId, "系统语音朗读失败")
            override fun onError(utteranceId: String, errorCode: Int) = finish(utteranceId, "系统语音朗读失败")
            override fun onStop(utteranceId: String, interrupted: Boolean) = finish(utteranceId, "系统语音朗读已中断")
        })
    }

    override fun speak(text: String, onDone: () -> Unit, onError: (String) -> Unit) {
        submit(SpeechRequest(text, onDone, onError))
    }

    private fun submit(request: SpeechRequest) {
        if (state == EngineState.INITIALIZING) {
            pending = request
            return
        }
        if (state != EngineState.READY) {
            request.onError("系统语音朗读暂不可用")
            return
        }
        if (tts.isLanguageAvailable(Locale.SIMPLIFIED_CHINESE) >= TextToSpeech.LANG_AVAILABLE) {
            tts.language = Locale.SIMPLIFIED_CHINESE
        }
        speaking = request
        if (tts.speak(request.text, TextToSpeech.QUEUE_FLUSH, null, request.id) == TextToSpeech.ERROR) {
            finish(request.id, "系统语音朗读暂不可用")
        }
    }

    private fun finish(id: String, error: String? = null) {
        mainHandler.post {
            val request = speaking?.takeIf { it.id == id } ?: return@post
            speaking = null
            if (error == null) request.onDone() else request.onError(error)
        }
    }

    override fun stop() {
        pending = null
        speaking = null
        tts.stop()
    }

    override fun shutdown() {
        state = EngineState.CLOSED
        stop()
        tts.shutdown()
    }
}

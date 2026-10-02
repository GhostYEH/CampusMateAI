package com.example.campusai.data.focus.voice

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.util.Locale
import java.util.UUID

class AndroidTextToSpeechSynthesizer(context: Context) : FocusSpeechSynthesizer {
    @Volatile private var ready = false
    @Volatile private var closed = false
    @Volatile private var pending: Triple<String, () -> Unit, (String) -> Unit>? = null
    private var onDone: (() -> Unit)? = null
    private var onError: ((String) -> Unit)? = null
    private lateinit var tts: TextToSpeech

    init {
        tts = TextToSpeech(context.applicationContext) { status ->
            ready = status == TextToSpeech.SUCCESS
            Handler(Looper.getMainLooper()).post {
                if (!closed) {
                    val waiting = pending
                    pending = null
                    if (waiting != null) {
                        if (ready) speak(waiting.first, waiting.second, waiting.third)
                        else waiting.third("系统语音朗读暂不可用")
                    }
                }
            }
        }.apply {
            setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String) = Unit
                override fun onDone(utteranceId: String) { this@AndroidTextToSpeechSynthesizer.onDone?.invoke() }
                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String) { this@AndroidTextToSpeechSynthesizer.onError?.invoke("系统语音朗读失败") }
                override fun onError(utteranceId: String, errorCode: Int) { this@AndroidTextToSpeechSynthesizer.onError?.invoke("系统语音朗读失败") }
            })
        }
    }

    override fun speak(text: String, onDone: () -> Unit, onError: (String) -> Unit) {
        if (!ready) {
            if (closed) onError("系统语音朗读暂不可用")
            else pending = Triple(text, onDone, onError)
            return
        }
        if (tts.isLanguageAvailable(Locale.SIMPLIFIED_CHINESE) >= TextToSpeech.LANG_AVAILABLE) {
            tts.language = Locale.SIMPLIFIED_CHINESE
        }
        this.onDone = onDone
        this.onError = onError
        val result = tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, UUID.randomUUID().toString())
        if (result == TextToSpeech.ERROR) onError("系统语音朗读暂不可用")
    }

    override fun stop() {
        pending = null
        tts.stop()
        onDone = null
        onError = null
    }

    override fun shutdown() {
        closed = true
        stop()
        tts.shutdown()
        ready = false
    }
}

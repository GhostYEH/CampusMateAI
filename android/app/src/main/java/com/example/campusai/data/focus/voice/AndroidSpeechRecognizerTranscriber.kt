package com.example.campusai.data.focus.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer

class AndroidSpeechRecognizerTranscriber(context: Context) : SpeechTranscriber {
    private val appContext = context.applicationContext
    private var recognizer: SpeechRecognizer? = null
    private var resultCallback: ((String) -> Unit)? = null
    private var errorCallback: ((String) -> Unit)? = null

    override fun start(onResult: (String) -> Unit, onError: (String) -> Unit) {
        if (!SpeechRecognizer.isRecognitionAvailable(appContext)) {
            onError("此设备暂不支持语音识别")
            return
        }
        resultCallback = onResult
        errorCallback = onError
        val activeRecognizer = recognizer ?: SpeechRecognizer.createSpeechRecognizer(appContext).also {
            it.setRecognitionListener(Listener())
            recognizer = it
        }
        activeRecognizer.startListening(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        })
    }

    override fun stop() {
        recognizer?.stopListening()
    }

    override fun cancel() {
        recognizer?.cancel()
    }

    override fun release() {
        resultCallback = null
        errorCallback = null
        recognizer?.destroy()
        recognizer = null
    }

    private inner class Listener : RecognitionListener {
        override fun onResults(results: Bundle?) {
            val text = results
                ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.firstOrNull()
                ?.trim()
                .orEmpty()
            if (text.isEmpty()) errorCallback?.invoke("没有识别到清晰的语音，请再试一次")
            else resultCallback?.invoke(text)
        }

        override fun onError(error: Int) {
            errorCallback?.invoke(
                when (error) {
                    SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "没有识别到清晰的语音，请再试一次"
                    SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "需要麦克风权限才能识别语音"
                    SpeechRecognizer.ERROR_NETWORK, SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "语音识别网络不可用，请检查网络后重试"
                    SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "语音识别正忙，请稍后重试"
                    else -> "语音识别暂时不可用，请重试"
                },
            )
        }

        override fun onReadyForSpeech(params: Bundle?) = Unit
        override fun onBeginningOfSpeech() = Unit
        override fun onRmsChanged(rmsdB: Float) = Unit
        override fun onBufferReceived(buffer: ByteArray?) = Unit
        override fun onEndOfSpeech() = Unit
        override fun onPartialResults(partialResults: Bundle?) = Unit
        override fun onEvent(eventType: Int, params: Bundle?) = Unit
    }
}

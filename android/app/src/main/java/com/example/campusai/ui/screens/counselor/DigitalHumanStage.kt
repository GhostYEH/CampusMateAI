package com.example.campusai.ui.screens.counselor

import android.annotation.SuppressLint
import android.graphics.Color
import android.view.View
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView

object DigitalHumanBridge {
    fun stageUrl(apiBaseUrl: String): String =
        apiBaseUrl.trim().trimEnd('/').removeSuffix("/api/v1") + "/digital-human/mobile.html?embed=1"

    fun configureScript(apiBaseUrl: String, accessToken: String): String =
        "window.CampusMateDigitalHuman.configure({apiBaseUrl:${jsString(apiBaseUrl)},accessToken:${jsString(accessToken)}});"

    fun speakScript(text: String): String =
        "window.CampusMateDigitalHuman.speak(${jsString(text)});"

    fun commandScript(command: DigitalHumanCommand): String = when (command) {
        DigitalHumanCommand.TOGGLE_MUTE -> "window.CampusMateDigitalHuman.toggleMuted();"
        DigitalHumanCommand.TOGGLE_PAUSE -> "window.CampusMateDigitalHuman.togglePaused();"
        DigitalHumanCommand.REPLAY -> "window.CampusMateDigitalHuman.replay();"
        DigitalHumanCommand.NONE -> ""
    }

    private fun jsString(value: String): String = buildString {
        append('"')
        value.forEach { character ->
            when (character) {
                '\\' -> append("\\\\")
                '"' -> append("\\\"")
                '\n' -> append("\\n")
                '\r' -> append("\\r")
                '\t' -> append("\\t")
                '\b' -> append("\\b")
                '\u000C' -> append("\\f")
                '\u2028' -> append("\\u2028")
                '\u2029' -> append("\\u2029")
                else -> if (character.code < 0x20) append("\\u%04x".format(character.code)) else append(character)
            }
        }
        append('"')
    }
}
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun DigitalHumanStage(
    apiBaseUrl: String,
    accessToken: String,
    speechText: String,
    speechRequestId: Int,
    command: DigitalHumanCommand = DigitalHumanCommand.NONE,
    commandRequestId: Int = 0,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    var pageReady by remember { mutableStateOf(false) }
    var lastSpokenRequestId by remember { mutableIntStateOf(0) }
    var lastCommandRequestId by remember { mutableIntStateOf(0) }
    val webView = remember {
        WebView(context).apply {
            setBackgroundColor(Color.TRANSPARENT)
            setLayerType(View.LAYER_TYPE_HARDWARE, null)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.mediaPlaybackRequiresUserGesture = false
            settings.loadsImagesAutomatically = true
            settings.cacheMode = android.webkit.WebSettings.LOAD_DEFAULT
            webChromeClient = WebChromeClient()
            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView, url: String) {
                    pageReady = true
                }
            }
            loadUrl(DigitalHumanBridge.stageUrl(apiBaseUrl))
        }
    }

    DisposableEffect(webView) {
        onDispose {
            webView.evaluateJavascript("window.CampusMateDigitalHuman?.stop();", null)
            webView.stopLoading()
            webView.destroy()
        }
    }

    AndroidView(
        factory = { webView },
        update = { view ->
            if (!pageReady) return@AndroidView
            view.evaluateJavascript(DigitalHumanBridge.configureScript(apiBaseUrl, accessToken), null)
            if (speechRequestId > 0 && speechRequestId != lastSpokenRequestId && speechText.isNotBlank()) {
                lastSpokenRequestId = speechRequestId
                view.evaluateJavascript(DigitalHumanBridge.speakScript(speechText), null)
            }
            if (commandRequestId > 0 && commandRequestId != lastCommandRequestId && command != DigitalHumanCommand.NONE) {
                lastCommandRequestId = commandRequestId
                view.evaluateJavascript(DigitalHumanBridge.commandScript(command), null)
            }
        },
        modifier = modifier.fillMaxSize(),
    )
}

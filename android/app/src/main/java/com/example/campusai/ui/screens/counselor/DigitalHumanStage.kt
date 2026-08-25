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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver

object DigitalHumanBridge {
    fun stageUrl(apiBaseUrl: String, forceFallback: Boolean = false): String =
        apiBaseUrl.trim().trimEnd('/').removeSuffix("/api/v1") +
            "/digital-human/mobile.html?embed=1" + if (forceFallback) "&fallback=1" else ""

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

internal enum class DigitalHumanRenderMode { LIVE_WEBGL, NATIVE_COMPAT }

internal fun shouldCreateEmbeddedDigitalHuman(renderMode: DigitalHumanRenderMode): Boolean =
    renderMode == DigitalHumanRenderMode.LIVE_WEBGL

internal fun selectDigitalHumanRenderMode(
    fingerprint: String,
    model: String,
    supportedAbis: List<String>,
    lowRamDevice: Boolean,
): DigitalHumanRenderMode {
    val emulator = fingerprint.contains("generic", ignoreCase = true) ||
        model.contains("sdk_gphone", ignoreCase = true) ||
        model.contains("Android SDK built", ignoreCase = true) ||
        model.contains("Emulator", ignoreCase = true)
    val hasArm64 = supportedAbis.any { it.equals("arm64-v8a", ignoreCase = true) }
    return if (emulator || lowRamDevice || !hasArm64) {
        DigitalHumanRenderMode.NATIVE_COMPAT
    } else {
        DigitalHumanRenderMode.LIVE_WEBGL
    }
}

internal fun shouldUseNativeDigitalHuman(fingerprint: String, model: String): Boolean =
    selectDigitalHumanRenderMode(
        fingerprint = fingerprint,
        model = model,
        supportedAbis = android.os.Build.SUPPORTED_ABIS.toList(),
        lowRamDevice = false,
    ) == DigitalHumanRenderMode.NATIVE_COMPAT

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun DigitalHumanStage(
    apiBaseUrl: String,
    accessToken: String,
    speechText: String,
    speechRequestId: Int,
    command: DigitalHumanCommand = DigitalHumanCommand.NONE,
    commandRequestId: Int = 0,
    forceFallback: Boolean = false,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var pageReady by remember { mutableStateOf(false) }
    var lastSpokenRequestId by remember { mutableIntStateOf(0) }
    var lastCommandRequestId by remember { mutableIntStateOf(0) }
    val webView = remember(apiBaseUrl, forceFallback) {
        WebView(context).apply {
            setBackgroundColor(Color.TRANSPARENT)
            setLayerType(if (forceFallback) View.LAYER_TYPE_NONE else View.LAYER_TYPE_HARDWARE, null)
            setRendererPriorityPolicy(WebView.RENDERER_PRIORITY_BOUND, false)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.mediaPlaybackRequiresUserGesture = false
            settings.loadsImagesAutomatically = true
            settings.cacheMode = android.webkit.WebSettings.LOAD_DEFAULT
            settings.setSupportZoom(false)
            settings.builtInZoomControls = false
            settings.displayZoomControls = false
            webChromeClient = WebChromeClient()
            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView, url: String) {
                    pageReady = true
                }
            }
            loadUrl(DigitalHumanBridge.stageUrl(apiBaseUrl, forceFallback))
        }
    }

    LaunchedEffect(pageReady, apiBaseUrl, accessToken) {
        if (pageReady) {
            webView.evaluateJavascript(DigitalHumanBridge.configureScript(apiBaseUrl, accessToken), null)
        }
    }
    LaunchedEffect(pageReady, speechRequestId) {
        if (pageReady && speechRequestId > 0 && speechRequestId != lastSpokenRequestId && speechText.isNotBlank()) {
            lastSpokenRequestId = speechRequestId
            webView.evaluateJavascript(DigitalHumanBridge.speakScript(speechText), null)
        }
    }
    LaunchedEffect(pageReady, commandRequestId) {
        if (pageReady && commandRequestId > 0 && commandRequestId != lastCommandRequestId && command != DigitalHumanCommand.NONE) {
            lastCommandRequestId = commandRequestId
            webView.evaluateJavascript(DigitalHumanBridge.commandScript(command), null)
        }
    }

    DisposableEffect(lifecycleOwner, webView) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> webView.onResume()
                Lifecycle.Event.ON_PAUSE -> webView.onPause()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
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
        update = {},
        modifier = modifier.fillMaxSize(),
    )
}

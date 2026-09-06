package com.example.campusai.ui.screens.counselor

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.graphics.Color
import android.webkit.RenderProcessGoneDetail
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.Box
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
import java.net.URI

object DigitalHumanBridge {
    const val BUNDLED_ASSET_ORIGIN = "https://appassets.androidplatform.net"
    private const val BUNDLED_STAGE_URL = "$BUNDLED_ASSET_ORIGIN/assets/digital-human/index.html"

    fun stageUrl(apiBaseUrl: String, reduceMotion: Boolean = false): String =
        BUNDLED_STAGE_URL + (if (reduceMotion) "?reduceMotion=1" else "")

    fun configureScript(apiBaseUrl: String, accessToken: String): String =
        "window.CampusMateDigitalHuman.configure({apiBaseUrl:${jsString(apiBaseUrl)},accessToken:${jsString(accessToken)}});"

    fun speakScript(text: String): String =
        "window.CampusMateDigitalHuman.speak(${jsString(text)});"

    fun presentationScript(reduceMotion: Boolean): String =
        "window.CampusMateDigitalHuman.setPresentation({zoom:1.18,idleMotion:${!reduceMotion}});"

    fun commandScript(command: DigitalHumanCommand): String = when (command) {
        DigitalHumanCommand.TOGGLE_MUTE -> "window.CampusMateDigitalHuman.toggleMuted();"
        DigitalHumanCommand.TOGGLE_PAUSE -> "window.CampusMateDigitalHuman.togglePaused();"
        DigitalHumanCommand.REPLAY -> "window.CampusMateDigitalHuman.replay();"
        DigitalHumanCommand.NONE -> ""
    }

    fun isTrustedStageUrl(expectedUrl: String, candidateUrl: String): Boolean = runCatching {
        val expected = URI(expectedUrl)
        val candidate = URI(candidateUrl)
        expected.scheme.equals(candidate.scheme, ignoreCase = true) &&
            expected.host.equals(candidate.host, ignoreCase = true) &&
            effectivePort(expected) == effectivePort(candidate) &&
            expected.rawPath == candidate.rawPath &&
            expected.rawQuery == candidate.rawQuery
    }.getOrDefault(false)

    private fun effectivePort(uri: URI): Int = when {
        uri.port >= 0 -> uri.port
        uri.scheme.equals("https", ignoreCase = true) -> 443
        uri.scheme.equals("http", ignoreCase = true) -> 80
        else -> -1
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

internal enum class DigitalHumanStageLoadState { LOADING, READY, FALLBACK }

internal enum class DigitalHumanLoadEvent {
    PAGE_STARTED,
    TRUSTED_PAGE_FINISHED,
    MAIN_FRAME_FAILED,
    RENDERER_GONE,
}

internal fun nextDigitalHumanStageLoadState(event: DigitalHumanLoadEvent): DigitalHumanStageLoadState = when (event) {
    DigitalHumanLoadEvent.PAGE_STARTED -> DigitalHumanStageLoadState.LOADING
    DigitalHumanLoadEvent.TRUSTED_PAGE_FINISHED -> DigitalHumanStageLoadState.READY
    DigitalHumanLoadEvent.MAIN_FRAME_FAILED,
    DigitalHumanLoadEvent.RENDERER_GONE,
    -> DigitalHumanStageLoadState.FALLBACK
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
    reduceMotion: Boolean = false,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var lastSpokenRequestId by remember { mutableIntStateOf(0) }
    var lastCommandRequestId by remember { mutableIntStateOf(0) }
    val stageUrl = remember(apiBaseUrl, reduceMotion) {
        DigitalHumanBridge.stageUrl(apiBaseUrl, reduceMotion)
    }
    var loadState by remember(stageUrl) { mutableStateOf(DigitalHumanStageLoadState.LOADING) }
    val pageReady = loadState == DigitalHumanStageLoadState.READY
    val webView = remember(stageUrl) {
        WebView(context).apply {
            setLayerType(android.view.View.LAYER_TYPE_HARDWARE, null)
            setBackgroundColor(Color.TRANSPARENT)
            setRendererPriorityPolicy(WebView.RENDERER_PRIORITY_BOUND, false)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.mediaPlaybackRequiresUserGesture = false
            settings.loadsImagesAutomatically = true
            settings.cacheMode = android.webkit.WebSettings.LOAD_DEFAULT
            settings.setSupportZoom(false)
            settings.builtInZoomControls = false
            settings.displayZoomControls = false
            settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            webChromeClient = WebChromeClient()
            webViewClient = object : WebViewClient() {
                override fun shouldInterceptRequest(
                    view: WebView,
                    request: WebResourceRequest,
                ): WebResourceResponse? {
                    val uri = request.url
                    if (uri.scheme != "https" || uri.host != "appassets.androidplatform.net") return null
                    val assetPath = uri.path?.removePrefix("/assets/") ?: return null
                    if (assetPath.contains("..")) return null
                    return runCatching {
                        val mimeType = when {
                            assetPath.endsWith(".html") -> "text/html"
                            assetPath.endsWith(".js") -> "application/javascript"
                            assetPath.endsWith(".wasm") -> "application/wasm"
                            else -> "application/octet-stream"
                        }
                        WebResourceResponse(mimeType, null, context.assets.open(assetPath))
                    }.getOrNull()
                }

                override fun onPageStarted(view: WebView, url: String, favicon: Bitmap?) {
                    loadState = nextDigitalHumanStageLoadState(DigitalHumanLoadEvent.PAGE_STARTED)
                }

                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                    request.isForMainFrame && !DigitalHumanBridge.isTrustedStageUrl(stageUrl, request.url.toString())

                override fun onPageFinished(view: WebView, url: String) {
                    if (DigitalHumanBridge.isTrustedStageUrl(stageUrl, url)) {
                        loadState = nextDigitalHumanStageLoadState(DigitalHumanLoadEvent.TRUSTED_PAGE_FINISHED)
                    }
                }

                override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                    if (request.isForMainFrame) {
                        loadState = nextDigitalHumanStageLoadState(DigitalHumanLoadEvent.MAIN_FRAME_FAILED)
                    }
                }

                override fun onReceivedHttpError(
                    view: WebView,
                    request: WebResourceRequest,
                    errorResponse: WebResourceResponse,
                ) {
                    if (request.isForMainFrame) {
                        loadState = nextDigitalHumanStageLoadState(DigitalHumanLoadEvent.MAIN_FRAME_FAILED)
                    }
                }

                override fun onRenderProcessGone(view: WebView, detail: RenderProcessGoneDetail): Boolean {
                    loadState = nextDigitalHumanStageLoadState(DigitalHumanLoadEvent.RENDERER_GONE)
                    return true
                }
            }
            loadUrl(stageUrl)
        }
    }

    LaunchedEffect(pageReady, apiBaseUrl, accessToken) {
        if (pageReady) {
            webView.evaluateJavascript(DigitalHumanBridge.configureScript(apiBaseUrl, accessToken), null)
        }
    }
    LaunchedEffect(pageReady, reduceMotion) {
        if (pageReady) {
            webView.evaluateJavascript(DigitalHumanBridge.presentationScript(reduceMotion), null)
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

    Box(modifier.fillMaxSize()) {
        if (loadState != DigitalHumanStageLoadState.FALLBACK) {
            AndroidView(
                factory = { webView },
                update = {},
                modifier = Modifier.fillMaxSize(),
            )
        }
    }
}

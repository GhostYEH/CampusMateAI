package com.example.campusai.ui.screens.courses

import android.graphics.Bitmap
import android.webkit.ConsoleMessage
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.example.campusai.data.remote.ClassroomUrlPolicy
import com.example.campusai.ui.theme.Muted
import com.example.campusai.data.focus.voice.AndroidTextToSpeechSynthesizer
import android.os.Handler
import android.os.Looper
import org.json.JSONTokener

/** Some Android WebViews report a zero CSS viewport for `100vh` inside a Compose dialog. */
private val classroomViewportFix = """
    (function () {
      if (!document.body) return;
      if (window.__campusClassroomViewportFix) return;
      window.__campusClassroomViewportFix = true;
      function applyHeight() {
        var height = Math.max(window.innerHeight || 0, document.documentElement.clientHeight || 0);
        if (!height || !document.body) return;
        var pixels = height + 'px';
        document.documentElement.style.setProperty('height', pixels, 'important');
        document.body.style.setProperty('height', pixels, 'important');
        Array.prototype.forEach.call(document.body.children, function (element) {
          if (element.classList && element.classList.contains('h-screen')) {
            element.style.setProperty('height', pixels, 'important');
          }
        });
      }
      applyHeight();
      window.addEventListener('resize', applyHeight);
      new MutationObserver(applyHeight).observe(document.body, { childList: true });
    })();
""".trimIndent()

/** A classroom remains inside CampusMate; navigation is confined to its trusted origin. */
@Composable
internal fun ClassroomViewer(url: String, onClose: () -> Unit) {
    val context = LocalContext.current
    val origin = remember(url) { ClassroomUrlPolicy.originOf(url) }
    var webView by remember(url) { mutableStateOf<WebView?>(null) }
    var loading by remember(url) { mutableStateOf(true) }
    var pageFinished by remember(url) { mutableStateOf(false) }
    var loadError by remember(url) { mutableStateOf<String?>(null) }
    var speaking by remember(url) { mutableStateOf(false) }
    var speechError by remember(url) { mutableStateOf<String?>(null) }
    val speaker = remember(url) { AndroidTextToSpeechSynthesizer(context) }
    val mainHandler = remember { Handler(Looper.getMainLooper()) }
    BackHandler { if (webView?.canGoBack() == true) webView?.goBack() else onClose() }
    DisposableEffect(url) { onDispose { speaker.shutdown(); webView?.stopLoading(); webView?.destroy() } }
    LaunchedEffect(pageFinished, loadError) {
        if (pageFinished && loadError == null) {
            kotlinx.coroutines.delay(10000)
            webView?.evaluateJavascript(
                "!(document.body?.innerText||'').trim() || document.body?.querySelector(':scope > .h-screen')?.getBoundingClientRect().height === 0",
            ) { result ->
                if (result == "true") {
                    loadError = "课堂网页已打开，但页面高度异常。请重新加载课堂。"
                }
            }
        }
    }

    Dialog(onDismissRequest = onClose, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        Column(Modifier.fillMaxSize().background(Color(0xFFF2F1E8)).statusBarsPadding().navigationBarsPadding()) {
            Row(Modifier.fillMaxWidth().height(56.dp).background(Color(0xFF153B34)), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onClose) { Icon(Icons.Default.ArrowBack, contentDescription = "返回互动课堂", tint = Color.White) }
                Text("互动课堂", color = Color.White, fontWeight = FontWeight.Bold)
                Spacer(Modifier.weight(1f))
                IconButton(onClick = {
                    if (speaking) {
                        speaker.stop(); speaking = false
                    } else {
                        webView?.evaluateJavascript("""
                            (function () {
                              var center = document.elementFromPoint(innerWidth * .5, innerHeight * .42);
                              var scene = center && center.closest('[data-scene-id], [data-testid="slide-canvas"], .slide, main');
                              var text = (scene || document.querySelector('main') || document.body).innerText || '';
                              return text.trim().slice(0, 1800);
                            })()
                        """.trimIndent()) { raw ->
                            val text = runCatching { JSONTokener(raw).nextValue() as? String }.getOrNull()?.trim().orEmpty()
                            if (text.isBlank()) {
                                speechError = "本页没有可朗读的文字"
                            } else {
                                speechError = null; speaking = true
                                speaker.speak(text,
                                    onDone = { mainHandler.post { speaking = false } },
                                    onError = { message -> mainHandler.post { speaking = false; speechError = message } })
                            }
                        }
                    }
                }) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(if (speaking) Icons.Default.Stop else Icons.Default.VolumeUp,
                            contentDescription = if (speaking) "停止朗读" else "朗读当前页",
                            tint = Color.White, modifier = Modifier.size(20.dp))
                        Text(if (speaking) "停止" else "朗读", color = Color.White, fontSize = 10.sp)
                    }
                }
                if (loading) CircularProgressIndicator(Modifier.size(18.dp), color = Color.White, strokeWidth = 2.dp)
                Spacer(Modifier.width(18.dp))
            }
            Box(Modifier.fillMaxSize()) {
                AndroidView(
                    modifier = Modifier.fillMaxSize(),
                    factory = {
                        WebView(context).apply {
                            settings.javaScriptEnabled = true
                            settings.domStorageEnabled = true
                            // Next.js and the classroom renderer have a normal mobile
                            // browser path. Some dev WebViews append `; wv`, which makes
                            // the page take an incomplete embedded-browser branch.
                            settings.userAgentString = settings.userAgentString.replace("; wv", "")
                            settings.allowFileAccess = false
                            settings.allowContentAccess = false
                            settings.setSupportMultipleWindows(false)
                            settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
                            webChromeClient = object : WebChromeClient() {
                                override fun onConsoleMessage(message: ConsoleMessage): Boolean {
                                    if (message.messageLevel() == ConsoleMessage.MessageLevel.ERROR &&
                                        (message.message().contains("Uncaught") || message.message().contains("ChunkLoadError"))
                                    ) {
                                        loadError = "课堂网页脚本运行失败，请重新加载；若仍失败，请检查课堂服务。"
                                    }
                                    return super.onConsoleMessage(message)
                                }
                            }
                            webViewClient = object : WebViewClient() {
                                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                                    ClassroomUrlPolicy.originOf(request.url.toString()) != origin

                                override fun onPageStarted(view: WebView, pageUrl: String?, favicon: Bitmap?) {
                                    speaker.stop()
                                    speaking = false
                                    speechError = null
                                    loading = true
                                    pageFinished = false
                                    loadError = null
                                }

                                override fun onPageFinished(view: WebView, pageUrl: String?) {
                                    view.evaluateJavascript(classroomViewportFix, null)
                                    loading = false
                                    pageFinished = true
                                }

                                override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                                    if (request.isForMainFrame) {
                                        loading = false
                                        loadError = "课堂网页连接失败（错误码 ${error.errorCode}）。请检查课堂服务和手机网络。"
                                    }
                                }

                                override fun onReceivedHttpError(view: WebView, request: WebResourceRequest, errorResponse: WebResourceResponse) {
                                    if (request.isForMainFrame) {
                                        loading = false
                                        loadError = "课堂网页返回 HTTP ${errorResponse.statusCode}。请稍后重试。"
                                    }
                                }
                            }
                            webView = this
                            loadUrl(url)
                        }
                    },
                )
                if (loading) Text("课堂正在打开…", modifier = Modifier.align(Alignment.Center).background(Color(0xFFF2F1E8)).padding(12.dp), color = Muted)
                speechError?.let { Text(it, modifier = Modifier.align(Alignment.TopCenter)
                    .background(Color(0xFFF2F1E8)).padding(8.dp), color = Color(0xFF153B34)) }
                loadError?.let { message ->
                    Column(
                        Modifier.align(Alignment.Center).padding(24.dp).background(Color(0xFFF2F1E8)).padding(20.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Text(message, color = Color(0xFF153B34))
                        Spacer(Modifier.height(12.dp))
                        Button(onClick = { loadError = null; loading = true; pageFinished = false; webView?.reload() }) {
                            Text("重新加载")
                        }
                    }
                }
            }
        }
    }
}

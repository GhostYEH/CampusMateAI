package com.example.campusai.ui.screens.courses

import android.graphics.Bitmap
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.example.campusai.data.remote.ClassroomUrlPolicy
import com.example.campusai.ui.theme.Muted

/** A classroom remains inside CampusMate; navigation is confined to its trusted origin. */
@Composable
internal fun ClassroomViewer(url: String, onClose: () -> Unit) {
    val context = LocalContext.current
    val origin = remember(url) { ClassroomUrlPolicy.originOf(url) }
    var webView by remember(url) { mutableStateOf<WebView?>(null) }
    var loading by remember(url) { mutableStateOf(true) }
    BackHandler { if (webView?.canGoBack() == true) webView?.goBack() else onClose() }
    DisposableEffect(url) { onDispose { webView?.stopLoading(); webView?.destroy() } }

    Dialog(onDismissRequest = onClose, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        Column(Modifier.fillMaxSize().background(Color(0xFFF2F1E8)).statusBarsPadding().navigationBarsPadding()) {
            Row(Modifier.fillMaxWidth().height(56.dp).background(Color(0xFF153B34)), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onClose) { Icon(Icons.Default.ArrowBack, contentDescription = "返回互动课堂", tint = Color.White) }
                Text("互动课堂", color = Color.White, fontWeight = FontWeight.Bold)
                Spacer(Modifier.weight(1f))
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
                            settings.allowFileAccess = false
                            settings.allowContentAccess = false
                            settings.setSupportMultipleWindows(false)
                            settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
                            webViewClient = object : WebViewClient() {
                                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                                    ClassroomUrlPolicy.originOf(request.url.toString()) != origin

                                override fun onPageStarted(view: WebView, pageUrl: String?, favicon: Bitmap?) {
                                    loading = true
                                }

                                override fun onPageFinished(view: WebView, pageUrl: String?) {
                                    loading = false
                                }
                            }
                            webView = this
                            loadUrl(url)
                        }
                    },
                )
                if (loading) Text("课堂正在打开…", modifier = Modifier.align(Alignment.Center).background(Color(0xFFF2F1E8)).padding(12.dp), color = Muted)
            }
        }
    }
}

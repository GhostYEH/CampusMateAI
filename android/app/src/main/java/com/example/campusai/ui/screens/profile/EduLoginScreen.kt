package com.example.campusai.ui.screens.profile

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.delay

/** 解析 Cookie 字符串 "k1=v1; k2=v2" 为 Map。安全处理 = 与 ; 。 */
fun parseCookieString(cookieStr: String): Map<String, String> {
    val result = mutableMapOf<String, String>()
    for (part in cookieStr.split(";")) {
        val trimmed = part.trim()
        if (trimmed.isEmpty()) continue
        val eqIdx = trimmed.indexOf("=")
        if (eqIdx <= 0) continue
        val key = trimmed.substring(0, eqIdx).trim()
        val value = trimmed.substring(eqIdx + 1).trim()
        if (key.isNotEmpty()) result[key] = value
    }
    return result
}

/** 从多个 URL 合并 Cookie（处理跨子域登录跳转）。 */
fun collectCookiesFromUrls(urls: List<String>): Map<String, String> {
    val merged = mutableMapOf<String, String>()
    val cm = CookieManager.getInstance()
    for (url in urls) {
        if (url.isBlank()) continue
        val cookieStr = cm.getCookie(url) ?: continue
        if (cookieStr.isBlank()) continue
        for ((k, v) in parseCookieString(cookieStr)) {
            merged[k] = v
        }
    }
    return merged
}

/** EduLoginScreen — 内嵌 WebView 教务登录页。

 * 用户在 WebView 中完成学校官方登录；
 * 自动检测页面跳转 + 提供"我已完成登录"按钮兜底；
 * 登录成功后提取 Cookie 回传后端验证。
 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun EduLoginScreen(
    loginUrl: String,
    connectionId: String,
    viewModel: EduViewModel,
    onBack: () -> Unit,
) {
    var webViewRef by remember { mutableStateOf<WebView?>(null) }
    var currentUrl by remember { mutableStateOf(loginUrl) }
    var lastVerifyTime by remember { mutableStateOf(0L) }
    var verifyInFlight by remember { mutableStateOf(false) }
    var capturedUserAgent by remember { mutableStateOf<String?>(null) }
    val state by viewModel.state.collectAsState()

    BackHandler {
        val wv = webViewRef
        if (wv != null && wv.canGoBack()) wv.goBack() else onBack()
    }

    // 设置 connectionId 到 ViewModel（EduLoginScreen 有独立 ViewModel 实例）
    LaunchedEffect(connectionId) {
        viewModel.setConnectionId(connectionId)
    }

    // cookie 提取 + 回传验证（闭包捕获 viewModel）
    val verifyLogin: (String?, Boolean) -> Unit = remember(viewModel, loginUrl) { { url, force ->
        if (!verifyInFlight && !url.isNullOrBlank()) {
            // 合并 currentUrl 和 loginUrl 的 cookie（处理跨子域跳转）
            val cookies = collectCookiesFromUrls(listOf(url, currentUrl, loginUrl))
            if (cookies.isNotEmpty()) {
                val now = System.currentTimeMillis()
                if (force || now - lastVerifyTime > 1200) {
                    lastVerifyTime = now
                    verifyInFlight = true
                    viewModel.submitCookies(cookies, url, capturedUserAgent)
                }
            }
        }
    } }

    // 监听状态变化，清除 inFlight flag
    LaunchedEffect(state) {
        if (state !is EduUiState.Verifying) {
            verifyInFlight = false
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onBack) { Text("返回") }
            Text("教务系统登录", style = MaterialTheme.typography.titleMedium)
            TextButton(onClick = {
                viewModel.reset()
                onBack()
            }) { Text("取消") }
        }
        Text(
            "请在下方页面中完成学校教务系统的登录。CampusMate 不保存您的密码，仅在校验后使用登录会话同步课表和成绩。",
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
            style = MaterialTheme.typography.bodySmall,
        )
        Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
            AndroidView(
                factory = { ctx ->
                    WebView(ctx).apply {
                        layoutParams = ViewGroup.LayoutParams(
                            ViewGroup.LayoutParams.MATCH_PARENT,
                            ViewGroup.LayoutParams.MATCH_PARENT,
                        )
                        settings.javaScriptEnabled = true
                        settings.domStorageEnabled = true
                        settings.databaseEnabled = true
                        CookieManager.getInstance().setAcceptCookie(true)
                        CookieManager.getInstance().setAcceptThirdPartyCookies(this, true)
                        capturedUserAgent = settings.userAgentString
                        webViewClient = object : WebViewClient() {
                            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                                currentUrl = url ?: ""
                            }
                            override fun onPageFinished(view: WebView?, url: String?) {
                                currentUrl = url ?: ""
                                CookieManager.getInstance().flush()
                                val now = System.currentTimeMillis()
                                if (now - lastVerifyTime > 1200 && !verifyInFlight) {
                                    lastVerifyTime = now
                                    verifyLogin(url, false)
                                }
                            }
                            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                                return false
                            }
                        }
                        webChromeClient = object : WebChromeClient() {}
                        loadUrl(loginUrl)
                        webViewRef = this
                    }
                },
                modifier = Modifier.fillMaxSize(),
            )
            if (state is EduUiState.Verifying) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
            }
        }
        if (state is EduUiState.Error) {
            Text(
                (state as EduUiState.Error).message,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                style = MaterialTheme.typography.bodySmall,
            )
        }
        Button(
            onClick = {
                CookieManager.getInstance().flush()
                verifyLogin(currentUrl.ifBlank { loginUrl }, true)
            },
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            enabled = state !is EduUiState.Verifying && !verifyInFlight,
        ) {
            Text("我已完成登录")
        }
    }

    LaunchedEffect(state) {
        if (state is EduUiState.Connected || state is EduUiState.Synced) {
            delay(300)
            onBack()
        }
    }
}

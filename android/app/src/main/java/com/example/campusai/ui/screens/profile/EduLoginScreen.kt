package com.example.campusai.ui.screens.profile

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
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
import com.example.campusai.data.remote.EduCookieDto
import kotlinx.coroutines.delay
import java.net.URI

/** Parses the Cookie header as ordered entries; never collapse same-name cookies. */
fun parseCookieString(cookieStr: String): List<Pair<String, String>> {
    val result = mutableListOf<Pair<String, String>>()
    for (part in cookieStr.split(";")) {
        val trimmed = part.trim()
        if (trimmed.isEmpty()) continue
        val eqIdx = trimmed.indexOf("=")
        if (eqIdx <= 0) continue
        val key = trimmed.substring(0, eqIdx).trim()
        val value = trimmed.substring(eqIdx + 1).trim()
        if (key.isNotEmpty()) result += key to value
    }
    return result
}

private fun canonicalHttpsOrigin(url: String): String? {
    return try {
        val parsed = URI(url)
        val host = parsed.host?.lowercase()
        if (host == null || parsed.scheme?.lowercase() != "https" || parsed.userInfo != null) null
        else {
            val port = when (parsed.port) { -1, 443 -> ""; else -> ":${parsed.port}" }
            "https://$host$port"
        }
    } catch (_: Exception) {
        null
    }
}

/** Only exact HTTPS origins supplied by the backend login flow may be loaded. */
fun isAllowedEduNavigation(url: String, loginUrl: String, backendAllowedOrigins: List<String> = emptyList()): Boolean {
    val target = canonicalHttpsOrigin(url) ?: return false
    val allowed = buildSet {
        canonicalHttpsOrigin(loginUrl)?.let(::add)
        backendAllowedOrigins.mapNotNull(::canonicalHttpsOrigin).forEach(::add)
    }
    return target in allowed
}

/** Fail closed for every WebView callback, including resource/POST callbacks. */
fun shouldBlockEduRequest(url: String?, loginUrl: String, backendAllowedOrigins: List<String> = emptyList()): Boolean =
    url == null || !isAllowedEduNavigation(url, loginUrl, backendAllowedOrigins)

/** CookieManager exposes name/value only; unavailable attributes stay null. */
fun cookieDtosForUrl(cookieStr: String, url: String): List<EduCookieDto> {
    val parsed = URI(url)
    val domain = parsed.host?.lowercase() ?: return emptyList()
    return parseCookieString(cookieStr).map { (name, value) ->
        EduCookieDto(name = name, value = value, domain = domain, source_url = url, host_only = true)
    }
}

/** Read cookies only from approved login origins and retain same-name entries by source domain. */
fun collectCookiesFromUrls(
    urls: List<String>,
    loginUrl: String,
    backendAllowedOrigins: List<String> = emptyList(),
): List<EduCookieDto> {
    val jar = mutableListOf<EduCookieDto>()
    val cm = CookieManager.getInstance()
    for (url in urls) {
        if (url.isBlank() || !isAllowedEduNavigation(url, loginUrl, backendAllowedOrigins)) continue
        val cookieStr = cm.getCookie(url) ?: continue
        if (cookieStr.isBlank()) continue
        jar += cookieDtosForUrl(cookieStr, url)
    }
    return jar.distinctBy { listOf(it.name, it.value, it.domain, it.path, it.source_url, it.host_only).joinToString("\u0000") }
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
    backendAllowedOrigins: List<String> = emptyList(),
    onBack: () -> Unit,
) {
    var webViewRef by remember { mutableStateOf<WebView?>(null) }
    var currentUrl by remember { mutableStateOf(loginUrl) }
    var lastVerifyTime by remember { mutableStateOf(0L) }
    var verifyInFlight by remember { mutableStateOf(false) }
    var capturedUserAgent by remember { mutableStateOf<String?>(null) }
    val state by viewModel.state.collectAsState()

    val clearLoginState = {
        CookieManager.getInstance().removeAllCookies(null)
        CookieManager.getInstance().flush()
        webViewRef?.apply {
            stopLoading()
            loadUrl("about:blank")
            clearHistory()
            clearCache(true)
            removeAllViews()
            destroy()
        }
        webViewRef = null
        capturedUserAgent = null
        currentUrl = ""
    }

    BackHandler {
        val wv = webViewRef
        if (wv != null && wv.canGoBack()) wv.goBack() else {
            clearLoginState()
            onBack()
        }
    }

    DisposableEffect(connectionId) { onDispose { clearLoginState() } }

    // 设置 connectionId 到 ViewModel（EduLoginScreen 有独立 ViewModel 实例）
    LaunchedEffect(connectionId) {
        viewModel.setConnectionId(connectionId)
    }

    // cookie 提取 + 回传验证（闭包捕获 viewModel）
    val verifyLogin: (String?, Boolean) -> Unit = remember(viewModel, loginUrl, backendAllowedOrigins) { { url, force ->
        if (!verifyInFlight && !url.isNullOrBlank()) {
            val cookieJar = collectCookiesFromUrls(listOf(url, currentUrl, loginUrl), loginUrl, backendAllowedOrigins)
            if (cookieJar.isNotEmpty()) {
                val now = System.currentTimeMillis()
                if (force || now - lastVerifyTime > 1200) {
                    lastVerifyTime = now
                    verifyInFlight = true
                    viewModel.submitCookies(cookieJar, url, capturedUserAgent)
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
                                if (url != null && isAllowedEduNavigation(url, loginUrl, backendAllowedOrigins)) currentUrl = url
                            }
                            override fun onPageFinished(view: WebView?, url: String?) {
                                if (shouldBlockEduRequest(url, loginUrl, backendAllowedOrigins)) {
                                    view?.stopLoading()
                                    view?.loadUrl("about:blank")
                                    CookieManager.getInstance().removeAllCookies(null)
                                    CookieManager.getInstance().flush()
                                    return
                                }
                                currentUrl = url ?: return
                                CookieManager.getInstance().flush()
                                val now = System.currentTimeMillis()
                                if (now - lastVerifyTime > 1200 && !verifyInFlight) {
                                    lastVerifyTime = now
                                    verifyLogin(url, false)
                                }
                            }
                            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                                return shouldBlockEduRequest(request?.url?.toString(), loginUrl, backendAllowedOrigins)
                            }
                            override fun shouldInterceptRequest(view: WebView?, request: WebResourceRequest?): WebResourceResponse? {
                                if (!shouldBlockEduRequest(request?.url?.toString(), loginUrl, backendAllowedOrigins)) return null
                                return WebResourceResponse("text/plain", "UTF-8", 403, "Blocked", emptyMap(), null)
                            }
                        }
                        webChromeClient = object : WebChromeClient() {}
                        if (isAllowedEduNavigation(loginUrl, loginUrl, backendAllowedOrigins)) loadUrl(loginUrl)
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
            clearLoginState()
            onBack()
        }
    }
}

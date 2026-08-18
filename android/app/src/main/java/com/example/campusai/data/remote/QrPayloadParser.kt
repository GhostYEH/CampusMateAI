package com.example.campusai.data.remote

/**
 * QR payload 协议 — 跨端统一解析。
 *
 * 格式: campusmate://auth/web-login?v=1&sid=<session_id>&token=<scan_token>
 *
 * 不接受任意 URL，严格校验 scheme / host / path / version / 参数。
 * 纯 Kotlin 实现，不依赖 android.net.Uri，便于 JVM 单元测试。
 */
object QrPayloadParser {
    private const val SCHEME = "campusmate"
    private const val HOST = "auth"
    private const val PATH = "/web-login"
    private const val VERSION = 1

    data class QrPayload(
        val sessionId: String,
        val scanToken: String,
        val version: Int = VERSION,
    )

    /**
     * 解析并严格校验二维码字符串。
     * 返回 null 表示不是有效的 CampusMate 登录二维码。
     */
    fun parse(raw: String?): QrPayload? {
        if (raw.isNullOrBlank()) return null
        val trimmed = raw.trim()
        if (!trimmed.startsWith("$SCHEME://")) return null
        // 手动解析: campusmate://auth/web-login?v=1&sid=xxx&token=yyy
        val afterScheme = trimmed.substring("$SCHEME://".length)
        // 分离 authority+path 和 query
        val queryStart = afterScheme.indexOf('?')
        val authorityAndPath = if (queryStart >= 0) afterScheme.substring(0, queryStart) else afterScheme
        val queryString = if (queryStart >= 0) afterScheme.substring(queryStart + 1) else ""
        // 分离 host 和 path
        val pathStart = authorityAndPath.indexOf('/')
        val host = if (pathStart >= 0) authorityAndPath.substring(0, pathStart) else authorityAndPath
        val path = if (pathStart >= 0) authorityAndPath.substring(pathStart) else ""
        if (host != HOST) return null
        if (path != PATH) return null
        // 解析 query params
        val params = mutableMapOf<String, String>()
        for (pair in queryString.split("&")) {
            val eq = pair.indexOf('=')
            if (eq >= 0) {
                val key = pair.substring(0, eq)
                val value = pair.substring(eq + 1)
                params[key] = value
            }
        }
        val version = params["v"]?.toIntOrNull() ?: return null
        if (version != VERSION) return null
        val sessionId = params["sid"] ?: return null
        val scanToken = params["token"] ?: return null
        if (sessionId.length < 16) return null
        if (scanToken.length < 32) return null
        return QrPayload(sessionId = sessionId, scanToken = scanToken, version = version)
    }
}

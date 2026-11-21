package com.example.campusai.data.classroom.nativeplayer

import java.net.URI

/**
 * 解析后的课堂媒体地址。
 *
 * [trusted] 只表示「这个地址属于当前课堂、当前服务域」的受保护媒体路径；
 * 只有 trusted 的请求才允许附带本站 Bearer。外域绝对地址可以展示，但绝不带本站凭证。
 */
data class ClassroomMediaTarget(
    val url: String,
    val trusted: Boolean,
    val relativeMediaPath: String? = null,
)

/**
 * 经典课堂 / 自主选题课堂的媒体地址与凭证边界。
 *
 * 播放契约固定下发本站相对地址，例如
 * `/api/v1/courses/{course_id}/interactive-classroom/{session_id}/media/media/img_1.png`。
 * 第一段 `media` 是路由前缀，后一段 `media|audio` 是资源目录，客户端必须原样保留，
 * 不能把重复段合并成 `/media/img_1.png`。
 */
object ClassroomMediaPolicy {
    private val mediaPathRegex = Regex("^(media|audio)/[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

    /** 当前课堂媒体接口的路径前缀；受管课堂没有这组媒体代理，返回 null。 */
    fun mediaBasePath(apiBaseUrl: String, ref: NativeClassroomRef): String? {
        val base = apiBasePath(apiBaseUrl) ?: return null
        return when (ref.source) {
            NativeClassroomSource.COURSE_CLASSIC -> {
                val course = ref.courseId.trim()
                val session = ref.sessionId.orEmpty().trim()
                if (course.isBlank() || session.isBlank()) {
                    null
                } else {
                    "$base/courses/$course/interactive-classroom/$session/media"
                }
            }
            NativeClassroomSource.SELF_CLASSIC -> {
                val session = ref.sessionId.orEmpty().trim()
                if (session.isBlank()) null else "$base/self-classroom/$session/media"
            }
            NativeClassroomSource.MANAGED -> null
        }
    }

    fun resolve(source: String?, apiBaseUrl: String, ref: NativeClassroomRef): ClassroomMediaTarget? =
        resolve(source, apiBaseUrl, mediaBasePath(apiBaseUrl, ref))

    /**
     * 将服务端媒体引用解析成绝对地址。
     *
     * [mediaBasePath] 是当前课堂媒体接口前缀；只有经典/自主课堂才有值。
     */
    fun resolve(source: String?, apiBaseUrl: String, mediaBasePath: String?): ClassroomMediaTarget? {
        val value = source?.trim().orEmpty()
        if (value.isBlank()) return null
        val origin = apiOrigin(apiBaseUrl) ?: return null
        fun target(url: String) = ClassroomMediaTarget(
            url = url,
            trusted = isTrustedPath(url, apiBaseUrl, mediaBasePath),
        )
        return when {
            value.startsWith("data:", ignoreCase = true) ->
                ClassroomMediaTarget(value, trusted = false)
            value.startsWith("http://", ignoreCase = true) || value.startsWith("https://", ignoreCase = true) ->
                target(value)
            value.startsWith("//") -> target("https:$value")
            value.startsWith("/") -> target(origin + value)
            mediaBasePath != null &&
                (value.startsWith("media/", ignoreCase = true) || value.startsWith("audio/", ignoreCase = true)) ->
                target("$origin$mediaBasePath/$value")
            value.contains('.') && !value.contains(' ') && !value.startsWith("asset:", ignoreCase = true) -> {
                // 纯文件名按当前课堂的 media 目录补齐；带目录的相对路径维持旧版同源拼接。
                val bareName = !value.contains('/')
                val url = if (mediaBasePath != null && bareName) {
                    "$origin$mediaBasePath/media/$value"
                } else {
                    "$origin/${value.trimStart('/')}"
                }
                target(url)
            }
            else -> null
        }
    }

    /** 只有当前课堂媒体接口下的 `media|audio` 资源才允许携带本站凭证。 */
    fun isTrusted(url: String, apiBaseUrl: String, ref: NativeClassroomRef): Boolean {
        val mediaBase = mediaBasePath(apiBaseUrl, ref) ?: return false
        return isTrustedPath(url, apiBaseUrl, mediaBase)
    }

    /**
     * 可信课堂媒体才返回 `Bearer <token>`；外域地址或同源非课堂媒体路径一律返回 null。
     * Coil/Media3 拦截器与单元测试共用这一判定，避免“解析对了但请求仍裸奔”。
     */
    fun authorizationHeader(
        url: String,
        apiBaseUrl: String,
        ref: NativeClassroomRef,
        token: String?,
    ): String? {
        if (!isTrusted(url, apiBaseUrl, ref)) return null
        val value = token?.trim().orEmpty()
        return if (value.isEmpty()) null else "Bearer $value"
    }

    /** scheme/host/port 完全相同；用于判断重定向目标是否仍在本站。 */
    fun isSameApiOrigin(url: String, apiBaseUrl: String): Boolean {
        val target = runCatching { URI(url.trim()) }.getOrNull() ?: return false
        val api = runCatching { URI(apiBaseUrl.trim()) }.getOrNull() ?: return false
        if (target.rawUserInfo != null) return false
        return target.scheme.equals(api.scheme, ignoreCase = true) &&
            target.host.equals(api.host, ignoreCase = true) &&
            effectivePort(target) == effectivePort(api)
    }

    private fun isTrustedPath(url: String, apiBaseUrl: String, mediaBasePath: String?): Boolean {
        if (mediaBasePath.isNullOrBlank()) return false
        if (!isSameApiOrigin(url, apiBaseUrl)) return false
        val path = runCatching { URI(url.trim()).path }.getOrNull().orEmpty()
        if (!path.startsWith("$mediaBasePath/")) return false
        val relative = path.removePrefix("$mediaBasePath/")
        return mediaPathRegex.matches(relative)
    }

    private fun apiOrigin(apiBaseUrl: String): String? {
        val uri = runCatching { URI(apiBaseUrl.trim()) }.getOrNull() ?: return null
        val scheme = uri.scheme ?: return null
        val host = uri.host ?: return null
        return if (uri.port >= 0) "$scheme://$host:${uri.port}" else "$scheme://$host"
    }

    private fun apiBasePath(apiBaseUrl: String): String? {
        val path = runCatching { URI(apiBaseUrl.trim()).path }.getOrNull() ?: return null
        return path.trimEnd('/')
    }

    private fun effectivePort(uri: URI): Int = when {
        uri.port >= 0 -> uri.port
        uri.scheme.equals("https", ignoreCase = true) -> 443
        uri.scheme.equals("http", ignoreCase = true) -> 80
        else -> -1
    }
}

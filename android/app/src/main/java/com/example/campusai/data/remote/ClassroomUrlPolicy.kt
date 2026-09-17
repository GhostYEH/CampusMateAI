package com.example.campusai.data.remote

import java.net.URI
import java.util.Locale

/**
 * 互动课堂 URL 准入策略 —— Android 侧唯一的 URL 判定点。
 *
 * 为什么需要它：原来 `Intent(Intent.ACTION_VIEW, Uri.parse(url))` 直接把后端返回的
 * 任意字符串交给系统浏览器，后端一旦返回或被人篡改成 `file://`、`javascript:`、
 * 恶意站点或带用户名密码的地址，就会在设备上被无条件打开。
 *
 * 约束（全部为硬性，任一条不满足即拒绝）：
 * - 只允许 **https**；
 * - scheme + host + port 必须与后端下发的可信 Origin **精确匹配**（含端口）；
 * - 禁止 file / content / javascript / data / about / blob / intent 等协议；
 * - 禁止 URL 携带用户名或密码；
 * - 禁止回环、私网、链路本地与未指定地址；
 * - 禁止路径穿越（`..`）；
 * - 不可信 URL **绝不**交给 `Intent.ACTION_VIEW`。
 *
 * 用 `java.net.URI` 而不是 `android.net.Uri`，这样纯 JVM 单测即可覆盖（不需要 Robolectric）。
 */
object ClassroomUrlPolicy {

    /** 允许的协议。学生浏览器只应通过 HTTPS 打开课堂。 */
    private val ALLOWED_SCHEMES = setOf("https")

    /** 明确禁止的协议（用于快速失败与可读的错误信息）。 */
    private val FORBIDDEN_SCHEMES = setOf(
        "file", "content", "javascript", "data", "about", "blob", "intent", "android_app",
    )

    /**
     * 把后端下发的 Origin 列表归一化成 `scheme://host[:port]`。
     * 非法条目与不可信协议一律丢弃（fail-closed：空列表 = 全部拒绝）。
     */
    fun normalizeOrigins(origins: List<String?>?): List<String> {
        val out = LinkedHashSet<String>()
        origins.orEmpty().forEach { entry ->
            val origin = originOf(entry) ?: return@forEach
            if (!isAllowedScheme(origin)) return@forEach
            if (isLoopbackOrPrivate(hostOf(entry))) return@forEach
            out.add(origin)
        }
        return out.toList()
    }

    /** 取完整 origin（scheme + host + port）；非法或不可解析返回 null。 */
    fun originOf(url: String?): String? {
        val parsed = parse(url) ?: return null
        val scheme = parsed.scheme?.lowercase(Locale.ROOT) ?: return null
        val host = parsed.host?.lowercase(Locale.ROOT) ?: return null
        if (host.isEmpty()) return null
        val port = parsed.port
        return if (port == -1) "$scheme://$host" else "$scheme://$host:$port"
    }

    /** 是否属于允许的协议。 */
    fun isAllowedScheme(url: String?): Boolean = schemeOf(url) in ALLOWED_SCHEMES

    /** 是否属于明确禁止的协议。 */
    fun isForbiddenScheme(url: String?): Boolean = schemeOf(url) in FORBIDDEN_SCHEMES

    /**
     * URL 是否可信：协议、用户名密码、路径穿越、地址范围、Origin 精确匹配全部通过。
     */
    fun isTrusted(url: String?, trustedOrigins: List<String?>?): Boolean {
        val parsed = parse(url) ?: return false
        if (schemeOf(url) !in ALLOWED_SCHEMES) return false
        val host = parsed.host?.lowercase(Locale.ROOT) ?: return false
        if (host.isEmpty()) return false
        // 禁止用户名/密码（凭据绝不进入 URL）
        if (!parsed.userInfo.isNullOrEmpty()) return false
        // 禁止路径穿越
        if (parsed.path.orEmpty().contains("..")) return false
        if (isLoopbackOrPrivate(host)) return false
        val allowed = normalizeOrigins(trustedOrigins)
        if (allowed.isEmpty()) return false
        return allowed.contains(originOf(url))
    }

    /**
     * 可安全交给系统浏览器打开的 URL；不可信时返回 null。
     * **调用方必须用返回值构造 Intent，绝不要直接用原始字符串。**
     */
    fun sanitize(url: String?, trustedOrigins: List<String?>?): String? =
        if (isTrusted(url, trustedOrigins)) url else null

    /** 供 UI 展示的拒绝原因（不含任何 URL 细节，避免泄漏）。 */
    fun rejectionReason(url: String?, trustedOrigins: List<String?>?): String = when {
        url.isNullOrBlank() -> "课堂地址为空"
        isForbiddenScheme(url) -> "课堂地址使用了不允许的协议"
        !isAllowedScheme(url) -> "课堂地址必须使用 HTTPS"
        parse(url)?.userInfo?.isNotEmpty() == true -> "课堂地址不能包含用户名或密码"
        parse(url)?.path.orEmpty().contains("..") -> "课堂地址路径非法"
        isLoopbackOrPrivate(hostOf(url)) -> "课堂地址指向本地或内网，已阻止打开"
        normalizeOrigins(trustedOrigins).isEmpty() -> "尚未配置可信的互动课堂服务地址"
        else -> "课堂地址不属于已配置的互动课堂服务"
    }

    // ===== 内部 =====

    /**
     * 取协议名。**手工扫描**而不是依赖 `URI.scheme`：像
     * `data:text/html,<script>1</script>` 这类含非法字符的 URL 会让 `URI()` 直接抛错，
     * 一旦因此漏判协议，禁止协议就可能被放行。
     */
    private fun schemeOf(url: String?): String {
        val text = url?.trim().orEmpty()
        if (text.isEmpty()) return ""
        val colon = text.indexOf(':')
        if (colon <= 0) return ""
        val candidate = text.substring(0, colon).lowercase(Locale.ROOT)
        // 合法 scheme 只允许字母/数字/+/-/.，且以字母开头
        if (!candidate.first().isLetter()) return ""
        if (!candidate.all { it.isLetterOrDigit() || it == '+' || it == '-' || it == '.' }) return ""
        return candidate
    }

    private fun parse(url: String?): URI? {
        val text = url?.trim().orEmpty()
        if (text.isEmpty()) return null
        return try {
            val parsed = URI(text)
            // 必须有 scheme，且不能是相对路径
            if (parsed.scheme.isNullOrEmpty()) null else parsed
        } catch (_: Exception) {
            null
        }
    }

    private fun hostOf(url: String?): String? =
        parse(url)?.host?.lowercase(Locale.ROOT)?.takeIf { it.isNotEmpty() }

    /** 回环 / 私网 / 链路本地 / 未指定地址，以及明显的本地主机名。 */
    private fun isLoopbackOrPrivate(host: String?): Boolean {
        val raw = host?.lowercase(Locale.ROOT)?.takeIf { it.isNotEmpty() } ?: return true
        // Java 的 URI.host 对 IPv6 会带方括号（如 [::1]），统一去掉再判定
        val value = raw.removePrefix("[").removeSuffix("]")
        if (value == "localhost" || value.endsWith(".localhost") || value.endsWith(".local")) return true
        if (!value.contains('.') && !value.contains(':')) return true // 单标签主机名

        if (value.contains(':')) {
            // —— IPv6 字面量 ——
            if (isPrivateIpv6Literal(value)) return true
            // IPv4 映射/兼容形式（`::ffff:127.0.0.1`、`::ffff:7f00:1`）
            // 是朴素判定最容易漏掉的绕过形式，必须解出内嵌的 IPv4 再判一次。
            val embedded = embeddedIpv4(value)
            return embedded != null && isPrivateIpv4(embedded)
        }
        // —— IPv4 字面量 / 域名 ——
        // 注意：`fc`/`fd` 这类 IPv6 ULA 前缀判定只对含 ':' 的字面量生效，
        // 否则会把 `fd-classroom.example.edu` 这种合法域名误判成内网。
        return isPrivateIpv4(value)
    }

    /**
     * 判断 IPv6 字面量是否属于回环 / 未指定 / 链路本地 / ULA / IPv4 映射私网。
     *
     * 必须覆盖**展开写法**：`0:0:0:0:0:0:0:1` 就是 `::1`，
     * 只比较字符串的朴素实现会把它当成公网地址放行。
     */
    private fun isPrivateIpv6Literal(value: String): Boolean {
        if (value == "::" || value == "::1") return true
        if (value.startsWith("fe80:") || value.startsWith("fc") || value.startsWith("fd")) return true
        val groups = value.split(':')
        if (groups.size != 8) return false
        val numeric = groups.map { group -> group.toIntOrNull(16) ?: return false }
        if (numeric.all { it == 0 }) return true // ::
        if (numeric.take(7).all { it == 0 } && numeric[7] == 1) return true // ::1 的展开写法
        if (numeric.take(5).all { it == 0 } && numeric[5] == 0xffff) {
            // ::ffff:a.b.c.d 的十六进制展开写法
            val v4 = "${numeric[6] shr 8}.${numeric[6] and 0xff}." +
                "${numeric[7] shr 8}.${numeric[7] and 0xff}"
            return isPrivateIpv4(v4)
        }
        return false
    }

    private fun isPrivateIpv4(addr: String): Boolean {
        val value = addr.trim().lowercase(Locale.ROOT)
        if (value.isEmpty()) return true
        if (value == "0.0.0.0") return true
        if (value.startsWith("127.") || value.startsWith("10.")) return true
        if (value.startsWith("192.168.")) return true
        if (value.startsWith("169.254.")) return true
        val second = value.split(".").getOrNull(1)?.toIntOrNull()
        if (value.startsWith("172.") && second != null && second in 16..31) return true
        return false
    }

    /**
     * 解出 IPv4 映射/兼容 IPv6 里内嵌的 IPv4（`::ffff:a.b.c.d` 或 `::ffff:xxxx:xxxx`）。
     * 不是这类形式时返回 null。
     */
    private fun embeddedIpv4(value: String): String? {
        val marker = "ffff:"
        val index = value.indexOf("::ffff:")
        val tail = when {
            index >= 0 -> value.substring(index + "::ffff:".length)
            value.startsWith("0:0:0:0:0:$marker") -> value.removePrefix("0:0:0:0:0:$marker")
            else -> return null
        }
        if (tail.isEmpty()) return null
        if (tail.contains('.')) return tail
        val parts = tail.split(':')
        if (parts.size != 2) return null
        val high = parts[0].toIntOrNull(16) ?: return null
        val low = parts[1].toIntOrNull(16) ?: return null
        return "${high shr 8}.${high and 0xff}.${low shr 8}.${low and 0xff}"
    }
}

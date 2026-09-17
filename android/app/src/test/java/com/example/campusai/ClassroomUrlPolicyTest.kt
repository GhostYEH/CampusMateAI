package com.example.campusai

import com.example.campusai.data.remote.ClassroomUrlPolicy
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 互动课堂 URL 准入策略测试。
 *
 * 这些断言对应一条真实存在的安全缺口：修复前
 * `Intent(Intent.ACTION_VIEW, Uri.parse(url))` 会把后端返回的任意字符串
 * 直接交给系统浏览器（包括 file:// / javascript: / 恶意站点 / 带用户名密码的地址）。
 */
class ClassroomUrlPolicyTest {

    private val trusted = listOf("https://classroom.example.com")
    private val trustedWithPort = listOf("https://classroom.example.com:8443")

    // ===== 协议 =====

    @Test
    fun `only https is allowed`() {
        assertTrue(ClassroomUrlPolicy.isTrusted("https://classroom.example.com/classroom/r1", trusted))
        assertFalse(ClassroomUrlPolicy.isTrusted("http://classroom.example.com/classroom/r1", trusted))
    }

    @Test
    fun `dangerous schemes are rejected`() {
        val dangerous = listOf(
            "file:///etc/passwd",
            "content://com.example/secret",
            "javascript:alert(1)",
            "data:text/html,<script>1</script>",
            "about:blank",
            "blob:https://classroom.example.com/x",
            "intent://evil#Intent;scheme=https;end",
        )
        dangerous.forEach { url ->
            assertTrue("应识别为禁止协议: $url", ClassroomUrlPolicy.isForbiddenScheme(url))
            assertFalse("不得信任: $url", ClassroomUrlPolicy.isTrusted(url, trusted))
            assertNull("不得放行: $url", ClassroomUrlPolicy.sanitize(url, trusted))
        }
    }

    // ===== Origin 精确匹配 =====

    @Test
    fun `origin must match exactly including port`() {
        assertTrue(
            ClassroomUrlPolicy.isTrusted(
                "https://classroom.example.com:8443/classroom/r1",
                trustedWithPort,
            ),
        )
        // 端口不同 -> 不可信（不能退化成 host 后缀匹配）
        assertFalse(
            ClassroomUrlPolicy.isTrusted(
                "https://classroom.example.com/classroom/r1",
                trustedWithPort,
            ),
        )
        assertFalse(
            ClassroomUrlPolicy.isTrusted(
                "https://classroom.example.com:84430/classroom/r1",
                trustedWithPort,
            ),
        )
        assertFalse(
            ClassroomUrlPolicy.isTrusted(
                "https://evil.example.com/classroom/r1",
                trusted,
            ),
        )
    }

    @Test
    fun `empty whitelist rejects everything`() {
        assertFalse(ClassroomUrlPolicy.isTrusted("https://classroom.example.com/classroom/r1", emptyList()))
        assertFalse(ClassroomUrlPolicy.isTrusted("https://classroom.example.com/classroom/r1", null))
        assertNull(ClassroomUrlPolicy.sanitize("https://classroom.example.com/classroom/r1", emptyList()))
    }

    @Test
    fun `normalizeOrigins drops junk and unsafe entries`() {
        val normalized = ClassroomUrlPolicy.normalizeOrigins(
            listOf(
                "https://classroom.example.com",
                "https://classroom.example.com", // 去重
                "not a url",
                "",
                null,
                "file:///etc/passwd",
                "https://127.0.0.1:3000", // 回环
                "https://10.0.0.5", // 私网
                "https://localhost:3000",
            ),
        )
        assertEquals(listOf("https://classroom.example.com"), normalized)
    }

    // ===== 凭据与路径 =====

    @Test
    fun `urls with credentials are rejected`() {
        assertFalse(
            ClassroomUrlPolicy.isTrusted(
                "https://user:pass@classroom.example.com/classroom/r1",
                trusted,
            ),
        )
        assertNull(
            ClassroomUrlPolicy.sanitize(
                "https://user@classroom.example.com/classroom/r1",
                trusted,
            ),
        )
    }

    @Test
    fun `path traversal is rejected`() {
        assertFalse(
            ClassroomUrlPolicy.isTrusted(
                "https://classroom.example.com/classroom/../admin",
                trusted,
            ),
        )
    }

    // ===== 地址范围 =====

    @Test
    fun `loopback and private addresses are rejected`() {
        val privateHosts = listOf(
            "https://127.0.0.1:3000/classroom/r1",
            "https://localhost:3000/classroom/r1",
            "https://10.1.2.3/classroom/r1",
            "https://192.168.1.10/classroom/r1",
            "https://172.16.0.9/classroom/r1",
            "https://169.254.169.254/classroom/r1",
            "https://[::1]/classroom/r1",
        )
        privateHosts.forEach { url ->
            // 即使把该 Origin 放进白名单也必须被拒绝
            assertFalse("不得信任: $url", ClassroomUrlPolicy.isTrusted(url, listOf(url)))
        }
    }

    @Test
    fun `obfuscated ipv6 forms of private addresses are rejected`() {
        // 攻击者/错误配置可能用"IPv4 映射/兼容 IPv6"绕过朴素的内网判定
        val obfuscated = listOf(
            "https://[::ffff:127.0.0.1]/classroom/r1",
            "https://[::ffff:7f00:1]/classroom/r1",
            "https://[0:0:0:0:0:ffff:7f00:1]/classroom/r1",
            "https://[::ffff:10.0.0.5]/classroom/r1",
            "https://[::ffff:192.168.1.5]/classroom/r1",
            "https://[::ffff:169.254.169.254]/classroom/r1",
            "https://[0:0:0:0:0:0:0:1]/classroom/r1",
        )
        obfuscated.forEach { url ->
            assertFalse("混淆 IPv6 不得被信任: $url", ClassroomUrlPolicy.isTrusted(url, listOf(url)))
            assertTrue(
                "混淆 IPv6 不得进入可信 Origin 列表: $url",
                ClassroomUrlPolicy.normalizeOrigins(listOf(url)).isEmpty(),
            )
        }
    }

    @Test
    fun `public hostnames that merely start with fc or fd are not over-rejected`() {
        // IPv6 ULA 判定只应对真正的 IPv6 字面量生效，不能误伤合法域名
        val legit = "https://fd-classroom.example.edu/classroom/r1"
        assertTrue("合法公网域名被误判为内网: $legit", ClassroomUrlPolicy.isTrusted(legit, listOf(legit)))
        val legitFc = "https://fc.example.edu/classroom/r1"
        assertTrue(ClassroomUrlPolicy.isTrusted(legitFc, listOf(legitFc)))
        // 真正的 IPv6 ULA 仍然要被拒绝
        assertFalse(ClassroomUrlPolicy.isTrusted("https://[fd00::1]/classroom/r1", listOf("https://[fd00::1]/classroom/r1")))
    }

    @Test
    fun `existing legitimate https classroom links keep working`() {
        val ok = "https://classroom.example.com/classroom/room_1"
        assertTrue(ClassroomUrlPolicy.isTrusted(ok, listOf("https://classroom.example.com")))
        assertEquals(ok, ClassroomUrlPolicy.sanitize(ok, listOf("https://classroom.example.com")))
        val withPort = "https://classroom.example.edu:8443/classroom/room_1"
        assertTrue(ClassroomUrlPolicy.isTrusted(withPort, listOf("https://classroom.example.edu:8443")))
    }

    // ===== sanitize / 文案 =====

    @Test
    fun `sanitize returns the url only when trusted`() {
        val ok = "https://classroom.example.com/classroom/r1"
        assertEquals(ok, ClassroomUrlPolicy.sanitize(ok, trusted))
        assertNull(ClassroomUrlPolicy.sanitize("https://evil.example.com/classroom/r1", trusted))
        assertNull(ClassroomUrlPolicy.sanitize(null, trusted))
        assertNull(ClassroomUrlPolicy.sanitize("   ", trusted))
    }

    @Test
    fun `rejection reason is actionable and never echoes the url`() {
        val cases = listOf(
            "http://classroom.example.com/classroom/r1",
            "file:///etc/passwd",
            "https://user:pass@classroom.example.com/classroom/r1",
            "https://127.0.0.1/classroom/r1",
            "https://evil.example.com/classroom/r1",
            null,
        )
        cases.forEach { url ->
            val reason = ClassroomUrlPolicy.rejectionReason(url, trusted)
            assertTrue("必须有可读原因", reason.isNotBlank())
            assertFalse("不得回显原始 URL", reason.contains("classroom.example.com"))
            assertFalse("不得回显原始 URL", reason.contains("passwd"))
        }
    }

    @Test
    fun `rejection reason explains missing whitelist`() {
        val reason = ClassroomUrlPolicy.rejectionReason(
            "https://classroom.example.com/classroom/r1",
            emptyList(),
        )
        assertTrue(reason.contains("尚未配置"))
    }
}

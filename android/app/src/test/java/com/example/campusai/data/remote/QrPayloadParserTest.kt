package com.example.campusai.data.remote

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class QrPayloadParserTest {

    @Test
    fun `valid payload parses correctly`() {
        val sid = "qrs_abcdef1234567890"
        val token = "st_" + "a".repeat(40)
        // 构造有效 payload
        val payload = "campusmate://auth/web-login?v=1&sid=$sid&token=$token"
        val parsed = QrPayloadParser.parse(payload)
        assertNotNull(parsed)
        assertEquals(sid, parsed!!.sessionId)
        assertEquals(token, parsed.scanToken)
        assertEquals(1, parsed.version)
    }

    @Test
    fun `rejects non campusmate scheme`() {
        assertNull(QrPayloadParser.parse("https://example.com"))
        assertNull(QrPayloadParser.parse("http://auth/web-login?v=1&sid=x&token=y"))
    }

    @Test
    fun `rejects wrong host`() {
        assertNull(QrPayloadParser.parse("campusmate://other/web-login?v=1&sid=x&token=y"))
    }

    @Test
    fun `rejects wrong path`() {
        assertNull(QrPayloadParser.parse("campusmate://auth/other?v=1&sid=x&token=y"))
    }

    @Test
    fun `rejects wrong version`() {
        val sid = "qrs_abcdef1234567890"
        val token = "st_" + "a".repeat(40)
        assertNull(QrPayloadParser.parse("campusmate://auth/web-login?v=2&sid=$sid&token=$token"))
    }

    @Test
    fun `rejects missing params`() {
        assertNull(QrPayloadParser.parse("campusmate://auth/web-login?v=1"))
        assertNull(QrPayloadParser.parse("campusmate://auth/web-login?v=1&sid=x"))
        assertNull(QrPayloadParser.parse("campusmate://auth/web-login?v=1&token=y"))
    }

    @Test
    fun `rejects empty or null`() {
        assertNull(QrPayloadParser.parse(null))
        assertNull(QrPayloadParser.parse(""))
        assertNull(QrPayloadParser.parse("   "))
    }

    @Test
    fun `rejects short session_id`() {
        val token = "st_" + "a".repeat(40)
        assertNull(QrPayloadParser.parse("campusmate://auth/web-login?v=1&sid=short&token=$token"))
    }

    @Test
    fun `rejects short scan_token`() {
        val sid = "qrs_abcdef1234567890"
        assertNull(QrPayloadParser.parse("campusmate://auth/web-login?v=1&sid=$sid&token=short"))
    }

    @Test
    fun `payload does not contain user identity`() {
        val sid = "qrs_abcdef1234567890"
        val token = "st_" + "a".repeat(40)
        val payload = "campusmate://auth/web-login?v=1&sid=$sid&token=$token"
        assertTrue(!payload.contains("user_id"))
        assertTrue(!payload.contains("password"))
        assertTrue(!payload.contains("jwt"))
    }
}
package com.example.campusai.ui.screens.courses

import android.webkit.WebViewClient
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ClassroomWebErrorTest {

    @Test
    fun `main frame failures map to actionable messages`() {
        assertTrue(classroomMainFrameErrorMessage(WebViewClient.ERROR_HOST_LOOKUP).contains("找不到课堂服务器"))
        assertTrue(classroomMainFrameErrorMessage(WebViewClient.ERROR_TIMEOUT).contains("超时"))
        assertTrue(classroomMainFrameErrorMessage(WebViewClient.ERROR_FAILED_SSL_HANDSHAKE).contains("证书"))
    }

    @Test
    fun `http failures distinguish permission and server errors`() {
        assertTrue(classroomHttpErrorMessage(403).contains("权限"))
        assertTrue(classroomHttpErrorMessage(404).contains("不存在"))
        assertTrue(classroomHttpErrorMessage(503).contains("暂时不可用"))
        assertEquals("课堂网页返回 HTTP 418。请稍后重试。", classroomHttpErrorMessage(418))
    }

    @Test
    fun `generic page errors are recognized but partial warnings do not block`() {
        assertTrue(isFatalClassroomScriptSignal("Uncaught TypeError: x is undefined"))
        assertTrue(isFatalClassroomScriptSignal("ChunkLoadError: loading chunk 3 failed"))
        assertTrue(classroomPartialScriptWarning().contains("仍可继续操作"))
    }
}

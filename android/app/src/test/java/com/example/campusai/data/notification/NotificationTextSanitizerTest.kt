package com.example.campusai.data.notification

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class NotificationTextSanitizerTest {
    @Test
    fun `uses clean big text before regular text`() {
        assertEquals("请提交 实验报告", NotificationTextSanitizer.primaryText("  请提交\n实验报告  ", "普通文本"))
    }

    @Test
    fun `falls back to text and removes empty whitespace`() {
        assertEquals("普通 文本", NotificationTextSanitizer.primaryText(" ", "  普通  文本 "))
        assertNull(NotificationTextSanitizer.clean(" \n\t "))
    }
}

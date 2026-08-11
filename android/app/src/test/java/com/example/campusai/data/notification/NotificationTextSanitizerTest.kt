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

    @Test
    fun `joins distinct expanded notification lines`() {
        assertEquals(
            "辅导员：请今晚提交登记表\n班长：截止时间延长到明天",
            NotificationTextSanitizer.joinedLines(
                arrayOf(" 辅导员：请今晚提交登记表 ", "", "辅导员：请今晚提交登记表", "班长：截止时间延长到明天"),
            ),
        )
    }
}

package com.example.campusai.data.notification

import org.junit.Assert.assertEquals
import org.junit.Test

class ConversationBundlerTest {
    @Test
    fun `four consecutive messages from one group become one bundle`() {
        val rows = (0 until 4).map { index -> candidate(index.toLong(), "软件工程1班", "消息$index") }
        val bundles = ConversationBundler.bundle(rows)
        assertEquals(1, bundles.size)
        assertEquals(listOf(0L, 1L, 2L, 3L), bundles.single().notificationIds)
        assertEquals("消息0\n消息1\n消息2\n消息3", bundles.single().content)
    }

    @Test
    fun `different sources or groups are never merged`() {
        val rows = listOf(
            candidate(1, "软件工程1班", "A"),
            candidate(2, "英语1班", "B"),
            candidate(3, "软件工程1班", "C", NotificationSource.QQ),
        )
        assertEquals(3, ConversationBundler.bundle(rows).size)
    }

    private fun candidate(
        id: Long,
        group: String,
        text: String,
        source: NotificationSource = NotificationSource.WECHAT,
    ) = QueuedNotification(id, "fp$id", source, group, text, 1_000L + id)
}

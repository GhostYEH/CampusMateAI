package com.example.campusai.data.notification

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class GroupNameNormalizerTest {
    @Test
    fun `notification counters and unicode punctuation normalize to the same group`() {
        assertEquals("2024级软件1班", GroupNameNormalizer.normalize(" 2024级软件1班（3条新消息） "))
        assertEquals("2024级软件1班", GroupNameNormalizer.normalize("2024级软件1班 (3)"))
        assertEquals("高数 班群", GroupNameNormalizer.normalize("高数   班群 5条新消息"))
    }

    @Test
    fun `whitelist matching remains exact after normalization`() {
        assertTrue(GroupNameNormalizer.matches("2024级软件1班（3条消息）", setOf("2024级软件1班")))
        assertFalse(GroupNameNormalizer.matches("2024级软件1班通知", setOf("2024级软件1班")))
        assertFalse(GroupNameNormalizer.matches("张三（2024级软件1班）", setOf("2024级软件1班")))
    }
}

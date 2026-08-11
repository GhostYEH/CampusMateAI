package com.example.campusai.data.notification

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class NotificationFingerprintTest {
    @Test
    fun `identical captured notifications have the same fingerprint`() {
        assertEquals(NotificationFingerprint.create(sample()), NotificationFingerprint.create(sample()))
    }

    @Test
    fun `content conversation and package changes produce distinct fingerprints`() {
        val original = NotificationFingerprint.create(sample())

        assertNotEquals(original, NotificationFingerprint.create(sample(text = "请下周提交报告")))
        assertNotEquals(original, NotificationFingerprint.create(sample(conversationTitle = "英语班群")))
        assertNotEquals(original, NotificationFingerprint.create(sample(packageName = "com.chaoxing.mobile")))
    }

    @Test
    fun `reposted notification with a new system key keeps the same fingerprint`() {
        assertEquals(
            NotificationFingerprint.create(sample(notificationKey = "first-key")),
            NotificationFingerprint.create(sample(notificationKey = "second-key")),
        )
    }

    @Test
    fun `same text outside dedup window produces a new fingerprint`() {
        assertNotEquals(
            NotificationFingerprint.create(sample(postTime = 1_000L)),
            NotificationFingerprint.create(sample(postTime = 601_000L)),
        )
    }

    private fun sample(
        packageName: String = "com.tencent.mm",
        text: String = "请周五前提交实验报告",
        conversationTitle: String? = "高数班群",
        notificationKey: String = "0|com.tencent.mm|1|null|1000",
        postTime: Long = 1_000L,
    ) = CapturedNotification(
        notificationKey = notificationKey,
        packageName = packageName,
        notificationId = 1,
        tag = null,
        appName = "微信",
        title = "高数班群",
        text = text,
        bigText = null,
        subText = null,
        summaryText = null,
        conversationTitle = conversationTitle,
        category = "msg",
        postTime = postTime,
        isOngoing = false,
        isClearable = true,
        isGroupSummary = false,
        source = NotificationSource.WECHAT,
    )
}

package com.example.campusai.data.notification

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NotificationFilterTest {
    private val filter = NotificationFilter(campusMatePackage = "com.example.campusai")

    @Test
    fun `rejects self empty and group summary notifications`() {
        assertFalse(filter.shouldStore(sample(packageName = "com.example.campusai"), NotificationSourceSettings()))
        assertFalse(filter.shouldStore(sample(title = null, text = null), NotificationSourceSettings()))
        assertFalse(filter.shouldStore(sample(isGroupSummary = true), NotificationSourceSettings()))
    }

    @Test
    fun `honors enabled source switches`() {
        assertTrue(filter.shouldStore(sample(), NotificationSourceSettings()))
        assertFalse(filter.shouldStore(sample(), NotificationSourceSettings(wechatEnabled = false)))
        assertTrue(filter.shouldStore(sample(source = NotificationSource.XUEXITONG), NotificationSourceSettings()))
        assertFalse(filter.shouldStore(sample(source = NotificationSource.OTHER), NotificationSourceSettings()))
    }

    private fun sample(
        packageName: String = "com.tencent.mm",
        title: String? = "高数班群",
        text: String? = "请周五前提交实验报告",
        isGroupSummary: Boolean = false,
        source: NotificationSource = NotificationSource.WECHAT,
    ) = CapturedNotification(
        notificationKey = "key",
        packageName = packageName,
        notificationId = 1,
        tag = null,
        appName = null,
        title = title,
        text = text,
        bigText = null,
        subText = null,
        summaryText = null,
        conversationTitle = null,
        category = null,
        postTime = 1L,
        isOngoing = false,
        isClearable = true,
        isGroupSummary = isGroupSummary,
        source = source,
    )
}

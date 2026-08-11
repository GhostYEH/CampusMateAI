package com.example.campusai.data.notification

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NotificationFilterTest {
    private val filter = NotificationFilter(campusMatePackage = "com.example.campusai")

    @Test
    fun `rejects self empty and group summary notifications`() {
        assertFalse(filter.shouldStore(sample(packageName = "com.example.campusai"), NotificationSourceSettings(), setOf("高数班群")))
        assertFalse(filter.shouldStore(sample(title = null, text = null), NotificationSourceSettings(), setOf("高数班群")))
        assertFalse(filter.shouldStore(sample(isGroupSummary = true), NotificationSourceSettings(), setOf("高数班群")))
    }

    @Test
    fun `honors enabled source switches`() {
        assertTrue(filter.shouldStore(sample(), NotificationSourceSettings(), setOf("高数班群")))
        assertFalse(filter.shouldStore(sample(), NotificationSourceSettings(wechatEnabled = false), setOf("高数班群")))
        assertTrue(filter.shouldStore(sample(source = NotificationSource.XUEXITONG), NotificationSourceSettings(), setOf("高数班群")))
        assertFalse(filter.shouldStore(sample(source = NotificationSource.OTHER), NotificationSourceSettings(), setOf("高数班群")))
    }

    @Test
    fun `wechat strict whitelist rejects when empty`() {
        assertFalse(filter.shouldStore(sample(), NotificationSourceSettings(), emptySet()))
    }

    @Test
    fun `wechat strict whitelist accepts when group matches title`() {
        assertTrue(filter.shouldStore(sample(), NotificationSourceSettings(), setOf("高数班群")))
    }

    @Test
    fun `wechat strict whitelist accepts when group matches conversation title`() {
        val notification = sample(title = "张三", conversationTitle = "高数班群")
        assertTrue(filter.shouldStore(notification, NotificationSourceSettings(), setOf("高数班群")))
    }

    @Test
    fun `wechat strict whitelist rejects when group not in whitelist`() {
        assertFalse(filter.shouldStore(sample(), NotificationSourceSettings(), setOf("英语角")))
    }

    @Test
    fun `wechat strict whitelist does not affect other sources`() {
        assertTrue(filter.shouldStore(sample(source = NotificationSource.XUEXITONG), NotificationSourceSettings(), emptySet()))
    }

    @Test
    fun `qq switch accepts campus affairs and rejects ordinary chat`() {
        val enabled = NotificationSourceSettings(qqEnabled = true)
        assertTrue(filter.shouldStore(
            sample(packageName = "com.tencent.mobileqq", source = NotificationSource.QQ),
            enabled,
        ))
        assertFalse(filter.shouldStore(
            sample(
                packageName = "com.tencent.mobileqq",
                title = "教务班群",
                text = "今天天气不错，晚点一起去操场吧",
                source = NotificationSource.QQ,
            ),
            enabled,
        ))
        assertFalse(filter.shouldStore(
            sample(packageName = "com.tencent.mobileqq", source = NotificationSource.QQ),
            NotificationSourceSettings(qqEnabled = false),
        ))
        assertTrue(filter.shouldStore(
            sample(
                packageName = "com.tencent.mobileqq",
                title = "教务处选课通知",
                text = "请尽快查看详情",
                source = NotificationSource.QQ,
            ),
            enabled,
        ))
    }

    @Test
    fun `hard excluded body cannot be accepted by campus heading fallback`() {
        val enabled = NotificationSourceSettings(qqEnabled = true)
        assertFalse(filter.shouldStore(
            sample(
                packageName = "com.tencent.mobileqq",
                title = "教务处通知",
                text = "请查看验证码 123456",
                source = NotificationSource.QQ,
            ),
            enabled,
        ))
        assertFalse(filter.shouldStore(
            sample(
                packageName = "com.tencent.mobileqq",
                title = "班级通知",
                text = "微信支付成功，请查看账单",
                source = NotificationSource.QQ,
            ),
            enabled,
        ))
    }

    private fun sample(
        packageName: String = "com.tencent.mm",
        title: String? = "高数班群",
        text: String? = "请周五前提交实验报告",
        isGroupSummary: Boolean = false,
        conversationTitle: String? = null,
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
        conversationTitle = conversationTitle,
        category = null,
        postTime = 1L,
        isOngoing = false,
        isClearable = true,
        isGroupSummary = isGroupSummary,
        source = source,
    )
}

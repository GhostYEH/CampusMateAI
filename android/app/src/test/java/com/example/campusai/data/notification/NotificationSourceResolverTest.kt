package com.example.campusai.data.notification

import org.junit.Assert.assertEquals
import org.junit.Test

class NotificationSourceResolverTest {
    @Test
    fun `resolves supported application packages`() {
        assertEquals(NotificationSource.WECHAT, NotificationSourceResolver.resolve("com.tencent.mm"))
        assertEquals(NotificationSource.XUEXITONG, NotificationSourceResolver.resolve("com.chaoxing.mobile"))
        assertEquals(NotificationSource.QQ, NotificationSourceResolver.resolve("com.tencent.mobileqq"))
        assertEquals(NotificationSource.QQ, NotificationSourceResolver.resolve("com.tencent.qqlite"))
        assertEquals(NotificationSource.QQ, NotificationSourceResolver.resolve("com.tencent.tim"))
        assertEquals(NotificationSource.OTHER, NotificationSourceResolver.resolve("com.example.unknown"))
    }
}

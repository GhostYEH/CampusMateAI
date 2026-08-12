package com.example.campusai.data.notification

object NotificationSourceResolver {
    private const val WECHAT_PACKAGE = "com.tencent.mm"
    private const val WECOM_PACKAGE = "com.tencent.wework"
    private const val XUEXITONG_PACKAGE = "com.chaoxing.mobile"
    private val QQ_PACKAGES = setOf("com.tencent.mobileqq", "com.tencent.qqlite", "com.tencent.tim")

    fun resolve(packageName: String): NotificationSource = when {
        packageName == WECHAT_PACKAGE -> NotificationSource.WECHAT
        packageName == WECOM_PACKAGE -> NotificationSource.WECOM
        packageName == XUEXITONG_PACKAGE -> NotificationSource.XUEXITONG
        packageName in QQ_PACKAGES -> NotificationSource.QQ
        else -> NotificationSource.OTHER
    }
}

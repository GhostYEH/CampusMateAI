package com.example.campusai.data.notification

object NotificationSourceResolver {
    private const val WECHAT_PACKAGE = "com.tencent.mm"
    private const val XUEXITONG_PACKAGE = "com.chaoxing.mobile"
    private const val QQ_PACKAGE = "com.tencent.mobileqq"

    fun resolve(packageName: String): NotificationSource = when (packageName) {
        WECHAT_PACKAGE -> NotificationSource.WECHAT
        XUEXITONG_PACKAGE -> NotificationSource.XUEXITONG
        QQ_PACKAGE -> NotificationSource.QQ
        else -> NotificationSource.OTHER
    }
}

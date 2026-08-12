package com.example.campusai.data.notification

enum class NotificationSource(val displayName: String) {
    WECHAT("微信"),
    WECOM("企业微信"),
    XUEXITONG("学习通"),
    QQ("QQ"),
    OTHER("其他应用"),
}

data class NotificationSourceSettings(
    val wechatEnabled: Boolean = true,
    val wecomEnabled: Boolean = true,
    val xuexitongEnabled: Boolean = true,
    val qqEnabled: Boolean = true,
    val otherEnabled: Boolean = false,
) {
    fun isEnabled(source: NotificationSource): Boolean = when (source) {
        NotificationSource.WECHAT -> wechatEnabled
        NotificationSource.WECOM -> wecomEnabled
        NotificationSource.XUEXITONG -> xuexitongEnabled
        NotificationSource.QQ -> qqEnabled
        NotificationSource.OTHER -> otherEnabled
    }

    fun withEnabled(source: NotificationSource, enabled: Boolean): NotificationSourceSettings = when (source) {
        NotificationSource.WECHAT -> copy(wechatEnabled = enabled)
        NotificationSource.WECOM -> copy(wecomEnabled = enabled)
        NotificationSource.XUEXITONG -> copy(xuexitongEnabled = enabled)
        NotificationSource.QQ -> copy(qqEnabled = enabled)
        NotificationSource.OTHER -> copy(otherEnabled = enabled)
    }
}

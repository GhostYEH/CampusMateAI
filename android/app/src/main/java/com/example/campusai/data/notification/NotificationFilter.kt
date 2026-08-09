package com.example.campusai.data.notification

class NotificationFilter(private val campusMatePackage: String) {
    fun shouldStore(
        notification: CapturedNotification,
        settings: NotificationSourceSettings,
    ): Boolean {
        if (notification.packageName == campusMatePackage || notification.isGroupSummary) return false
        if (!settings.isEnabled(notification.source)) return false

        return listOf(
            notification.title,
            notification.text,
            notification.bigText,
            notification.subText,
            notification.summaryText,
            notification.conversationTitle,
        ).any { NotificationTextSanitizer.clean(it) != null }
    }
}

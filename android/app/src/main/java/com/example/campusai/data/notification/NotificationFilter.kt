package com.example.campusai.data.notification

class NotificationFilter(private val campusMatePackage: String) {
    fun shouldStore(
        notification: CapturedNotification,
        settings: NotificationSourceSettings,
    ): Boolean {
        if (notification.packageName == campusMatePackage || notification.isGroupSummary) return false
        if (!settings.isEnabled(notification.source)) return false

        val primaryText = NotificationTextSanitizer.primaryText(notification.bigText, notification.text)
        if (NotificationTextSanitizer.clean(primaryText) == null) return false

        return !NotificationContentClassifier.isLikelyNonTask(primaryText)
    }

    fun classifyReason(notification: CapturedNotification): String {
        val primaryText = NotificationTextSanitizer.primaryText(notification.bigText, notification.text)
        return when (val result = NotificationContentClassifier.classify(primaryText)) {
            is Classification.ACCEPT -> "ACCEPT: ${result.reason}"
            is Classification.IGNORE -> "IGNORE: ${result.reason}"
        }
    }
}

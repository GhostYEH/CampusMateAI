package com.example.campusai.data.notification

class NotificationFilter(private val campusMatePackage: String) {
    fun shouldStore(
        notification: CapturedNotification,
        settings: NotificationSourceSettings,
        wechatWhitelist: Set<String> = emptySet(),
        wecomWhitelist: Set<String> = emptySet(),
        qqWhitelist: Set<String> = emptySet(),
    ): Boolean {
        if (notification.packageName == campusMatePackage || notification.isGroupSummary) return false
        if (!settings.isEnabled(notification.source)) return false

        val sourceWhitelist = when (notification.source) {
            NotificationSource.WECHAT -> wechatWhitelist
            NotificationSource.WECOM -> wecomWhitelist
            NotificationSource.QQ -> qqWhitelist
            else -> null
        }
        if (sourceWhitelist != null && GroupIdentityResolver.matchingGroup(notification, sourceWhitelist) == null) return false

        val primaryText = NotificationTextSanitizer.primaryText(notification.bigText, notification.text)
        if (NotificationTextSanitizer.clean(primaryText) == null) return false
        if (NotificationContentClassifier.isHardExcluded(primaryText)) return false

        val bodyResult = NotificationContentClassifier.classify(primaryText)
        if (bodyResult.type != NotificationContentType.CHAT) return true
        val heading = GroupIdentityResolver.candidates(notification).joinToString("\n")
        val headingResult = NotificationContentClassifier.classify(heading)
        return headingResult.type == NotificationContentType.NOTICE &&
            NotificationContentClassifier.hasActionSignal(primaryText)
    }

    fun classifyReason(notification: CapturedNotification): String {
        val primaryText = NotificationTextSanitizer.primaryText(notification.bigText, notification.text)
        val result = NotificationContentClassifier.classify(primaryText)
        return "${result.type}: ${result.reason}"
    }
}

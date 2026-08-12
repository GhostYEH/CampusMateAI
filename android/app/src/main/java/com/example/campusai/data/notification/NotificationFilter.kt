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

        if (notification.source == NotificationSource.WECHAT) {
            if (wechatWhitelist.isEmpty()) return false
            val candidateGroup = notification.conversationTitle ?: notification.title
            if (candidateGroup == null || candidateGroup !in wechatWhitelist) return false
        }

        if (notification.source == NotificationSource.WECOM) {
            if (wecomWhitelist.isEmpty()) return false
            val candidateGroup = notification.conversationTitle ?: notification.title
            if (candidateGroup == null || candidateGroup !in wecomWhitelist) return false
        }

        if (notification.source == NotificationSource.QQ) {
            if (qqWhitelist.isEmpty()) return false
            val candidateGroup = notification.conversationTitle ?: notification.title
            if (candidateGroup == null || candidateGroup !in qqWhitelist) return false
        }

        val primaryText = NotificationTextSanitizer.primaryText(notification.bigText, notification.text)
        if (NotificationTextSanitizer.clean(primaryText) == null) return false
        if (NotificationContentClassifier.isHardExcluded(primaryText)) return false

        if (!NotificationContentClassifier.isLikelyNonTask(primaryText)) return true

        val heading = listOfNotNull(notification.conversationTitle, notification.title)
            .distinct()
            .joinToString("\n")
        return !NotificationContentClassifier.isLikelyNonTask(heading) &&
            NotificationContentClassifier.hasActionSignal(primaryText)
    }

    fun classifyReason(notification: CapturedNotification): String {
        val primaryText = NotificationTextSanitizer.primaryText(notification.bigText, notification.text)
        return when (val result = NotificationContentClassifier.classify(primaryText)) {
            is Classification.ACCEPT -> "ACCEPT: ${result.reason}"
            is Classification.IGNORE -> "IGNORE: ${result.reason}"
        }
    }
}

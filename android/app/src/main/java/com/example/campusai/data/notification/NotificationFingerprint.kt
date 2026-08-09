package com.example.campusai.data.notification

import java.security.MessageDigest

object NotificationFingerprint {
    fun create(notification: CapturedNotification): String {
        val primaryText = NotificationTextSanitizer.primaryText(notification.bigText, notification.text).orEmpty()
        val identity = listOf(
            notification.packageName,
            notification.notificationKey,
            notification.notificationId.toString(),
            notification.tag.orEmpty(),
            notification.title.orEmpty(),
            primaryText,
            notification.conversationTitle.orEmpty(),
        ).joinToString(separator = "\u001F")
        return MessageDigest.getInstance("SHA-256")
            .digest(identity.toByteArray(Charsets.UTF_8))
            .joinToString(separator = "") { "%02x".format(it) }
    }
}

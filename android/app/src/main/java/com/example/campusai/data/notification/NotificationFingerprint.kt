package com.example.campusai.data.notification

import java.security.MessageDigest

object NotificationFingerprint {
    private const val DEDUP_WINDOW_MS = 10 * 60 * 1000L

    fun create(notification: CapturedNotification): String {
        val primaryText = NotificationTextSanitizer.primaryText(notification.bigText, notification.text).orEmpty()
        val identity = listOf(
            notification.packageName,
            notification.title.orEmpty(),
            primaryText,
            notification.conversationTitle.orEmpty(),
            (notification.postTime / DEDUP_WINDOW_MS).toString(),
        ).joinToString(separator = "\u001F")
        return MessageDigest.getInstance("SHA-256")
            .digest(identity.toByteArray(Charsets.UTF_8))
            .joinToString(separator = "") { "%02x".format(it) }
    }
}

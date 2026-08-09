package com.example.campusai.data.notification

import android.app.Notification
import android.content.Context
import android.service.notification.StatusBarNotification

class NotificationNormalizer(private val context: Context) {
    fun normalize(statusBarNotification: StatusBarNotification): CapturedNotification? {
        val notification = statusBarNotification.notification ?: return null
        val extras = notification.extras ?: return null

        return CapturedNotification(
            notificationKey = statusBarNotification.key.orEmpty(),
            packageName = statusBarNotification.packageName.orEmpty(),
            notificationId = statusBarNotification.id,
            tag = NotificationTextSanitizer.clean(statusBarNotification.tag),
            appName = appNameFor(statusBarNotification.packageName),
            title = NotificationTextSanitizer.clean(extras.getCharSequence(Notification.EXTRA_TITLE)),
            text = NotificationTextSanitizer.clean(extras.getCharSequence(Notification.EXTRA_TEXT)),
            bigText = NotificationTextSanitizer.clean(extras.getCharSequence(Notification.EXTRA_BIG_TEXT)),
            subText = NotificationTextSanitizer.clean(extras.getCharSequence(Notification.EXTRA_SUB_TEXT)),
            summaryText = NotificationTextSanitizer.clean(extras.getCharSequence(Notification.EXTRA_SUMMARY_TEXT)),
            conversationTitle = NotificationTextSanitizer.clean(
                extras.getCharSequence(Notification.EXTRA_CONVERSATION_TITLE),
            ),
            category = notification.category,
            postTime = statusBarNotification.postTime,
            isOngoing = notification.flags and Notification.FLAG_ONGOING_EVENT != 0,
            isClearable = statusBarNotification.isClearable,
            isGroupSummary = notification.flags and Notification.FLAG_GROUP_SUMMARY != 0,
            source = NotificationSourceResolver.resolve(statusBarNotification.packageName),
        )
    }

    private fun appNameFor(packageName: String): String? = runCatching {
        context.packageManager.getApplicationLabel(
            context.packageManager.getApplicationInfo(packageName, 0),
        ).toString()
    }.getOrNull()?.let(NotificationTextSanitizer::clean)
}

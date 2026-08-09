package com.example.campusai.data.notification

data class CapturedNotification(
    val notificationKey: String,
    val packageName: String,
    val notificationId: Int,
    val tag: String?,
    val appName: String?,
    val title: String?,
    val text: String?,
    val bigText: String?,
    val subText: String?,
    val summaryText: String?,
    val conversationTitle: String?,
    val category: String?,
    val postTime: Long,
    val isOngoing: Boolean,
    val isClearable: Boolean,
    val isGroupSummary: Boolean,
    val source: NotificationSource,
)

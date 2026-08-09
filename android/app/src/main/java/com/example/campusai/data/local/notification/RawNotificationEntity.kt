package com.example.campusai.data.local.notification

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "raw_notifications",
    indices = [Index(value = ["fingerprint"], unique = true)],
)
data class RawNotificationEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val notificationKey: String,
    val fingerprint: String,
    val packageName: String,
    val source: String,
    val appName: String?,
    val title: String?,
    val text: String?,
    val bigText: String?,
    val subText: String?,
    val summaryText: String?,
    val conversationTitle: String?,
    val category: String?,
    val postTime: Long,
    val capturedAt: Long,
    val isOngoing: Boolean,
    val isClearable: Boolean,
    val processingState: String = "READY_FOR_REVIEW",
)

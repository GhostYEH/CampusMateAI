package com.example.campusai.data.repository

import android.app.Application
import android.content.Intent
import android.provider.Settings
import androidx.core.app.NotificationManagerCompat
import com.example.campusai.data.local.AppDataStore
import com.example.campusai.data.local.notification.CampusMateDatabase
import com.example.campusai.data.local.notification.RawNotificationEntity
import com.example.campusai.data.notification.CapturedNotification
import com.example.campusai.data.notification.NotificationFilter
import com.example.campusai.data.notification.NotificationFingerprint
import com.example.campusai.data.notification.NotificationSource
import com.example.campusai.data.notification.NotificationSourceSettings
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

data class InboxNotification(
    val id: Long,
    val source: NotificationSource,
    val appName: String?,
    val title: String?,
    val text: String?,
    val bigText: String?,
    val conversationTitle: String?,
    val postTime: Long,
    val capturedAt: Long,
)

class NotificationInboxRepository(application: Application) {
    private val app = application
    private val dataStore = AppDataStore(application)
    private val dao = CampusMateDatabase.create(application).rawNotificationDao()
    private val filter = NotificationFilter(application.packageName)

    fun observeRecentNotifications(limit: Int = DEFAULT_INBOX_LIMIT): Flow<List<InboxNotification>> =
        dao.observeRecent(limit.coerceIn(1, MAX_INBOX_LIMIT)).map { entities ->
            entities.map(::toInboxNotification)
        }

    fun observeSourceSettings(): Flow<NotificationSourceSettings> = dataStore.notificationSourceSettings

    suspend fun setNotificationSourceEnabled(source: NotificationSource, enabled: Boolean) {
        dataStore.setNotificationSourceEnabled(source, enabled)
    }

    suspend fun capture(notification: CapturedNotification): Boolean {
        val settings = dataStore.notificationSourceSettings.first()
        if (!filter.shouldStore(notification, settings)) return false

        val entity = RawNotificationEntity(
            notificationKey = notification.notificationKey,
            fingerprint = NotificationFingerprint.create(notification),
            packageName = notification.packageName,
            source = notification.source.name,
            appName = notification.appName,
            title = notification.title,
            text = notification.text,
            bigText = notification.bigText,
            subText = notification.subText,
            summaryText = notification.summaryText,
            conversationTitle = notification.conversationTitle,
            category = notification.category,
            postTime = notification.postTime,
            capturedAt = System.currentTimeMillis(),
            isOngoing = notification.isOngoing,
            isClearable = notification.isClearable,
        )
        return dao.insertIgnore(entity) != -1L
    }

    suspend fun deleteNotification(id: Long) {
        dao.deleteById(id)
    }

    suspend fun clearInbox() {
        dao.clear()
    }

    fun isNotificationAccessGranted(): Boolean =
        NotificationManagerCompat.getEnabledListenerPackages(app).contains(app.packageName)

    fun createNotificationAccessSettingsIntent(): Intent =
        Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

    private fun toInboxNotification(entity: RawNotificationEntity): InboxNotification = InboxNotification(
        id = entity.id,
        source = runCatching { NotificationSource.valueOf(entity.source) }.getOrDefault(NotificationSource.OTHER),
        appName = entity.appName,
        title = entity.title,
        text = entity.text,
        bigText = entity.bigText,
        conversationTitle = entity.conversationTitle,
        postTime = entity.postTime,
        capturedAt = entity.capturedAt,
    )

    private companion object {
        const val DEFAULT_INBOX_LIMIT = 50
        const val MAX_INBOX_LIMIT = 200
    }
}

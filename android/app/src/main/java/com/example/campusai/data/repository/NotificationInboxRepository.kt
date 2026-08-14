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
import com.example.campusai.data.notification.NotificationTextSanitizer
import com.example.campusai.data.notification.GroupIdentityResolver
import com.example.campusai.data.notification.QueuedNotification
import com.example.campusai.data.notification.ConversationBundler
import com.example.campusai.data.local.notification.NotificationProcessingState
import com.example.campusai.workers.NoticeWorkScheduler
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
        val whitelist = dataStore.monitoredGroupChats.first()
        val wecomWhitelist = dataStore.wecomGroupChats.first()
        val qqWhitelist = dataStore.qqGroupChats.first()
        if (!filter.shouldStore(notification, settings, whitelist, wecomWhitelist, qqWhitelist)) return false

        val sourceWhitelist = when (notification.source) {
            NotificationSource.WECHAT -> whitelist
            NotificationSource.WECOM -> wecomWhitelist
            NotificationSource.QQ -> qqWhitelist
            else -> emptySet()
        }
        val normalizedGroup = GroupIdentityResolver.matchingGroup(notification, sourceWhitelist)
            ?: notification.conversationTitle
            ?: notification.title
            ?: notification.appName
            ?: notification.source.displayName
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
            conversationTitle = normalizedGroup,
            category = notification.category,
            postTime = notification.postTime,
            capturedAt = System.currentTimeMillis(),
            isOngoing = notification.isOngoing,
            isClearable = notification.isClearable,
        )
        val inserted = dao.insertIgnore(entity) != -1L
        if (inserted) NoticeWorkScheduler.scheduleDebounced(app)
        return inserted
    }

    suspend fun claimBundles(limit: Int = MAX_CLAIM_ROWS): List<com.example.campusai.data.notification.ConversationBundle> {
        val now = System.currentTimeMillis()
        dao.recoverStaleProcessing(now - STALE_PROCESSING_MS, now)
        return ConversationBundler.bundle(dao.claimPending(limit, now).mapNotNull { entity ->
            val text = NotificationTextSanitizer.primaryText(entity.bigText, entity.text) ?: return@mapNotNull null
            QueuedNotification(
                id = entity.id,
                fingerprint = entity.fingerprint,
                source = runCatching { NotificationSource.valueOf(entity.source) }.getOrDefault(NotificationSource.OTHER),
                normalizedGroupName = entity.conversationTitle ?: entity.title ?: entity.source,
                text = text,
                publishedAt = entity.postTime,
                attemptCount = entity.attemptCount,
            )
        })
    }

    suspend fun updateBundleState(ids: List<Long>, state: String, incrementAttempt: Boolean = false) {
        if (ids.isNotEmpty()) dao.updateState(ids, state, if (incrementAttempt) 1 else 0, System.currentTimeMillis())
    }

    suspend fun hasPending(): Boolean = dao.pendingCount() > 0

    suspend fun cleanup() {
        val now = System.currentTimeMillis()
        dao.deleteCompletedBefore(now - COMPLETED_RETENTION_MS)
        dao.deleteFailedBefore(now - FAILED_RETENTION_MS)
        dao.trimTerminalHistory(MAX_HISTORY_ROWS)
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
        // The backend accepts at most 20 batch items. A claimed row can produce at
        // most one bundle, so this also bounds every upload request to that limit.
        const val MAX_CLAIM_ROWS = 20
        const val STALE_PROCESSING_MS = 15 * 60 * 1000L
        const val COMPLETED_RETENTION_MS = 14 * 24 * 60 * 60 * 1000L
        const val FAILED_RETENTION_MS = 30 * 24 * 60 * 60 * 1000L
        const val MAX_HISTORY_ROWS = 500
    }
}

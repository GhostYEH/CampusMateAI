package com.example.campusai.data.notification

import android.content.ComponentName
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import com.example.campusai.CampusAIApplication
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import java.time.Instant

class CampusNotificationListenerService : NotificationListenerService() {
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val normalizer by lazy { NotificationNormalizer(applicationContext) }

    override fun onListenerConnected() {
        super.onListenerConnected()
    }

    override fun onNotificationPosted(statusBarNotification: StatusBarNotification?) {
        super.onNotificationPosted(statusBarNotification)
        val captured = statusBarNotification?.let(normalizer::normalize) ?: return
        val inboxRepository = (application as? CampusAIApplication)?.notificationInboxRepository ?: return
        val appRepository = (application as? CampusAIApplication)?.repository ?: return

        serviceScope.launch {
            runCatching {
                // Local persistence and the fingerprint form the first idempotency
                // boundary. Only a newly stored, allow-listed campus notification
                // is sent to the shared backend for extraction and task creation.
                if (!inboxRepository.capture(captured)) return@runCatching

                val content = NotificationTextSanitizer
                    .primaryText(captured.bigText, captured.text)
                    ?: return@runCatching
                val sourceName = captured.conversationTitle
                    ?: captured.title
                    ?: captured.appName
                    ?: captured.source.displayName
                appRepository.enqueueNoticeIngestion(
                    content = content,
                    sourceName = sourceName,
                    publishedAt = Instant.ofEpochMilli(captured.postTime).toString(),
                )
            }
                .onFailure { Log.w(TAG, "Notification capture failed", it) }
        }
    }

    override fun onListenerDisconnected() {
        super.onListenerDisconnected()
        requestRebind(ComponentName(this, CampusNotificationListenerService::class.java))
    }

    override fun onDestroy() {
        serviceScope.cancel()
        super.onDestroy()
    }

    private companion object {
        const val TAG = "CampusNotification"
    }
}

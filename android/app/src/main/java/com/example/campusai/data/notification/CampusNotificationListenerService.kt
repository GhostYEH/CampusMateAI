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

        serviceScope.launch {
            runCatching { inboxRepository.capture(captured) }
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

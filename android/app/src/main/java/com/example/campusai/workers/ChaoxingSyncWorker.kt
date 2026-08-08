package com.example.campusai.workers

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import androidx.work.ListenableWorker
import com.example.campusai.CampusAIApplication
import com.example.campusai.R
import kotlinx.coroutines.flow.first

class ChaoxingSyncWorker(
    private val appContext: Context,
    workerParams: WorkerParameters
): CoroutineWorker(appContext, workerParams) {

    override suspend fun doWork(): ListenableWorker.Result {
        val repository = (appContext.applicationContext as CampusAIApplication).repository
        val stateStore = ChaoxingSyncStateStore(appContext)

        val isConnected = stateStore.isConnected.first()
        if (!isConnected) {
            return ListenableWorker.Result.success() // Or failure, but success avoids retries for disconnected state
        }

        val result = repository.syncChaoxing()
        
        return if (result.first) {
            stateStore.setReauthRequired(false)
            stateStore.setLastSyncedAt(System.currentTimeMillis().toString())
            repository.refreshCourses()
            repository.refreshTasks()
            repository.refreshNotices()
            ListenableWorker.Result.success()
        } else {
            if (result.second == "reauth_required") {
                stateStore.setReauthRequired(true)
                showReauthNotification()
                // Do not retry endlessly if reauth is required
                ListenableWorker.Result.failure()
            } else {
                // Network or other error, retry with exponential backoff (handled by WorkManager default backoff)
                ListenableWorker.Result.retry()
            }
        }
    }

    private fun showReauthNotification() {
        val notificationManager = appContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channelId = "chaoxing_sync_channel"
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                "Chaoxing Sync",
                NotificationManager.IMPORTANCE_DEFAULT
            )
            notificationManager.createNotificationChannel(channel)
        }

        val notification = NotificationCompat.Builder(appContext, channelId)
            .setSmallIcon(android.R.drawable.ic_dialog_alert) // using default icon for simplicity, could be R.drawable.ic_launcher_foreground
            .setContentTitle("CampusMate")
            .setContentText("学习通登录已失效，请重新连接")
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setAutoCancel(true)
            .build()

        notificationManager.notify(1001, notification)
    }
}

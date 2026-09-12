package com.example.campusai.work

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf

/**
 * Agent 提醒 Worker。
 *
 * 使用 WorkManager unique work：key 包含 campaign/item/reminder 或 workflow/action，
 * 重组或重试不会重复创建提醒。
 */
class AgentReminderWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val title = inputData.getString(KEY_TITLE) ?: "校园提醒"
        val message = inputData.getString(KEY_MESSAGE) ?: ""
        val deepLink = inputData.getString(KEY_DEEP_LINK)
        val channelId = ensureChannel(applicationContext)
        val intent = Intent().apply {
            action = Intent.ACTION_VIEW
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            deepLink?.let { putExtra("deep_link", it) }
        }
        val pendingIntent = PendingIntent.getActivity(
            applicationContext,
            0,
            intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val notification = NotificationCompat.Builder(applicationContext, channelId)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText(message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(message))
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()
        val manager = applicationContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        runCatching { manager.notify(notificationId(), notification) }
        return Result.success()
    }

    private fun notificationId(): Int = (id.hashCode() and 0x7FFFFFFF)

    companion object {
        const val KEY_TITLE = "title"
        const val KEY_MESSAGE = "message"
        const val KEY_DEEP_LINK = "deep_link"
        private const val CHANNEL_ID = "agent_reminders"

        fun uniqueWorkKey(scope: String, identifier: String, reminder: String): String =
            "agent_reminder:$scope:$identifier:$reminder"

        fun scheduleFinalReviewReminder(
            context: Context,
            campaignId: String,
            itemId: String,
            title: String,
            message: String,
            delayMillis: Long = 0,
        ) {
            val key = uniqueWorkKey("campaign", campaignId, "item:$itemId:reminder")
            val data = workDataOf(
                KEY_TITLE to title,
                KEY_MESSAGE to message,
                KEY_DEEP_LINK to "final_review://campaign/$campaignId/item/$itemId",
            )
            enqueueUnique(context, key, data, delayMillis)
        }

        fun scheduleNoticeWorkflowReminder(
            context: Context,
            workflowId: String,
            actionId: String,
            title: String,
            message: String,
            delayMillis: Long = 0,
        ) {
            val key = uniqueWorkKey("workflow", workflowId, "action:$actionId")
            val data = workDataOf(
                KEY_TITLE to title,
                KEY_MESSAGE to message,
                KEY_DEEP_LINK to "notice_workflow://workflow/$workflowId/action/$actionId",
            )
            enqueueUnique(context, key, data, delayMillis)
        }

        private fun enqueueUnique(context: Context, key: String, data: Data, delayMillis: Long) {
            val request = OneTimeWorkRequestBuilder<AgentReminderWorker>()
                .setInputData(data)
                .apply { if (delayMillis > 0) setInitialDelay(delayMillis, java.util.concurrent.TimeUnit.MILLISECONDS) }
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(
                key,
                ExistingWorkPolicy.KEEP,
                request,
            )
        }

        private fun ensureChannel(context: Context): String {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                if (manager.getNotificationChannel(CHANNEL_ID) == null) {
                    val channel = NotificationChannel(
                        CHANNEL_ID,
                        "Agent 提醒",
                        NotificationManager.IMPORTANCE_DEFAULT,
                    ).apply { description = "复习、研究和通知事务提醒" }
                    manager.createNotificationChannel(channel)
                }
            }
            return CHANNEL_ID
        }
    }
}
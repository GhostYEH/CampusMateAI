package com.example.campusai.workers

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import com.example.campusai.data.notification.ConversationBundler
import java.util.concurrent.TimeUnit

object NoticeWorkScheduler {
    private const val DEBOUNCE_WORK = "notice-debounce"
    private const val MAX_AGE_WORK = "notice-max-age"
    private const val UPLOAD_WORK = "notice-upload"

    fun scheduleDebounced(context: Context) {
        val request = OneTimeWorkRequestBuilder<NoticeDebounceWorker>()
            .setInitialDelay(ConversationBundler.BATCH_QUIET_WINDOW_MS, TimeUnit.MILLISECONDS)
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork(DEBOUNCE_WORK, ExistingWorkPolicy.REPLACE, request)
        val maxAgeRequest = OneTimeWorkRequestBuilder<NoticeDebounceWorker>()
            .setInitialDelay(ConversationBundler.BATCH_MAX_AGE_MS, TimeUnit.MILLISECONDS)
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork(MAX_AGE_WORK, ExistingWorkPolicy.KEEP, maxAgeRequest)
    }

    fun scheduleUpload(context: Context) {
        val request = OneTimeWorkRequestBuilder<NoticeUploadWorker>()
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork(UPLOAD_WORK, ExistingWorkPolicy.APPEND_OR_REPLACE, request)
    }
}

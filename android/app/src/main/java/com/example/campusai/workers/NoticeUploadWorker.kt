package com.example.campusai.workers

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.example.campusai.data.repository.AppRepository

class NoticeUploadWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val repository = AppRepository(applicationContext as android.app.Application)
        val pendingNotices = repository.getPendingNotices().filter { it.status == "pending" }
        
        if (pendingNotices.isEmpty()) {
            return Result.success()
        }

        val updatedNotices = mutableListOf<com.example.campusai.data.model.PendingNotice>()
        var hasFailures = false

        for (notice in pendingNotices) {
            val success = repository.ingestNoticeDirectly(notice)
            if (success) {
                updatedNotices.add(notice.copy(status = "completed"))
            } else {
                hasFailures = true
                val retryCount = notice.retryCount + 1
                val status = if (retryCount >= 50) "failed" else "pending"
                updatedNotices.add(notice.copy(retryCount = retryCount, status = status))
            }
        }

        // Just update status instead of replacing the whole list
        (applicationContext as? com.example.campusai.CampusAIApplication)?.let {
            val dataStore = com.example.campusai.data.local.AppDataStore(it)
            dataStore.updateNoticeStatus(updatedNotices)
        } ?: run {
            // Fallback if application context is not castable
            val dataStore = com.example.campusai.data.local.AppDataStore(applicationContext)
            dataStore.updateNoticeStatus(updatedNotices)
        }

        return if (hasFailures) {
            Result.retry()
        } else {
            Result.success()
        }
    }
}
package com.example.campusai.workers

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters

class NoticeDebounceWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        NoticeWorkScheduler.scheduleUpload(applicationContext)
        return Result.success()
    }
}

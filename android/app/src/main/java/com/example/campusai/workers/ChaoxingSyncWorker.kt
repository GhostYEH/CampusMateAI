package com.example.campusai.workers

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import androidx.work.ListenableWorker
import com.example.campusai.CampusAIApplication

class ChaoxingSyncWorker(
    private val appContext: Context,
    workerParams: WorkerParameters
): CoroutineWorker(appContext, workerParams) {

    override suspend fun doWork(): ListenableWorker.Result {
        val repository = (appContext.applicationContext as CampusAIApplication).repository
        repository.syncChaoxing()
        return ListenableWorker.Result.success()
    }
}

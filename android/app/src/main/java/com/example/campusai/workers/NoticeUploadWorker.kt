package com.example.campusai.workers

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.example.campusai.CampusAIApplication
import com.example.campusai.data.local.notification.NotificationProcessingState
import com.example.campusai.data.remote.ApiClient
import com.example.campusai.data.remote.NoticeBatchIngestRequest
import com.example.campusai.data.remote.NoticeBatchItemRequest
import com.example.campusai.data.remote.NoticeBatchMessageRequest
import java.io.IOException
import java.time.Instant

class NoticeUploadWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val application = applicationContext as? CampusAIApplication ?: return Result.failure()
        val inbox = application.notificationInboxRepository
        var drained = 0
        while (drained < MAX_BUNDLES_PER_RUN) {
            val bundles = inbox.claimBundles()
            if (bundles.isEmpty()) break
            drained += bundles.size
            val request = NoticeBatchIngestRequest(bundles.map { bundle ->
                NoticeBatchItemRequest(
                    client_id = bundle.clientId,
                    client_fingerprint = bundle.clientFingerprint,
                    source_name = bundle.normalizedGroupName,
                    published_at = bundle.messages.minOfOrNull { Instant.ofEpochMilli(it.publishedAt).toString() },
                    messages = bundle.messages.map {
                        NoticeBatchMessageRequest(it.text, Instant.ofEpochMilli(it.publishedAt).toString())
                    },
                )
            })
            val response = try {
                ApiClient.api.ingestNoticeBatch(request)
            } catch (_: IOException) {
                return handleTransportFailure(inbox, bundles)
            } catch (_: Exception) {
                return handleTransportFailure(inbox, bundles)
            }
            if (!response.isSuccessful) {
                val retryable = response.code() >= 500 || response.code() == 408 || response.code() == 429
                var shouldRetry = false
                bundles.forEach { bundle ->
                    val state = if (retryable && bundle.maxAttemptCount + 1 < MAX_ATTEMPTS) {
                        shouldRetry = true
                        NotificationProcessingState.RETRY
                    } else NotificationProcessingState.FAILED
                    inbox.updateBundleState(bundle.notificationIds, state, true)
                }
                return if (shouldRetry) Result.retry() else Result.failure()
            }
            val byFingerprint = response.body()?.items.orEmpty().associateBy { it.client_fingerprint }
            var batchNeedsRetry = false
            bundles.forEach { bundle ->
                val result = byFingerprint[bundle.clientFingerprint]
                val state = when (result?.status) {
                    "completed" -> NotificationProcessingState.COMPLETED
                    "ignored" -> NotificationProcessingState.IGNORED
                    "failed" -> NotificationProcessingState.FAILED
                    else -> if (bundle.maxAttemptCount + 1 >= MAX_ATTEMPTS) {
                        NotificationProcessingState.FAILED
                    } else NotificationProcessingState.RETRY
                }
                if (state == NotificationProcessingState.RETRY) batchNeedsRetry = true
                inbox.updateBundleState(bundle.notificationIds, state, state == NotificationProcessingState.RETRY)
            }
            if (batchNeedsRetry) return Result.retry()
        }
        inbox.cleanup()
        if (inbox.hasPending()) NoticeWorkScheduler.scheduleUpload(applicationContext)
        return Result.success()
    }

    private companion object {
        const val MAX_BUNDLES_PER_RUN = 100
        const val MAX_ATTEMPTS = 8
    }

    private suspend fun handleTransportFailure(
        inbox: com.example.campusai.data.repository.NotificationInboxRepository,
        bundles: List<com.example.campusai.data.notification.ConversationBundle>,
    ): Result {
        var retryable = false
        bundles.forEach { bundle ->
            val state = if (bundle.maxAttemptCount + 1 >= MAX_ATTEMPTS) {
                NotificationProcessingState.FAILED
            } else {
                retryable = true
                NotificationProcessingState.RETRY
            }
            inbox.updateBundleState(bundle.notificationIds, state, true)
        }
        return if (retryable) Result.retry() else Result.failure()
    }
}

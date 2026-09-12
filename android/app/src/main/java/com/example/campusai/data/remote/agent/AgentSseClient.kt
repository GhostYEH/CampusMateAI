package com.example.campusai.data.remote.agent

import com.example.campusai.BuildConfig
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.channels.ProducerScope
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.channelFlow
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.math.min

/**
 * Agent Runtime SSE 客户端。
 *
 * - 使用 Bearer header 鉴权，禁止 token query。
 * - 附带 Last-Event-ID 以支持断点恢复。
 * - 按 sequence 去重，避免重连后重复处理事件。
 * - 断线指数退避重连。
 * - 401 时调用 token refresher 刷新后恢复。
 */
class AgentSseClient(
    private val baseUrl: String = BuildConfig.API_BASE_URL,
    private val tokenProvider: () -> String?,
    private val tokenRefresher: () -> String?,
    private val client: OkHttpClient,
) {
    @OptIn(ExperimentalCoroutinesApi::class, FlowPreview::class)
    fun streamRunEvents(
        runId: String,
        initialLastEventId: String? = null,
    ): Flow<SseEvent> = channelFlow {
        var lastEventId = initialLastEventId
        var maxSequence = -1L
        var attempt = 0

        while (!isClosedForSend) {
            val token = tokenProvider()
            val builder = Request.Builder()
                .url("${baseUrl}agent-runs/$runId/events/stream")
                .header("Accept", "text/event-stream")
            if (!token.isNullOrBlank()) builder.header("Authorization", "Bearer $token")
            if (!lastEventId.isNullOrBlank()) builder.header("Last-Event-ID", lastEventId)

            val request = builder.build()
            val result = runCatching {
                client.newCall(request).execute().use { response ->
                    when (response.code) {
                        401 -> SseConnectResult.AuthFailed
                        in 200..299 -> {
                            val source = response.body?.source()
                                ?: throw IOException("SSE 响应没有内容")
                            maxSequence = SseEventParser.parse(source, maxSequence) { event ->
                                lastEventId = event.id.ifBlank { lastEventId }
                                trySend(SseEvent.Event(event))
                            }
                            SseConnectResult.Closed
                        }
                        else -> throw IOException("SSE 连接失败 (${response.code})")
                    }
                }
            }

            when (val value = result.getOrNull()) {
                SseConnectResult.Closed -> {
                    attempt = 0
                    if (!isClosedForSend) backoff(attempt)
                }
                SseConnectResult.AuthFailed -> {
                    val refreshed = tokenRefresher()
                    if (refreshed.isNullOrBlank()) {
                        trySend(SseEvent.Error(IOException("鉴权失效且刷新失败")))
                        return@channelFlow
                    }
                    attempt = 0
                }
                null -> {
                    val cause = result.exceptionOrNull() ?: IOException("未知 SSE 错误")
                    trySend(SseEvent.Error(cause))
                    attempt++
                    if (attempt > MAX_ATTEMPTS) return@channelFlow
                    backoff(attempt)
                }
            }
        }
    }

    private suspend fun ProducerScope<SseEvent>.backoff(attempt: Int) {
        val delayMs = min(BASE_BACKOFF_MS * (1L shl (attempt - 1)), MAX_BACKOFF_MS)
        kotlinx.coroutines.delay(delayMs)
    }

    sealed interface SseConnectResult { data object Closed : SseConnectResult; data object AuthFailed : SseConnectResult }
    sealed interface SseEvent {
        data class Event(val event: AgentEventDto) : SseEvent
        data class Error(val cause: Throwable) : SseEvent
    }

    companion object {
        private const val MAX_ATTEMPTS = 6
        private const val BASE_BACKOFF_MS = 1000L
        private const val MAX_BACKOFF_MS = 30_000L

        fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(0, TimeUnit.MILLISECONDS)
            .build()
    }
}

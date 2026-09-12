package com.example.campusai.data.remote.agent

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okio.BufferedSource

/**
 * SSE 事件解析与去重工具。
 *
 * - 解析 SSE 文本流（id/event/data 行）为 AgentEventDto。
 * - 按 sequence 去重：只发射 sequence > maxSequence 的事件。
 */
object SseEventParser {
    private val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
    private val eventAdapter = moshi.adapter(AgentEventDto::class.java)

    /**
     * 解析 SSE 流，对每个去重后的事件调用 emit。
     * 返回处理过的最大 sequence。
     */
    fun parse(
        source: BufferedSource,
        initialMaxSequence: Long = -1L,
        emit: (AgentEventDto) -> Unit,
    ): Long {
        var maxSequence = initialMaxSequence
        var event = ""
        val data = StringBuilder()
        var eventId = ""
        while (!source.exhausted()) {
            val line = source.readUtf8Line() ?: break
            when {
                line.startsWith("id:") -> eventId = line.removePrefix("id:").trim()
                line.startsWith("event:") -> event = line.removePrefix("event:").trim()
                line.startsWith("data:") -> {
                    if (data.isNotEmpty()) data.append('\n')
                    data.append(line.removePrefix("data:").removePrefix(" "))
                }
                line.isEmpty() -> {
                    if (data.isNotEmpty()) {
                        val json = data.toString()
                        runCatching { eventAdapter.fromJson(json) }
                            .getOrNull()
                            ?.let { evt ->
                                val withId = if (evt.id.isBlank() && eventId.isNotBlank()) {
                                    evt.copy(id = eventId)
                                } else evt
                                if (withId.sequence > maxSequence) {
                                    maxSequence = withId.sequence
                                    emit(withId)
                                }
                            }
                    }
                    event = ""
                    data.clear()
                }
            }
        }
        return maxSequence
    }

    /**
     * 从已有事件列表计算 Last-Event-ID（最后一个事件的 id）。
     */
    fun lastEventId(events: List<AgentEventDto>): String? =
        events.lastOrNull()?.id?.takeIf { it.isNotBlank() }
}
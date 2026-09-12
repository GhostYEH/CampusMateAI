package com.example.campusai.data.remote.agent

import okio.Buffer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SseEventParserTest {

    private fun sseStream(events: List<String>): Buffer {
        val buffer = Buffer()
        events.forEach { buffer.writeUtf8(it); buffer.writeUtf8("\n") }
        return buffer
    }

    @Test
    fun `parses single event with id and data`() {
        val source = sseStream(listOf(
            "id:evt_001",
            """data:{"id":"evt_001","type":"RUN_STARTED","run_id":"run_1","sequence":1,"status":"RUNNING","phase":"CONTEXT_BUILDING","summary":"开始","created_at":""}""",
            "",
        ))
        val emitted = mutableListOf<AgentEventDto>()
        SseEventParser.parse(source, -1L) { emitted += it }
        assertEquals(1, emitted.size)
        assertEquals("evt_001", emitted[0].id)
        assertEquals(1L, emitted[0].sequence)
        assertEquals(AgentEventType.RUN_STARTED, emitted[0].eventType())
    }

    @Test
    fun `dedupes events by sequence on reconnect`() {
        val source = sseStream(listOf(
            """data:{"id":"evt_001","type":"RUN_STARTED","sequence":1,"status":"RUNNING","summary":"","created_at":""}""",
            "",
            """data:{"id":"evt_002","type":"MODEL_COMPLETED","sequence":2,"status":"RUNNING","summary":"","created_at":""}""",
            "",
            """data:{"id":"evt_003","type":"TOOL_COMPLETED","sequence":3,"status":"RUNNING","summary":"","created_at":""}""",
            "",
        ))
        val emitted = mutableListOf<AgentEventDto>()
        // 模拟重连：已有 maxSequence=1，只应收到 sequence 2 和 3
        val maxSeq = SseEventParser.parse(source, 1L) { emitted += it }
        assertEquals(2, emitted.size)
        assertEquals(2L, emitted[0].sequence)
        assertEquals(3L, emitted[1].sequence)
        assertEquals(3L, maxSeq)
    }

    @Test
    fun `skips duplicate sequence events`() {
        val source = sseStream(listOf(
            """data:{"id":"evt_005","type":"RUN_STARTED","sequence":5,"status":"RUNNING","summary":"","created_at":""}""",
            "",
            """data:{"id":"evt_005","type":"RUN_STARTED","sequence":5,"status":"RUNNING","summary":"","created_at":""}""",
            "",
            """data:{"id":"evt_006","type":"MODEL_COMPLETED","sequence":6,"status":"RUNNING","summary":"","created_at":""}""",
            "",
        ))
        val emitted = mutableListOf<AgentEventDto>()
        SseEventParser.parse(source, -1L) { emitted += it }
        assertEquals(2, emitted.size)
        assertEquals(5L, emitted[0].sequence)
        assertEquals(6L, emitted[1].sequence)
    }

    @Test
    fun `uses id field from SSE id line when data lacks id`() {
        val source = sseStream(listOf(
            "id:evt_from_id_line",
            """data:{"type":"RUN_STARTED","sequence":1,"status":"RUNNING","summary":"","created_at":""}""",
            "",
        ))
        val emitted = mutableListOf<AgentEventDto>()
        SseEventParser.parse(source, -1L) { emitted += it }
        assertEquals(1, emitted.size)
        assertEquals("evt_from_id_line", emitted[0].id)
    }

    @Test
    fun `lastEventId returns last event id`() {
        val events = listOf(
            AgentEventDto(id = "evt_001", sequence = 1),
            AgentEventDto(id = "evt_002", sequence = 2),
        )
        assertEquals("evt_002", SseEventParser.lastEventId(events))
    }

    @Test
    fun `lastEventId returns null for empty list`() {
        assertEquals(null, SseEventParser.lastEventId(emptyList()))
    }

    @Test
    fun `handles multi-line data`() {
        val source = sseStream(listOf(
            "id:evt_001",
            """data:{"id":"evt_001","type":"RUN_STARTED","sequence":1,"status":"RUNNING","summary":"line1""",
            """data: line2","created_at":""}""",
            "",
        ))
        val emitted = mutableListOf<AgentEventDto>()
        SseEventParser.parse(source, -1L) { emitted += it }
        assertEquals(1, emitted.size)
        assertTrue(emitted[0].summary.contains("line1"))
        assertTrue(emitted[0].summary.contains("line2"))
    }

    @Test
    fun `ignores malformed json without crashing`() {
        val source = sseStream(listOf(
            "data:not valid json",
            "",
            """data:{"id":"evt_002","type":"RUN_STARTED","sequence":2,"status":"RUNNING","summary":"","created_at":""}""",
            "",
        ))
        val emitted = mutableListOf<AgentEventDto>()
        SseEventParser.parse(source, -1L) { emitted += it }
        assertEquals(1, emitted.size)
        assertEquals("evt_002", emitted[0].id)
    }

    @Test
    fun `returns initial max sequence when stream is empty`() {
        val source = Buffer()
        val maxSeq = SseEventParser.parse(source, 5L) {}
        assertEquals(5L, maxSeq)
    }
}
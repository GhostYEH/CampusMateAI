package com.example.campusai.ui.screens.counselor

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CpmCounselorStateTest {
    @Test
    fun `submission enters chat and creates empty generating assistant bubble`() {
        val state = CpmCounselorStateReducer.submit(CpmCounselorUiState(), "  大一怎么规划  ", now = 12L)

        assertTrue(state.chatActive)
        assertTrue(state.sending)
        assertEquals("大一怎么规划", state.messages[0].content)
        assertEquals(CpmMessageStatus.COMPLETED, state.messages[0].status)
        assertEquals("", state.messages[1].content)
        assertEquals(CpmMessageStatus.GENERATING, state.messages[1].status)
    }

    @Test
    fun `chunks append to the same assistant message in order`() {
        val submitted = CpmCounselorStateReducer.submit(CpmCounselorUiState(), "问题", now = 20L)
        val id = submitted.messages.last().id

        val updated = CpmCounselorStateReducer.appendChunk(
            CpmCounselorStateReducer.appendChunk(submitted, id, "第一段"),
            id,
            "第二段",
        )

        assertEquals("第一段第二段", updated.messages.last().content)
        assertEquals(CpmMessageStatus.GENERATING, updated.messages.last().status)
    }

    @Test
    fun `completion exposes speech separately from the message stream`() {
        val submitted = CpmCounselorStateReducer.submit(CpmCounselorUiState(), "问题", now = 30L)
        val id = submitted.messages.last().id
        val chunked = CpmCounselorStateReducer.appendChunk(submitted, id, "完整回答")

        val completed = CpmCounselorStateReducer.complete(chunked, id)

        assertFalse(completed.sending)
        assertEquals(CpmMessageStatus.COMPLETED, completed.messages.last().status)
        assertEquals("完整回答", completed.speechText)
        assertEquals(1, completed.speechRequestId)
    }

    @Test
    fun `failure retains partial text and marks the existing bubble`() {
        val submitted = CpmCounselorStateReducer.submit(CpmCounselorUiState(), "问题", now = 40L)
        val id = submitted.messages.last().id
        val chunked = CpmCounselorStateReducer.appendChunk(submitted, id, "已经收到的内容")

        val failed = CpmCounselorStateReducer.fail(chunked, id, "网络异常")

        assertFalse(failed.sending)
        assertEquals("已经收到的内容", failed.messages.last().content)
        assertEquals("网络异常", failed.messages.last().errorMessage)
        assertEquals(CpmMessageStatus.ERROR, failed.messages.last().status)
    }
}


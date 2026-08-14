package com.example.campusai.data.remote

import org.junit.Assert.assertEquals
import org.junit.Test

class NoticeApiContractTest {
    @Test
    fun `manual extraction request matches backend schema`() {
        val request = NoticeExtractRequest(content = "请提交实验报告")
        assertEquals("请提交实验报告", request.content)
        assertEquals(null, request.published_at)
        assertEquals(null, request.source_name)
        assertEquals(true, request.allow_multi_task)
    }

    @Test
    fun `multi extraction response maps nested tasks to screen model`() {
        val response = MultiNoticeExtractResponseDto(
            tasks = listOf(
                NoticeExtractTaskDto(title = "实验报告", task = "提交实验报告", deadline = "2026-08-20T17:00:00+08:00", confidence = 0.9),
                NoticeExtractTaskDto(title = "班会", task = "参加班会", confidence = 0.8),
            ),
        )
        val mapped = response.toExtractResult()
        assertEquals("实验报告", mapped.title)
        assertEquals("2026-08-20T17:00:00+08:00", mapped.deadline)
        assertEquals(listOf("提交实验报告", "参加班会"), mapped.tasks)
        assertEquals(0.9, mapped.confidence, 0.001)
    }
}

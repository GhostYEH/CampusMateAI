package com.example.campusai

import com.example.campusai.data.remote.agent.AgentEventDto
import com.example.campusai.data.remote.agent.AgentRunStatus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class AgentRuntimeApiContractTest {
    @Test fun unknownRuntimeStatusIsKeptForConservativeUi() {
        // 未知状态必须保持 UNKNOWN，UI 不能把它提升为成功态。
        val event = AgentEventDto(
            id = "e1",
            type = "UNKNOWN_EVENT",
            runId = "run",
            sequence = 2,
            status = "UNKNOWN",
            phase = "UNKNOWN",
            summary = "安全摘要",
        )
        assertEquals(AgentRunStatus.UNKNOWN, event.runStatus())
        assertNotEquals(AgentRunStatus.SUCCEEDED, event.runStatus())
    }
}

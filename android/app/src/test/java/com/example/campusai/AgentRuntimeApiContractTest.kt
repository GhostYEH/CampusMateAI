package com.example.campusai

import com.example.campusai.data.remote.AgentEventDto
import com.example.campusai.data.remote.AgentProgressDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class AgentRuntimeApiContractTest {
    @Test fun unknownRuntimeStatusIsKeptForConservativeUi() {
        val event = AgentEventDto("e1", "UNKNOWN_EVENT", "run", 2, "UNKNOWN", "UNKNOWN", summary = "安全摘要", progress = AgentProgressDto())
        assertEquals("UNKNOWN", event.status)
        assertNotEquals("APPROVED", event.status)
    }
}

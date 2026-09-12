package com.example.campusai.data.remote.agent

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AgentErrorEnvelopeTest {
    private val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()

    @Test
    fun `approval required error parses code and details`() {
        val json = """
        {"code":"AGENT_APPROVAL_REQUIRED","message":"需要用户确认后继续",
         "request_id":"req_01H8XKQD0","details":{"run_id":"run_01H8XKQD2","approval_id":"apv_01H8XKQD4"}}
        """.trimIndent()
        val error = moshi.adapter(AgentErrorEnvelope::class.java).fromJson(json)!!
        assertEquals(AgentErrorCode.AGENT_APPROVAL_REQUIRED, error.errorCode())
        assertEquals("req_01H8XKQD0", error.requestId)
        assertNotNull(error.details)
        assertEquals("apv_01H8XKQD4", error.details!!["approval_id"])
    }

    @Test
    fun `academic policy restricted error parses`() {
        val json = """
        {"code":"AGENT_ACADEMIC_POLICY_RESTRICTED","message":"该作业在考试限制期,仅提供讲解",
         "request_id":"req_nw_001","details":{"run_id":"run_nw_001","academic_policy":"EXAM_RESTRICTED"}}
        """.trimIndent()
        val error = moshi.adapter(AgentErrorEnvelope::class.java).fromJson(json)!!
        assertEquals(AgentErrorCode.AGENT_ACADEMIC_POLICY_RESTRICTED, error.errorCode())
    }

    @Test
    fun `unknown error code maps to UNKNOWN`() {
        val error = AgentErrorEnvelope(code = "FUTURE_ERROR_CODE")
        assertEquals(AgentErrorCode.UNKNOWN, error.errorCode())
    }

    @Test
    fun `error parser extracts from response body`() {
        val json = """{"code":"AGENT_IDEMPOTENCY_CONFLICT","message":"重复","request_id":"r1"}"""
        val body = json.toResponseBody(null)
        val parsed = AgentErrorParser.parse(body)
        assertNotNull(parsed)
        assertEquals(AgentErrorCode.AGENT_IDEMPOTENCY_CONFLICT, parsed!!.errorCode())
    }

    @Test
    fun `error parser handles null body`() {
        assertEquals(null, AgentErrorParser.parse(null as okhttp3.ResponseBody?))
    }

    @Test
    fun `isApprovalRequired detects approval code`() {
        assertTrue(AgentErrorParser.isApprovalRequired(AgentErrorEnvelope(code = "AGENT_APPROVAL_REQUIRED")))
        assertTrue(!AgentErrorParser.isApprovalRequired(AgentErrorEnvelope(code = "OTHER")))
        assertTrue(!AgentErrorParser.isApprovalRequired(null))
    }

    @Test
    fun `isAcademicRestricted detects policy code`() {
        assertTrue(AgentErrorParser.isAcademicRestricted(AgentErrorEnvelope(code = "AGENT_ACADEMIC_POLICY_RESTRICTED")))
        assertTrue(!AgentErrorParser.isAcademicRestricted(null))
    }

    @Test
    fun `isIdempotencyConflict detects conflict code`() {
        assertTrue(AgentErrorParser.isIdempotencyConflict(AgentErrorEnvelope(code = "AGENT_IDEMPOTENCY_CONFLICT")))
        assertTrue(!AgentErrorParser.isIdempotencyConflict(null))
    }
}
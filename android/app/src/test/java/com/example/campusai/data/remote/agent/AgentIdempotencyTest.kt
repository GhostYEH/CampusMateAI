package com.example.campusai.data.remote.agent

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class AgentIdempotencyTest {

    @Test
    fun `stable key is deterministic for same inputs`() {
        val k1 = AgentIdempotency.stableKey("user_1", "fr_create_campaign", "payload_a")
        val k2 = AgentIdempotency.stableKey("user_1", "fr_create_campaign", "payload_a")
        assertEquals(k1, k2)
    }

    @Test
    fun `stable key differs for different users`() {
        val k1 = AgentIdempotency.stableKey("user_1", "op", "payload")
        val k2 = AgentIdempotency.stableKey("user_2", "op", "payload")
        assertNotEquals(k1, k2)
    }

    @Test
    fun `stable key differs for different operations`() {
        val k1 = AgentIdempotency.stableKey("user_1", "op_a", "payload")
        val k2 = AgentIdempotency.stableKey("user_1", "op_b", "payload")
        assertNotEquals(k1, k2)
    }

    @Test
    fun `stable key differs for different payloads`() {
        val k1 = AgentIdempotency.stableKey("user_1", "op", "payload_a")
        val k2 = AgentIdempotency.stableKey("user_1", "op", "payload_b")
        assertNotEquals(k1, k2)
    }

    @Test
    fun `payload key is stable across rotations`() {
        val request = FinalReviewCampaignCreateRequest(
            courseIds = listOf("c1", "c2"),
            examIds = listOf("e1"),
            dailyCapacityMinutes = 120,
        )
        val k1 = AgentIdempotency.payloadKey("user_1", "fr_create", request)
        val k2 = AgentIdempotency.payloadKey("user_1", "fr_create", request)
        assertEquals(k1, k2)
    }

    @Test
    fun `payload key differs for different payload content`() {
        val r1 = FinalReviewCampaignCreateRequest(examIds = listOf("e1"))
        val r2 = FinalReviewCampaignCreateRequest(examIds = listOf("e2"))
        val k1 = AgentIdempotency.payloadKey("user_1", "op", r1)
        val k2 = AgentIdempotency.payloadKey("user_1", "op", r2)
        assertNotEquals(k1, k2)
    }

    @Test
    fun `random key is unique`() {
        val keys = (1..100).map { AgentIdempotency.random() }
        assertEquals(100, keys.toSet().size)
    }
}

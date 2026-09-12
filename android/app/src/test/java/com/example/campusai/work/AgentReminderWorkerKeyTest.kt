package com.example.campusai.work

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class AgentReminderWorkerKeyTest {

    @Test
    fun `final review reminder key includes campaign and item`() {
        val key = AgentReminderWorker.uniqueWorkKey("campaign", "c1", "item:i1:reminder")
        assertEquals("agent_reminder:campaign:c1:item:i1:reminder", key)
    }

    @Test
    fun `notice workflow reminder key includes workflow and action`() {
        val key = AgentReminderWorker.uniqueWorkKey("workflow", "w1", "action:a1")
        assertEquals("agent_reminder:workflow:w1:action:a1", key)
    }

    @Test
    fun `same campaign item produces same key`() {
        val k1 = AgentReminderWorker.uniqueWorkKey("campaign", "c1", "item:i1:reminder")
        val k2 = AgentReminderWorker.uniqueWorkKey("campaign", "c1", "item:i1:reminder")
        assertEquals(k1, k2)
    }

    @Test
    fun `different items produce different keys`() {
        val k1 = AgentReminderWorker.uniqueWorkKey("campaign", "c1", "item:i1:reminder")
        val k2 = AgentReminderWorker.uniqueWorkKey("campaign", "c1", "item:i2:reminder")
        assertNotEquals(k1, k2)
    }

    @Test
    fun `different campaigns produce different keys`() {
        val k1 = AgentReminderWorker.uniqueWorkKey("campaign", "c1", "item:i1:reminder")
        val k2 = AgentReminderWorker.uniqueWorkKey("campaign", "c2", "item:i1:reminder")
        assertNotEquals(k1, k2)
    }

    @Test
    fun `different workflows produce different keys`() {
        val k1 = AgentReminderWorker.uniqueWorkKey("workflow", "w1", "action:a1")
        val k2 = AgentReminderWorker.uniqueWorkKey("workflow", "w2", "action:a1")
        assertNotEquals(k1, k2)
    }

    @Test
    fun `campaign and workflow scopes produce different keys`() {
        val k1 = AgentReminderWorker.uniqueWorkKey("campaign", "x", "item:i:reminder")
        val k2 = AgentReminderWorker.uniqueWorkKey("workflow", "x", "item:i:reminder")
        assertNotEquals(k1, k2)
    }
}
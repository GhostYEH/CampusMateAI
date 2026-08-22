package com.example.campusai

import com.example.campusai.data.model.Task
import com.example.campusai.data.repository.TaskRemotePolicy
import org.junit.Assert.assertTrue
import org.junit.Assert.assertEquals
import org.junit.Test

class TaskRemotePolicyTest {
    @Test
    fun `a successful empty server response replaces old task state`() {
        val old = listOf(Task("old", "Old", "", "", false, ""))

        assertTrue(TaskRemotePolicy.replaceAfterSuccessfulRead(old, emptyList()).isEmpty())
    }

    @Test
    fun `malformed blank and duplicate ids cannot reach task screens`() {
        val response = listOf(
            Task("", "No identity", "", "", false, ""),
            Task("task-1", "First", "", "", false, ""),
            Task("task-1", "Duplicate", "", "", true, ""),
            Task("task-2", "Second", "", "", false, ""),
        )

        val result = TaskRemotePolicy.replaceAfterSuccessfulRead(emptyList(), response)

        assertEquals(listOf("task-1", "task-2"), result.map(Task::id))
        assertEquals("First", result.first().title)
    }
}

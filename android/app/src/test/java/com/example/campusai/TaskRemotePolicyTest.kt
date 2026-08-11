package com.example.campusai

import com.example.campusai.data.model.Task
import com.example.campusai.data.repository.TaskRemotePolicy
import org.junit.Assert.assertTrue
import org.junit.Test

class TaskRemotePolicyTest {
    @Test
    fun `a successful empty server response replaces old task state`() {
        val old = listOf(Task("old", "Old", "", "", false, ""))

        assertTrue(TaskRemotePolicy.replaceAfterSuccessfulRead(old, emptyList()).isEmpty())
    }
}

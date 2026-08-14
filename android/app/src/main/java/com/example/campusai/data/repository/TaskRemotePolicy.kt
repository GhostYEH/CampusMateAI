package com.example.campusai.data.repository

import com.example.campusai.data.model.Task

object TaskRemotePolicy {
    fun replaceAfterSuccessfulRead(previous: List<Task>, response: List<Task>): List<Task> =
        response
            // A task without an id cannot be opened, updated, or deleted safely.
            .filter { it.id.isNotBlank() }
            // Defensive boundary for malformed or eventually-consistent API pages.
            // Keeping the first occurrence also preserves the server's display order.
            .distinctBy(Task::id)
}

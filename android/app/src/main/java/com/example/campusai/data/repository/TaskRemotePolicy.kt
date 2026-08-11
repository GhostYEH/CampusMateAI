package com.example.campusai.data.repository

import com.example.campusai.data.model.Task

object TaskRemotePolicy {
    fun replaceAfterSuccessfulRead(previous: List<Task>, response: List<Task>): List<Task> = response
}

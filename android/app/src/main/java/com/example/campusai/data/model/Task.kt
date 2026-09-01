package com.example.campusai.data.model

data class Task(
    val id: String,
    val title: String,
    val due: String,
    val course: String,
    val done: Boolean,
    val description: String = "",
    val importance: String = "unknown",
    val completedAt: String? = null,
)

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
    val source: String? = null,
    val courseId: String? = null,
    val sourceUrl: String? = null,
    val submittedAt: String? = null,
    val startAt: String? = null,
    val externalId: String? = null,
    val sourceText: String? = null,
)

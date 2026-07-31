package com.example.campusai.data.model

data class Task(
    val id: Long,
    val title: String,
    val due: String,
    val course: String,
    val done: Boolean,
    val description: String = "",
)
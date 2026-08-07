package com.example.campusai.data.model

data class User(
    val name: String,
    val role: String,
    val detail: String,
    val email: String = "",
    val phone: String = "",
    val studentId: String = "",
    val accountId: String = "",
    val teachers: List<Teacher> = emptyList(),
)

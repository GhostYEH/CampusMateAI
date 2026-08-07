package com.example.campusai.data.model

data class Teacher(
    val id: String,
    val name: String,
    val email: String = "",
    val phone: String = "",
    val subject: String = "",
    val notes: String = ""
)

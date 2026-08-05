package com.example.campusai.data.model

data class Notice(
    val id: String,
    val title: String,
    val source: String,
    val time: String,
    val unread: Boolean,
    val category: String = "",
    val content: String = "",
)

package com.example.campusai.data.model

data class Notice(
    val id: Long,
    val title: String,
    val source: String,
    val time: String,
    val unread: Boolean
)
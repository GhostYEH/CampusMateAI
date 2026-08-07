package com.example.campusai.data.model

data class PendingNotice(
    val id: String,
    val content: String,
    val sourceName: String,
    val publishedAt: String,
    val retryCount: Int = 0,
    val status: String = "pending"
)
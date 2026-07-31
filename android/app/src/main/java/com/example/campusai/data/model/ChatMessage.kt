package com.example.campusai.data.model

data class ChatMessage(
    val role: String,
    val text: String,
    val expressionLabel: ExpressionLabel? = null,
)

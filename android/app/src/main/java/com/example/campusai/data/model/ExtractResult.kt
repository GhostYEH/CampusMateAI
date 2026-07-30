package com.example.campusai.data.model

data class ExtractResult(
    val title: String = "",
    val source: String = "",
    val deadline: String = "",
    val tasks: List<String> = emptyList(),
    val confidence: Double = 0.0,
    val error: String? = null,
    var saved: Boolean = false
)
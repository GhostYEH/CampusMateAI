package com.example.campusai.data.model

data class Course(
    val id: String = "",
    val name: String,
    val code: String = "",
    val type: String = "",
    val teacher: String = "",
    val location: String = "",
    val provider: String? = null,
    val external_id: String? = null,
    val source_url: String? = null,
    val last_synced_at: String? = null
)

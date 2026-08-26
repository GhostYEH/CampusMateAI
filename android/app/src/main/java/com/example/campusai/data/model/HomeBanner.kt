package com.example.campusai.data.model

data class HomeBanner(
    val id: String,
    val eyebrow: String,
    val title: String,
    val subtitle: String,
    val ctaLabel: String,
    val imageUrl: String,
    val actionKey: String,
    val themeKey: String,
    val sortOrder: Int,
    val status: String,
    val startsAt: String?,
    val endsAt: String?,
    val createdAt: String,
    val updatedAt: String,
) {
    val destination: String?
        get() = when (actionKey) {
            "CPM_ASSISTANT" -> "counselor"
            "CHAOXING" -> "chaoxing"
            "EDU_SYSTEM" -> "edu_system"
            "TASKS" -> "tasks"
            "COMMUNITY" -> "community"
            else -> null
        }
}

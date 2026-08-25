package com.example.campusai.ui.screens.profile

data class EduLoginSensitiveState(
    val username: String = "",
    val password: String = "",
    val captcha: String = "",
    val preLoginToken: String? = null,
)

enum class EduLoginSensitiveEvent {
    DIRECT_CONNECTED,
    WEB_HANDOFF,
    DISCONNECT,
    CONNECTION_REPLACED,
    CANCEL,
    DISPOSE,
}

fun reduceEduLoginSensitiveState(
    state: EduLoginSensitiveState,
    @Suppress("UNUSED_PARAMETER") event: EduLoginSensitiveEvent,
): EduLoginSensitiveState = state.copy(
    password = "",
    captcha = "",
    preLoginToken = null,
)

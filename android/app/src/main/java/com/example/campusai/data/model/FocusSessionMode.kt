package com.example.campusai.data.model

/** The experience selected for one focus session; separate from the timer's FocusMode. */
enum class FocusSessionMode(
    val title: String,
    val description: String,
) {
    QUIET("安静专注", "只保留倒计时，减少打扰"),
    AI_COMPANION("AI 陪伴", "AI 语音陪你完成专注"),
    SMART_GUARD("摄像头＋语音", "AI 语音陪伴，并在本机观察学习状态"),

    ;

    companion object {
        fun fromApiValue(value: String?): FocusSessionMode =
            entries.firstOrNull { it.name == value } ?: QUIET
    }
}

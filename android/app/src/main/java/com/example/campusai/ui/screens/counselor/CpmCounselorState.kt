package com.example.campusai.ui.screens.counselor

import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Balance
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.School
import androidx.compose.material.icons.filled.Work

enum class CpmMessageStatus { GENERATING, COMPLETED, ERROR }

enum class DigitalHumanCommand { NONE, TOGGLE_MUTE, TOGGLE_PAUSE, REPLAY }

data class CpmChatMessage(
    val id: String,
    val role: String,
    val content: String,
    val status: CpmMessageStatus,
    val errorMessage: String? = null,
)

data class CpmPrompt(
    val id: String,
    val label: String,
    val prompt: String,
    val icon: ImageVector,
)

object CpmPromptCatalog {
    val all: List<CpmPrompt> = listOf(
        CpmPrompt("freshman", "大一应该\n怎么规划", "大一应该怎么规划？", Icons.Default.School),
        CpmPrompt("graduate", "我应该读研\n还是就业", "我应该读研还是就业？", Icons.Default.Work),
        CpmPrompt("club", "社团应该\n怎么选", "社团应该怎么选？", Icons.Default.Groups),
        CpmPrompt("balance", "怎么平衡\n学习和生活", "怎么平衡学习和生活？", Icons.Default.Balance),
        CpmPrompt("internship", "大学期间如何\n准备实习", "大学期间应该如何准备实习？", Icons.Default.Work),
        CpmPrompt("direction", "找不到方向\n怎么办", "大学里暂时找不到方向怎么办？", Icons.Default.School),
        CpmPrompt("friendship", "怎样建立健康的\n同学关系", "怎样建立健康的同学关系？", Icons.Default.Groups),
        CpmPrompt("habits", "如何养成稳定的\n学习习惯", "如何养成稳定的学习习惯？", Icons.Default.Balance),
    )

    fun batch(offset: Int, size: Int = 4): List<CpmPrompt> =
        List(size.coerceAtMost(all.size)) { index -> all[(offset + index).mod(all.size)] }
}

data class CpmCounselorUiState(
    val messages: List<CpmChatMessage> = emptyList(),
    val input: String = "",
    val sending: Boolean = false,
    val chatActive: Boolean = false,
    val recommendationOffset: Int = 0,
    val speechText: String = "",
    val speechRequestId: Int = 0,
    val lastCompletedAnswer: String = "",
    val playbackCommand: DigitalHumanCommand = DigitalHumanCommand.NONE,
    val playbackCommandId: Int = 0,
) {
    val recommendations: List<CpmPrompt> get() = CpmPromptCatalog.batch(recommendationOffset)
}

object CpmCounselorStateReducer {
    fun submit(state: CpmCounselorUiState, rawQuestion: String, now: Long): CpmCounselorUiState {
        val question = rawQuestion.trim()
        if (question.isEmpty() || state.sending) return state
        val user = CpmChatMessage("user-$now", "user", question, CpmMessageStatus.COMPLETED)
        val assistant = CpmChatMessage("assistant-$now", "assistant", "", CpmMessageStatus.GENERATING)
        return state.copy(
            messages = state.messages + user + assistant,
            input = "",
            sending = true,
            chatActive = true,
        )
    }

    fun appendChunk(state: CpmCounselorUiState, id: String, chunk: String): CpmCounselorUiState =
        state.copy(messages = state.messages.map { message ->
            if (message.id == id) message.copy(content = message.content + chunk) else message
        })

    fun complete(state: CpmCounselorUiState, id: String): CpmCounselorUiState {
        val answer = state.messages.firstOrNull { it.id == id }?.content.orEmpty()
        return state.copy(
            messages = state.messages.map { message ->
                if (message.id == id) message.copy(status = CpmMessageStatus.COMPLETED) else message
            },
            sending = false,
            speechText = answer,
            speechRequestId = if (answer.isBlank()) state.speechRequestId else state.speechRequestId + 1,
            lastCompletedAnswer = answer.ifBlank { state.lastCompletedAnswer },
        )
    }

    fun fail(state: CpmCounselorUiState, id: String, error: String): CpmCounselorUiState =
        state.copy(
            messages = state.messages.map { message ->
                if (message.id == id) message.copy(
                    content = message.content.ifBlank { "暂时无法生成回答，请稍后重试。" },
                    status = CpmMessageStatus.ERROR,
                    errorMessage = error,
                ) else message
            },
            sending = false,
        )
}

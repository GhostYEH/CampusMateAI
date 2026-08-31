package com.example.campusai.data.focus.voice

import com.example.campusai.data.remote.ApiClient
import com.example.campusai.data.remote.FocusAiAskRequest

interface FocusAiRepository {
    suspend fun ask(text: String): Result<String>
}

object RemoteFocusAiRepository : FocusAiRepository {
    override suspend fun ask(text: String): Result<String> = runCatching {
        val response = ApiClient.api.askFocusAi(FocusAiAskRequest(text))
        if (!response.isSuccessful) {
            throw IllegalStateException(response.errorBody()?.string()?.takeIf { it.isNotBlank() } ?: "AI 服务暂不可用，请稍后重试")
        }
        response.body()?.answer?.takeIf { it.isNotBlank() }
            ?: throw IllegalStateException("AI 服务没有返回回答")
    }
}

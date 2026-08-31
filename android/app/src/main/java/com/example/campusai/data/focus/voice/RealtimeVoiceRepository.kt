package com.example.campusai.data.focus.voice

import com.example.campusai.data.remote.ApiClient

interface RealtimeVoiceRepository {
    suspend fun create(): Result<RealtimeVoiceSessionConfig>
    suspend fun stop(sessionId: String): Result<Unit>
}

object RemoteRealtimeVoiceRepository : RealtimeVoiceRepository {
    override suspend fun create(): Result<RealtimeVoiceSessionConfig> = runCatching {
        val response = ApiClient.api.createFocusRealtimeVoiceSession()
        val body = response.body() ?: error("实时语音服务暂不可用")
        if (!response.isSuccessful) error("实时语音服务暂不可用")
        RealtimeVoiceSessionConfig(
            sessionId = body.session_id,
            websocketUrl = ApiClient.websocketUrl(body.websocket_path),
            accessToken = ApiClient.currentAccessToken().orEmpty(),
        )
    }

    override suspend fun stop(sessionId: String): Result<Unit> = runCatching {
        val response = ApiClient.api.stopFocusRealtimeVoiceSession(sessionId)
        if (!response.isSuccessful) error("实时语音会话关闭失败")
    }
}

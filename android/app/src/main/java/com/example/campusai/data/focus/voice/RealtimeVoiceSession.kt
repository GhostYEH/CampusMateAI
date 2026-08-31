package com.example.campusai.data.focus.voice

import android.content.Context
import android.util.Log
import kotlinx.coroutines.flow.StateFlow

enum class RealtimeVoicePhase { IDLE, CONNECTING, LISTENING, THINKING, SPEAKING, RECONNECTING, ERROR }

data class RealtimeVoiceSessionConfig(
    val sessionId: String,
    val websocketUrl: String,
    val accessToken: String,
    // Retained only for the historical RTC fallback; Seeduplex does not use them.
    val appId: String = "",
    val roomId: String = "",
    val userId: String = "",
    val agentUserId: String = "",
    val token: String = "",
    val tokenExpiresAt: Long = 0,
)

data class RealtimeVoiceSessionState(
    val phase: RealtimeVoicePhase = RealtimeVoicePhase.IDLE,
    val message: String? = null,
    val transcriptDelta: String? = null,
    val transcriptDone: String? = null,
    val transcriptDoneEventId: Long = 0L,
    val transcriptDoneUpstreamEventId: String? = null,
    val transcriptDoneItemId: String? = null,
    val answerDelta: String? = null,
    val answerDeltaEventId: Long = 0L,
    val answerDeltaUpstreamEventId: String? = null,
    val answerDeltaResponseId: String? = null,
    val answerDeltaItemId: String? = null,
    val answerDone: String? = null,
    val answerDoneEventId: Long = 0L,
    val answerDoneUpstreamEventId: String? = null,
    val answerDoneResponseId: String? = null,
    val answerDoneItemId: String? = null,
    /** Incremented when upstream VAD hears the user while AI output is active. */
    val bargeInEventId: Long = 0L,
    val bargeInResponseId: String? = null,
)

/** Provider boundary: Focus UI and controller never talk to an RTC SDK directly. */
interface RealtimeVoiceSession {
    val state: StateFlow<RealtimeVoiceSessionState>
    suspend fun connect(config: RealtimeVoiceSessionConfig)
    fun interrupt()
    fun mute()
    fun unmute()
    suspend fun stop()
    fun release()
}

/**
 * Volcengine RTC adapter. Reflection keeps the provider API isolated from product code while
 * the official RTC library remains the only owner of the realtime microphone and AI audio.
 */
class VolcengineRtcRealtimeVoiceSession(private val context: Context) : RealtimeVoiceSession {
    private val _state = kotlinx.coroutines.flow.MutableStateFlow(RealtimeVoiceSessionState())
    override val state: StateFlow<RealtimeVoiceSessionState> = _state
    private var engine: Any? = null
    private var room: Any? = null
    private var config: RealtimeVoiceSessionConfig? = null

    override suspend fun connect(config: RealtimeVoiceSessionConfig) {
        if (_state.value.phase == RealtimeVoicePhase.LISTENING) return
        _state.value = RealtimeVoiceSessionState(RealtimeVoicePhase.CONNECTING)
        this.config = config
        try {
            val rtcVideoClass = Class.forName("com.ss.bytertc.engine.RTCVideo")
            val create = rtcVideoClass.methods.first { it.name == "createRTCVideo" }
            engine = create.invoke(null, *create.parameterTypes.mapIndexed { index, type ->
                when {
                    index == 0 && type.isAssignableFrom(Context::class.java) -> context
                    index == 1 && type == String::class.java -> config.appId
                    type == Boolean::class.javaPrimitiveType -> false
                    else -> null
                }
            }.toTypedArray())
            val rtc = requireNotNull(engine) { "RTC engine was not created" }
            room = rtc.javaClass.methods.first { it.name == "createRTCRoom" && it.parameterTypes.size == 1 }
                .invoke(rtc, config.roomId)
            val userInfo = createUserInfo(config.userId)
            val roomConfig = createRoomConfig()
            val joined = requireNotNull(room).javaClass.methods.first { it.name == "joinRoom" && it.parameterTypes.size == 3 }
                .invoke(room, config.token, userInfo, roomConfig)
            if (joined is Int && joined != 0) error("RTC joinRoom failed: $joined")
            rtc.javaClass.methods.firstOrNull { it.name == "startAudioCapture" && it.parameterTypes.isEmpty() }?.invoke(rtc)
            _state.value = RealtimeVoiceSessionState(RealtimeVoicePhase.LISTENING, "正在听你说…")
            Log.i(TAG, "rtc_connected session=${config.sessionId}")
        } catch (error: Throwable) {
            Log.w(TAG, "rtc_connect_failed type=${error.javaClass.simpleName}")
            releaseRtcOnly()
            _state.value = RealtimeVoiceSessionState(RealtimeVoicePhase.ERROR, "实时语音连接失败，请稍后重试")
        }
    }

    override fun interrupt() {
        val activeConfig = config ?: return
        try {
            val json = "{\"Command\":\"interrupt\",\"InterruptMode\":1}"
            val payload = tlv("ctrl", json)
            engine?.javaClass?.methods?.firstOrNull { it.name == "sendUserBinaryMessage" && it.parameterTypes.size == 2 }
                ?.invoke(engine, activeConfig.agentUserId, payload)
            Log.i(TAG, "barge_in_detected ai_output_interrupted new_turn_started")
            _state.value = RealtimeVoiceSessionState(RealtimeVoicePhase.LISTENING, "正在听你说…")
        } catch (error: Throwable) {
            Log.w(TAG, "rtc_interrupt_failed type=${error.javaClass.simpleName}")
        }
    }

    override fun mute() { engine?.javaClass?.methods?.firstOrNull { it.name == "muteAudioCapture" }?.invoke(engine, true) }
    override fun unmute() { engine?.javaClass?.methods?.firstOrNull { it.name == "muteAudioCapture" }?.invoke(engine, false) }

    override suspend fun stop() {
        releaseRtcOnly()
        _state.value = RealtimeVoiceSessionState()
    }

    override fun release() {
        releaseRtcOnly()
        _state.value = RealtimeVoiceSessionState()
    }

    private fun releaseRtcOnly() {
        runCatching { room?.javaClass?.methods?.firstOrNull { it.name == "leaveRoom" }?.invoke(room) }
        runCatching { room?.javaClass?.methods?.firstOrNull { it.name == "destroy" }?.invoke(room) }
        runCatching { engine?.javaClass?.methods?.firstOrNull { it.name == "stopAudioCapture" }?.invoke(engine) }
        runCatching { engine?.javaClass?.methods?.firstOrNull { it.name == "destroy" }?.invoke(engine) }
        room = null
        engine = null
    }

    private fun createUserInfo(userId: String): Any {
        val clazz = Class.forName("com.ss.bytertc.engine.UserInfo")
        val constructor = clazz.constructors.first { it.parameterTypes.size == 2 }
        return constructor.newInstance(userId, "")
    }

    private fun createRoomConfig(): Any {
        val clazz = Class.forName("com.ss.bytertc.engine.RTCRoomConfig")
        return clazz.constructors.firstOrNull { it.parameterTypes.isEmpty() }?.newInstance()
            ?: clazz.constructors.first { it.parameterTypes.size == 4 }.newInstance(null, true, true, true)
    }

    private fun tlv(type: String, value: String): ByteArray {
        val text = value.toByteArray(Charsets.UTF_8)
        return ByteArray(8 + text.size).also { out ->
            type.take(4).forEachIndexed { index, char -> out[index] = char.code.toByte() }
            val length = text.size
            out[4] = (length ushr 24).toByte(); out[5] = (length ushr 16).toByte()
            out[6] = (length ushr 8).toByte(); out[7] = length.toByte()
            text.copyInto(out, 8)
        }
    }

    private companion object { const val TAG = "FocusRealtimeVoice" }
}

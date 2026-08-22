package com.example.campusai.data.focus.voice

import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** Product-level coordinator. The realtime SDK remains behind [RealtimeVoiceSession]. */
class FocusVoiceController(
    private val transcriber: SpeechTranscriber,
    private val aiRepository: FocusAiRepository,
    private val synthesizer: FocusSpeechSynthesizer,
    private val scope: CoroutineScope,
    private val realtimeRepository: RealtimeVoiceRepository? = null,
    private val realtimeSession: RealtimeVoiceSession? = null,
) {
    private val _state = MutableStateFlow(FocusVoiceState())
    val state: StateFlow<FocusVoiceState> = _state.asStateFlow()
    private var requestJob: Job? = null
    private var realtimeConfig: RealtimeVoiceSessionConfig? = null
    private var nextMessageId = 0L
    private var nextTurnId = 0L
    private var activeTurnId: Long? = null
    private var activeRealtimeTurn: RealtimeTurn? = null
    private val realtimeTurnsByResponseId = mutableMapOf<String, RealtimeTurn>()
    private var handledTranscriptDoneEventId = 0L
    private var handledAnswerDeltaEventId = 0L
    private var handledAnswerDoneEventId = 0L
    private var handledBargeInEventId = 0L

    init {
        realtimeSession?.let { session ->
            scope.launch {
                session.state.collect { realtime ->
                    val phase = when (realtime.phase) {
                        RealtimeVoicePhase.IDLE -> FocusVoicePhase.IDLE
                        RealtimeVoicePhase.CONNECTING -> FocusVoicePhase.CONNECTING
                        RealtimeVoicePhase.LISTENING -> FocusVoicePhase.LISTENING
                        RealtimeVoicePhase.THINKING -> FocusVoicePhase.THINKING
                        RealtimeVoicePhase.SPEAKING -> FocusVoicePhase.SPEAKING
                        RealtimeVoicePhase.RECONNECTING -> FocusVoicePhase.RECONNECTING
                        RealtimeVoicePhase.ERROR -> FocusVoicePhase.ERROR
                    }
                    var updated = _state.value.copy(
                        phase = phase,
                        liveTranscript = realtime.transcriptDelta ?: _state.value.liveTranscript,
                        liveAnswer = realtime.answerDelta ?: _state.value.liveAnswer,
                        errorMessage = realtime.message,
                    )
                    if (realtime.bargeInEventId > handledBargeInEventId) {
                        handledBargeInEventId = realtime.bargeInEventId
                        val cancelledResponseId = realtime.bargeInResponseId
                        if (cancelledResponseId != null) {
                            realtimeTurnsByResponseId.remove(cancelledResponseId)
                        } else {
                            // Older providers may omit a response id.  A speech-start event is
                            // still a hard turn boundary, so no pending AI response may survive.
                            realtimeTurnsByResponseId.clear()
                        }
                        activeRealtimeTurn = null
                        activeTurnId = null
                        updated = updated.copy(
                            phase = FocusVoicePhase.LISTENING,
                            liveAnswer = null,
                            errorMessage = null,
                        )
                        Log.i(TAG, "realtime_barge_in_applied response_id=${cancelledResponseId ?: "-"}")
                    }
                    if (realtime.answerDeltaEventId > handledAnswerDeltaEventId) {
                        handledAnswerDeltaEventId = realtime.answerDeltaEventId
                        val responseId = realtime.answerDeltaResponseId
                        if (responseId == null) {
                            Log.w(TAG, "realtime_answer_delta_missing_response_id event_id=${realtime.answerDeltaUpstreamEventId ?: "-"} item_id=${realtime.answerDeltaItemId ?: "-"}")
                        } else if (realtimeTurnsByResponseId[responseId] == null) {
                            val turn = activeRealtimeTurn
                            if (turn == null) {
                                Log.w(TAG, "realtime_answer_delta_unbound_no_active_turn response_id=$responseId item_id=${realtime.answerDeltaItemId ?: "-"}")
                            } else {
                                realtimeTurnsByResponseId[responseId] = turn
                                Log.i(TAG, "realtime_response_bound turn_id=${turn.turnId} response_id=$responseId item_id=${realtime.answerDeltaItemId ?: "-"}")
                            }
                        }
                    }
                    if (realtime.transcriptDoneEventId > handledTranscriptDoneEventId) {
                        handledTranscriptDoneEventId = realtime.transcriptDoneEventId
                        realtime.transcriptDone?.takeIf { it.isNotBlank() }?.let { text ->
                            val turnId = ++nextTurnId
                            activeTurnId = turnId
                            activeRealtimeTurn = RealtimeTurn(
                                turnId = turnId,
                                transcriptEventId = realtime.transcriptDoneUpstreamEventId,
                                transcriptItemId = realtime.transcriptDoneItemId,
                            )
                            Log.i(
                                TAG,
                                "realtime_user_turn_started turn_id=$turnId transcript_done_event=${realtime.transcriptDoneEventId} upstream_event_id=${realtime.transcriptDoneUpstreamEventId ?: "-"} item_id=${realtime.transcriptDoneItemId ?: "-"} length=${text.length}",
                            )
                            // A new user turn is a hard boundary: no transcript or answer
                            // fragment from the preceding turn may leak into it.
                            updated = updated
                                .appendMessage(
                                    role = FocusVoiceMessageRole.USER,
                                    text = text,
                                    turnId = turnId,
                                    upstreamEventId = realtime.transcriptDoneUpstreamEventId,
                                    itemId = realtime.transcriptDoneItemId,
                                )
                                .copy(liveTranscript = null, liveAnswer = null)
                        }
                    }
                    if (realtime.answerDoneEventId > handledAnswerDoneEventId) {
                        handledAnswerDoneEventId = realtime.answerDoneEventId
                        realtime.answerDone?.takeIf { it.isNotBlank() }?.let { text ->
                            val responseId = realtime.answerDoneResponseId
                            val turn = responseId?.let(realtimeTurnsByResponseId::remove)
                            if (turn != null) {
                                Log.i(
                                    TAG,
                                    "realtime_assistant_turn_completed turn_id=${turn.turnId} answer_done_event=${realtime.answerDoneEventId} upstream_event_id=${realtime.answerDoneUpstreamEventId ?: "-"} response_id=$responseId item_id=${realtime.answerDoneItemId ?: "-"} length=${text.length}",
                                )
                                updated = updated
                                    .appendMessage(
                                        role = FocusVoiceMessageRole.ASSISTANT,
                                        text = text,
                                        turnId = turn.turnId,
                                        upstreamEventId = realtime.answerDoneUpstreamEventId,
                                        responseId = responseId,
                                        itemId = realtime.answerDoneItemId,
                                    )
                                    .copy(liveAnswer = null, liveTranscript = null)
                                if (activeRealtimeTurn?.turnId == turn.turnId) activeRealtimeTurn = null
                                if (activeTurnId == turn.turnId) activeTurnId = null
                            } else {
                                Log.w(TAG, "realtime_answer_done_ignored_unbound_response answer_done_event=${realtime.answerDoneEventId} response_id=${responseId ?: "-"} item_id=${realtime.answerDoneItemId ?: "-"}")
                            }
                        }
                    }
                    _state.value = updated
                }
            }
        }
    }

    /** Default Focus path: RTC owns microphone capture and remote AI audio. */
    fun connectRealtime() {
        val repository = realtimeRepository ?: return
        val session = realtimeSession ?: return
        if (_state.value.phase == FocusVoicePhase.CONNECTING) return
        // A failed WebSocket keeps its short-lived session credentials.  Reuse them for
        // reconnect instead of leaving the UI permanently at "连接失败".
        realtimeConfig?.let { existingConfig ->
            _state.value = _state.value.copy(phase = FocusVoicePhase.RECONNECTING, errorMessage = null)
            scope.launch { session.connect(existingConfig) }
            return
        }
        _state.value = _state.value.copy(phase = FocusVoicePhase.CONNECTING, errorMessage = null)
        scope.launch {
            repository.create().onSuccess { config ->
                realtimeConfig = config
                session.connect(config)
            }.onFailure {
                _state.value = _state.value.copy(
                    phase = FocusVoicePhase.ERROR,
                    errorMessage = "实时语音服务暂不可用，请稍后重试",
                )
            }
        }
    }

    fun interruptRealtime() {
        realtimeSession?.interrupt()
        _state.value = _state.value.copy(phase = FocusVoicePhase.LISTENING, errorMessage = null)
    }
    fun muteRealtime() = realtimeSession?.mute()
    fun unmuteRealtime() = realtimeSession?.unmute()

    /** Legacy push-to-talk fallback; not used by the realtime Focus path. */
    fun startListening() {
        when (_state.value.phase) {
            FocusVoicePhase.THINKING, FocusVoicePhase.LISTENING, FocusVoicePhase.CONNECTING -> return
            FocusVoicePhase.SPEAKING -> stopSpeaking()
            else -> Unit
        }
        _state.value = _state.value.copy(phase = FocusVoicePhase.LISTENING, errorMessage = null)
        transcriber.start(::onTranscript, ::onError)
    }

    fun stopListening() {
        if (_state.value.phase == FocusVoicePhase.LISTENING) transcriber.stop()
    }

    fun stopSpeaking() {
        synthesizer.stop()
        if (_state.value.phase == FocusVoicePhase.SPEAKING) _state.value = _state.value.copy(phase = FocusVoicePhase.IDLE)
    }

    fun cancel() {
        transcriber.cancel()
        synthesizer.stop()
        requestJob?.cancel()
        requestJob = null
        _state.value = _state.value.copy(phase = FocusVoicePhase.IDLE, errorMessage = null)
    }

    fun reportPermissionDenied() {
        _state.value = _state.value.copy(phase = FocusVoicePhase.ERROR, errorMessage = "需要麦克风权限才能开启实时陪伴")
    }

    fun release() {
        cancel()
        realtimeConfig?.let { config -> scope.launch { realtimeRepository?.stop(config.sessionId) } }
        realtimeConfig = null
        realtimeSession?.release()
        transcriber.release()
        synthesizer.shutdown()
        scope.cancel()
    }

    private fun onTranscript(text: String) {
        val transcript = text.trim()
        if (transcript.isEmpty()) return onError("没有识别到清晰的语音，请再试一次")
        val turnId = ++nextTurnId
        activeTurnId = turnId
        _state.value = _state.value
            .appendMessage(FocusVoiceMessageRole.USER, transcript, turnId)
            .copy(phase = FocusVoicePhase.THINKING, errorMessage = null, liveTranscript = null, liveAnswer = null)
        requestJob?.cancel()
        requestJob = scope.launch {
            aiRepository.ask(transcript)
                .onSuccess { answer ->
                    _state.value = _state.value
                        .appendMessage(FocusVoiceMessageRole.ASSISTANT, answer, turnId)
                        .copy(phase = FocusVoicePhase.SPEAKING, errorMessage = null, liveAnswer = null)
                    if (activeTurnId == turnId) activeTurnId = null
                    synthesizer.speak(answer, onDone = { _state.value = _state.value.copy(phase = FocusVoicePhase.IDLE) }, onError = ::onError)
                }
                .onFailure { onError("AI 暂时无法回答，请稍后重试") }
        }
    }

    private fun onError(message: String) {
        requestJob?.cancel(); requestJob = null
        transcriber.cancel(); synthesizer.stop()
        _state.value = _state.value.copy(phase = FocusVoicePhase.ERROR, errorMessage = message)
    }

    private fun FocusVoiceState.appendMessage(
        role: FocusVoiceMessageRole,
        text: String,
        turnId: Long,
        upstreamEventId: String? = null,
        responseId: String? = null,
        itemId: String? = null,
    ): FocusVoiceState {
        val normalized = text.trim()
        if (normalized.isEmpty()) return this
        return copy(messages = messages + FocusVoiceMessage(++nextMessageId, turnId, role, normalized, upstreamEventId, responseId, itemId))
    }

    private data class RealtimeTurn(
        val turnId: Long,
        val transcriptEventId: String?,
        val transcriptItemId: String?,
    )

    private companion object { const val TAG = "FocusVoiceController" }
}

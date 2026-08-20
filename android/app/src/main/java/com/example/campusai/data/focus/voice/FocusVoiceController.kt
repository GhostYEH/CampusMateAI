package com.example.campusai.data.focus.voice

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
                    _state.value = _state.value.copy(phase = phase, errorMessage = realtime.message)
                }
            }
        }
    }

    /** Default Focus path: RTC owns microphone capture and remote AI audio. */
    fun connectRealtime() {
        val repository = realtimeRepository ?: return
        val session = realtimeSession ?: return
        if (_state.value.phase == FocusVoicePhase.CONNECTING || realtimeConfig != null) return
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

    fun interruptRealtime() = realtimeSession?.interrupt()
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
        _state.value = _state.value.copy(phase = FocusVoicePhase.THINKING, transcript = transcript, errorMessage = null)
        requestJob?.cancel()
        requestJob = scope.launch {
            aiRepository.ask(transcript)
                .onSuccess { answer ->
                    _state.value = _state.value.copy(phase = FocusVoicePhase.SPEAKING, answer = answer, errorMessage = null)
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
}

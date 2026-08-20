package com.example.campusai.data.focus.voice

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FocusVoiceControllerTest {
    @Test fun `listening result processes then speaks then idles`() {
        val transcriber = FakeTranscriber()
        val speaker = FakeSpeaker()
        val controller = controller(transcriber, speaker)

        controller.startListening()
        assertEquals(FocusVoicePhase.LISTENING, controller.state.value.phase)
        transcriber.result("这道题怎么做")
        assertEquals(FocusVoicePhase.SPEAKING, controller.state.value.phase)
        assertEquals("这道题怎么做", controller.state.value.transcript)
        assertEquals("简短回答", controller.state.value.answer)
        speaker.done()
        assertEquals(FocusVoicePhase.IDLE, controller.state.value.phase)
    }

    @Test fun `error and cancel return expected states`() {
        val transcriber = FakeTranscriber()
        val speaker = FakeSpeaker()
        val controller = controller(transcriber, speaker)
        controller.startListening()
        transcriber.error("识别失败")
        assertEquals(FocusVoicePhase.ERROR, controller.state.value.phase)
        controller.cancel()
        assertEquals(FocusVoicePhase.IDLE, controller.state.value.phase)
    }

    @Test fun `new listening stops speaking and processing is not duplicated`() {
        val transcriber = FakeTranscriber()
        val speaker = FakeSpeaker()
        val controller = controller(transcriber, speaker)
        controller.startListening()
        transcriber.result("问题")
        assertEquals(FocusVoicePhase.SPEAKING, controller.state.value.phase)
        controller.startListening()
        assertTrue(speaker.stopped)
        assertEquals(FocusVoicePhase.LISTENING, controller.state.value.phase)
    }

    @Test fun `realtime lifecycle maps transport states and releases`() {
        val realtime = FakeRealtimeSession()
        val controller = FocusVoiceController(
            transcriber = FakeTranscriber(),
            aiRepository = object : FocusAiRepository { override suspend fun ask(text: String) = Result.success("回答") },
            synthesizer = FakeSpeaker(),
            scope = CoroutineScope(Dispatchers.Unconfined),
            realtimeRepository = object : RealtimeVoiceRepository {
                override suspend fun create() = Result.success(realtime.config)
                override suspend fun stop(sessionId: String) = Result.success(Unit)
            },
            realtimeSession = realtime,
        )
        controller.connectRealtime()
        assertEquals(FocusVoicePhase.LISTENING, controller.state.value.phase)
        realtime.emit(RealtimeVoicePhase.THINKING)
        assertEquals(FocusVoicePhase.THINKING, controller.state.value.phase)
        realtime.emit(RealtimeVoicePhase.SPEAKING)
        controller.interruptRealtime()
        assertTrue(realtime.interrupted)
        controller.release()
        assertTrue(realtime.released)
    }

    private fun controller(transcriber: FakeTranscriber, speaker: FakeSpeaker) = FocusVoiceController(
        transcriber = transcriber,
        aiRepository = object : FocusAiRepository { override suspend fun ask(text: String) = Result.success("简短回答") },
        synthesizer = speaker,
        scope = CoroutineScope(Dispatchers.Unconfined),
    )

    private class FakeTranscriber : SpeechTranscriber {
        private var onResult: ((String) -> Unit)? = null
        private var onError: ((String) -> Unit)? = null
        override fun start(onResult: (String) -> Unit, onError: (String) -> Unit) { this.onResult = onResult; this.onError = onError }
        override fun stop() = Unit
        override fun cancel() = Unit
        override fun release() = Unit
        fun result(text: String) = onResult?.invoke(text)
        fun error(message: String) = onError?.invoke(message)
    }

    private class FakeSpeaker : FocusSpeechSynthesizer {
        private var onDone: (() -> Unit)? = null
        var stopped = false
        override fun speak(text: String, onDone: () -> Unit, onError: (String) -> Unit) { this.onDone = onDone }
        override fun stop() { stopped = true; onDone = null }
        override fun shutdown() = Unit
        fun done() = onDone?.invoke()
    }

    private class FakeRealtimeSession : RealtimeVoiceSession {
        private val mutableState = MutableStateFlow(RealtimeVoiceSessionState())
        override val state: StateFlow<RealtimeVoiceSessionState> = mutableState
        var interrupted = false
        var released = false
        val config = RealtimeVoiceSessionConfig("s", "123456789012345678901234", "r", "u", "ai", "t", 1)
        override suspend fun connect(config: RealtimeVoiceSessionConfig) { emit(RealtimeVoicePhase.LISTENING) }
        override fun interrupt() { interrupted = true; emit(RealtimeVoicePhase.LISTENING) }
        override fun mute() = Unit
        override fun unmute() = Unit
        override suspend fun stop() = Unit
        override fun release() { released = true; emit(RealtimeVoicePhase.IDLE) }
        fun emit(phase: RealtimeVoicePhase) { mutableState.value = RealtimeVoiceSessionState(phase) }
    }
}

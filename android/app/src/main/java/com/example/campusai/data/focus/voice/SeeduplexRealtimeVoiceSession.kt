package com.example.campusai.data.focus.voice

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaPlayer
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.util.Log
import com.example.campusai.data.remote.ApiClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/** CampusMate WebSocket transport. It never knows the upstream Seeduplex key or protocol. */
class SeeduplexRealtimeVoiceSession(private val context: Context) : RealtimeVoiceSession {
    private val _state = MutableStateFlow(RealtimeVoiceSessionState())
    override val state: StateFlow<RealtimeVoiceSessionState> = _state
    private val client = OkHttpClient.Builder().readTimeout(0, TimeUnit.MILLISECONDS).build()
    private val capturing = AtomicBoolean(false)
    private var socket: WebSocket? = null
    private var recorder: AudioRecord? = null
    private var echoCanceler: AcousticEchoCanceler? = null
    private var captureThread: Thread? = null
    private val audioTrackLock = Any()
    private var audioTrack: AudioTrack? = null
    private val compressedAudioLock = Any()
    private val compressedAudioBuffer = ByteArrayOutputStream()
    private var compressedAudioPlayer: MediaPlayer? = null
    // The backend's transcript "delta" events are cumulative snapshots, not append-only chunks.
    // Keep the latest snapshot until the corresponding done event arrives.
    private val transcriptBufferLock = Any()
    private var transcriptBuffer = ""
    private var transcriptDoneEventId = 0L
    private var answerDeltaEventId = 0L
    private var answerDoneEventId = 0L
    private var bargeInEventId = 0L

    override suspend fun connect(config: RealtimeVoiceSessionConfig) {
        if (socket != null) return
        clearTranscriptBuffer()
        _state.value = RealtimeVoiceSessionState(RealtimeVoicePhase.CONNECTING)
        val url = config.websocketUrl + "?access_token=" + java.net.URLEncoder.encode(config.accessToken, "UTF-8")
        socket = client.newWebSocket(Request.Builder().url(url).build(), object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.i(TAG, "seeduplex_backend_connected session=${config.sessionId}")
                startCapture(webSocket)
            }
            override fun onMessage(webSocket: WebSocket, text: String) = handleEvent(text)
            override fun onMessage(webSocket: WebSocket, bytes: okio.ByteString) {
                val audio = bytes.toByteArray()
                Log.d(TAG, "ai_audio_received bytes=${audio.size}")
                Log.i(TAG, "AUDIO_RECEIVE bytes=${audio.size}")
                Log.i(TAG, "AUDIO_HEADER=${audio.firstBytesHex()}")
                if (audio.hasCompressedContainerHeader() || hasCompressedAudioBuffered()) {
                    bufferCompressedAudio(audio)
                } else {
                    playPcmAudio(audio)
                }
            }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.w(TAG, "seeduplex_socket_failed type=${t.javaClass.simpleName}")
                stopCapture(); socket = null
                releaseAudioPlayback()
                clearTranscriptBuffer()
                _state.value = RealtimeVoiceSessionState(RealtimeVoicePhase.ERROR, "实时语音连接失败，请稍后重试")
            }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                stopCapture(); socket = null
                releaseAudioPlayback()
                clearTranscriptBuffer()
                _state.value = RealtimeVoiceSessionState()
            }
        })
    }

    override fun interrupt() {
        val sent = socket?.send("{\"type\":\"response.cancel\"}") == true
        if (sent) {
            Log.i(TAG, "response_cancel_sent")
            // Keep AudioRecord and the WebSocket alive: cancelling a response is not ending a session.
            _state.value = _state.value.copy(
                phase = RealtimeVoicePhase.LISTENING,
                message = "正在听你说…",
                answerDelta = null,
            )
            flushAudioPlayback()
        } else {
            Log.w(TAG, "response_cancel_not_sent socket_unavailable")
        }
    }

    override fun mute() = stopCapture()
    override fun unmute() { socket?.let(::startCapture) }
    override suspend fun stop() {
        socket?.send("{\"type\":\"stop\"}")
        stopCapture()
        releaseAudioPlayback()
        socket?.close(1000, "focus closed")
        socket = null
        clearTranscriptBuffer()
    }

    override fun release() {
        stopCapture()
        releaseAudioPlayback()
        socket?.cancel()
        socket = null
        clearTranscriptBuffer()
        client.dispatcher.executorService.shutdown()
        _state.value = RealtimeVoiceSessionState()
    }

    private fun startCapture(webSocket: WebSocket) {
        if (!capturing.compareAndSet(false, true)) return
        val minBuffer = AudioRecord.getMinBufferSize(SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        if (minBuffer <= 0) { _state.value = RealtimeVoiceSessionState(RealtimeVoicePhase.ERROR, "麦克风初始化失败"); return }
        // Voice communication enables the platform's acoustic-processing path.  The explicit
        // echo canceller prevents the AI's speaker output from being treated as a new user turn
        // while retaining full-duplex capture for genuine user barge-in.
        recorder = AudioRecord(MediaRecorder.AudioSource.VOICE_COMMUNICATION, SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(minBuffer, FRAME_BYTES * 4))
        recorder?.let { activeRecorder ->
            if (AcousticEchoCanceler.isAvailable()) {
                echoCanceler = AcousticEchoCanceler.create(activeRecorder.audioSessionId)?.also { canceller ->
                    runCatching { canceller.enabled = true }
                    Log.i(TAG, "acoustic_echo_canceler_enabled")
                }
            } else {
                Log.w(TAG, "acoustic_echo_canceler_unavailable")
            }
            activeRecorder.startRecording()
        }
        _state.value = RealtimeVoiceSessionState(RealtimeVoicePhase.LISTENING, "正在听你说…")
        Log.i(TAG, "audio_capture_started")
        captureThread = Thread {
            val frame = ByteArray(FRAME_BYTES)
            while (capturing.get()) {
                val read = recorder?.read(frame, 0, frame.size, AudioRecord.READ_BLOCKING) ?: -1
                if (read > 0) webSocket.send(okio.ByteString.of(*frame.copyOf(read)))
            }
        }.apply { name = "CampusMateSeeduplexCapture"; start() }
    }

    private fun stopCapture() {
        if (!capturing.compareAndSet(true, false)) return
        runCatching { echoCanceler?.release() }
        echoCanceler = null
        runCatching { recorder?.stop() }; runCatching { recorder?.release() }
        recorder = null; captureThread = null
    }

    private fun playPcmAudio(audio: ByteArray) {
        if (audio.isEmpty()) return
        try {
            val track = ensureAudioTrack() ?: return
            val written = track.write(audio, 0, audio.size, AudioTrack.WRITE_BLOCKING)
            if (written < 0) {
                Log.e(TAG, "AUDIO_PLAY_ERROR write_result=$written requested=${audio.size}")
            } else {
                Log.i(TAG, "AUDIO_WRITE bytes=$written")
            }
        } catch (error: Throwable) {
            Log.e(TAG, "AUDIO_PLAY_ERROR type=${error.javaClass.simpleName}", error)
            releaseAudioPlayback()
        }
    }

    private fun ensureAudioTrack(): AudioTrack? {
        return synchronized(audioTrackLock) {
            audioTrack?.takeIf { it.state == AudioTrack.STATE_INITIALIZED }?.let { return@synchronized it }
            releaseAudioPlaybackLocked()
            val minBufferBytes = AudioTrack.getMinBufferSize(
                OUTPUT_SAMPLE_RATE,
                AudioFormat.CHANNEL_OUT_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
            )
            if (minBufferBytes <= 0) {
                Log.e(TAG, "AUDIO_PLAY_ERROR invalid_min_buffer=$minBufferBytes")
                return@synchronized null
            }
            try {
                AudioTrack.Builder()
                    .setAudioAttributes(
                        AudioAttributes.Builder()
                            .setUsage(AudioAttributes.USAGE_MEDIA)
                            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                            .build(),
                    )
                    .setAudioFormat(
                        AudioFormat.Builder()
                            .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                            .setSampleRate(OUTPUT_SAMPLE_RATE)
                            .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                            .build(),
                    )
                    .setBufferSizeInBytes(maxOf(minBufferBytes, OUTPUT_BUFFER_BYTES))
                    .setTransferMode(AudioTrack.MODE_STREAM)
                    .build()
                    .also { track ->
                        if (track.state != AudioTrack.STATE_INITIALIZED) {
                            Log.e(TAG, "AUDIO_PLAY_ERROR audio_track_state=${track.state}")
                            track.release()
                        } else {
                            audioTrack = track
                            Log.i(TAG, "AUDIO_TRACK_INIT sample_rate=$OUTPUT_SAMPLE_RATE channels=1 bits=16 buffer_bytes=${maxOf(minBufferBytes, OUTPUT_BUFFER_BYTES)}")
                            track.play()
                            Log.i(TAG, "AUDIO_TRACK_PLAY")
                        }
                    }
                    .takeIf { it.state == AudioTrack.STATE_INITIALIZED }
            } catch (error: Throwable) {
                Log.e(TAG, "AUDIO_PLAY_ERROR init_type=${error.javaClass.simpleName}", error)
                null
            }
        }
    }

    private fun flushAudioPlayback() = synchronized(audioTrackLock) {
        runCatching { audioTrack?.pause() }
        runCatching { audioTrack?.flush() }
        runCatching { audioTrack?.play() }
        clearCompressedAudio()
    }

    private fun releaseAudioPlayback() {
        synchronized(audioTrackLock) { releaseAudioPlaybackLocked() }
        clearCompressedAudio()
    }

    private fun releaseAudioPlaybackLocked() {
        audioTrack?.let { track ->
            runCatching { track.pause() }
            runCatching { track.flush() }
            runCatching { track.release() }
        }
        audioTrack = null
    }

    /** Seeduplex currently delivers Ogg/Opus. Accumulate a response and use Android's decoder. */
    private fun bufferCompressedAudio(audio: ByteArray) = synchronized(compressedAudioLock) {
        compressedAudioBuffer.write(audio)
        Log.i(TAG, "AUDIO_OGG_BUFFER bytes=${compressedAudioBuffer.size()}")
    }

    private fun hasCompressedAudioBuffered(): Boolean = synchronized(compressedAudioLock) {
        compressedAudioBuffer.size() > 0
    }

    private fun clearCompressedAudio() = synchronized(compressedAudioLock) {
        compressedAudioBuffer.reset()
        runCatching { compressedAudioPlayer?.stop() }
        runCatching { compressedAudioPlayer?.release() }
        compressedAudioPlayer = null
    }

    private fun playCompressedAudioIfAvailable() {
        val audio = synchronized(compressedAudioLock) {
            if (compressedAudioBuffer.size() == 0) return
            compressedAudioBuffer.toByteArray().also { compressedAudioBuffer.reset() }
        }
        try {
            val file = File.createTempFile("seeduplex_", ".ogg", context.cacheDir).apply {
                writeBytes(audio)
                deleteOnExit()
            }
            val player = MediaPlayer().apply {
                setDataSource(file.absolutePath)
                setOnCompletionListener {
                    runCatching { it.release() }
                    file.delete()
                    _state.value = _state.value.copy(
                        phase = RealtimeVoicePhase.LISTENING,
                        message = "正在听你说…",
                    )
                }
                prepare()
                start()
            }
            synchronized(compressedAudioLock) { compressedAudioPlayer = player }
            _state.value = _state.value.copy(
                phase = RealtimeVoicePhase.SPEAKING,
                message = "AI 正在回答…",
            )
            Log.i(TAG, "AUDIO_OGG_PLAY bytes=${audio.size}")
        } catch (error: Throwable) {
            Log.e(TAG, "AUDIO_OGG_PLAY_ERROR type=${error.javaClass.simpleName}", error)
        }
    }

    private fun ByteArray.firstBytesHex(): String =
        take(16).joinToString(separator = " ") { byte -> "%02X".format(byte.toInt() and 0xFF) }

    private fun ByteArray.hasCompressedContainerHeader(): Boolean =
        startsWithAscii("OggS") || startsWithAscii("RIFF") || startsWithAscii("ID3") ||
            (size >= 2 && (this[0].toInt() and 0xFF) == 0xFF && (this[1].toInt() and 0xF6) == 0xF0)

    private fun ByteArray.startsWithAscii(value: String): Boolean =
        size >= value.length && value.indices.all { index -> this[index] == value[index].code.toByte() }

    private fun cacheTranscriptSnapshot(text: String): String = synchronized(transcriptBufferLock) {
        if (text.isNotBlank()) transcriptBuffer = text
        transcriptBuffer
    }

    private fun consumeTranscriptBuffer(): String = synchronized(transcriptBufferLock) {
        transcriptBuffer.also { transcriptBuffer = "" }
    }

    private fun clearTranscriptBuffer() = synchronized(transcriptBufferLock) {
        transcriptBuffer = ""
    }

    private fun handleEvent(raw: String) {
        val event = org.json.JSONObject(raw)
        val type = event.optString("type")
        val eventId = event.optString("event_id").orNullIdentifier()
        val responseId = event.optString("response_id").ifBlank {
            event.optJSONObject("response")?.optString("id").orEmpty()
        }.orNullIdentifier()
        val itemId = event.optString("item_id").ifBlank {
            event.optJSONObject("item")?.optString("id").orEmpty()
        }.orNullIdentifier()
        Log.d(TAG, "realtime_server_event type=$type event_id=${eventId ?: "-"} response_id=${responseId ?: "-"} item_id=${itemId ?: "-"}")
        Log.d(TAG, "TYPE_CHECK=[$type]")
        when (type) {
            "state" -> when (event.optString("state")) {
                // Preserve completed-event fields. A state event can immediately follow a
                // transcript completion event, and the controller consumes those fields.
                "listening" -> {
                    _state.value = _state.value.copy(
                        phase = RealtimeVoicePhase.LISTENING,
                        message = "正在听你说…",
                    )
                    playCompressedAudioIfAvailable()
                }
                "speaking" -> {
                    clearCompressedAudio()
                    _state.value = _state.value.copy(
                        phase = RealtimeVoicePhase.SPEAKING,
                        message = "正在回答…",
                    )
                }
            }
            "user_speech_started" -> {
                // The backend VAD heard the user.  Stop both PCM and the locally decoded
                // Ogg playback immediately; microphone capture remains running for this turn.
                val interruptedResponseId = event.optString("response_id").orNullIdentifier()
                flushAudioPlayback()
                _state.value = _state.value.copy(
                    phase = RealtimeVoicePhase.LISTENING,
                    message = "正在听你说…",
                    answerDelta = null,
                    bargeInEventId = ++bargeInEventId,
                    bargeInResponseId = interruptedResponseId,
                )
                Log.i(TAG, "barge_in_detected response_id=${interruptedResponseId ?: "-"} ai_audio_stopped")
            }
            "user_transcript_delta" -> {
                Log.d(TAG, "TRANSCRIPT_RAW=$raw")
                val text = event.optString("text")
                val cachedTranscript = cacheTranscriptSnapshot(text)
                Log.i(TAG, "TRANSCRIPT_DELTA_CACHE=$cachedTranscript")

                _state.value = _state.value.copy(
                    transcriptDelta = cachedTranscript,
                )
            }
            "user_transcript_done" -> {
                // The done event currently carries metadata only, so use the last cumulative
                // transcript snapshot. Prefer a supplied text value for protocol compatibility.
                val text = event.optString("text").ifBlank(::consumeTranscriptBuffer)
                clearTranscriptBuffer()
                Log.i(TAG, "FINAL_TRANSCRIPT=$text")
                Log.i(TAG, "realtime_transcript_done length=${text.length} event_id=${eventId ?: "-"} item_id=${itemId ?: "-"}")
                _state.value = _state.value.copy(
                    transcriptDone = text,
                    transcriptDoneEventId = ++transcriptDoneEventId,
                    transcriptDoneUpstreamEventId = eventId,
                    transcriptDoneItemId = itemId,
                    transcriptDelta = null,
                )
            }
            "ai_text_delta" -> {
                val text = event.optString("text")
                Log.d(TAG, "realtime_answer_delta length=${text.length} event_id=${eventId ?: "-"} response_id=${responseId ?: "-"} item_id=${itemId ?: "-"}")
                _state.value = _state.value.copy(
                    answerDelta = text,
                    answerDeltaEventId = ++answerDeltaEventId,
                    answerDeltaUpstreamEventId = eventId,
                    answerDeltaResponseId = responseId,
                    answerDeltaItemId = itemId,
                )
            }
            "ai_text_done" -> {
                val text = event.optString("text")
                Log.i(TAG, "realtime_answer_done length=${text.length} event_id=${eventId ?: "-"} response_id=${responseId ?: "-"} item_id=${itemId ?: "-"}")
                _state.value = _state.value.copy(
                    answerDone = text,
                    answerDoneEventId = ++answerDoneEventId,
                    answerDoneUpstreamEventId = eventId,
                    answerDoneResponseId = responseId,
                    answerDoneItemId = itemId,
                    answerDelta = null,
                )
            }
            "error" -> _state.value = RealtimeVoiceSessionState(RealtimeVoicePhase.ERROR, event.optString("message", "实时语音服务暂不可用"))
        }
    }

    private fun String?.orNullIdentifier(): String? = this?.takeIf { it.isNotBlank() && it != "-" }

    private companion object {
        const val TAG = "SeeduplexVoice"
        const val SAMPLE_RATE = 16000
        const val FRAME_BYTES = 640 // 20 ms, mono PCM16
        const val OUTPUT_SAMPLE_RATE = 24000
        const val OUTPUT_BUFFER_BYTES = OUTPUT_SAMPLE_RATE * 2 / 5 // 200 ms, mono PCM16
    }
}

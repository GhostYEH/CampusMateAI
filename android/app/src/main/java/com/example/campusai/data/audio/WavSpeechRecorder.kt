package com.example.campusai.data.audio

import android.annotation.SuppressLint
import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** A small capture boundary so framing and shutdown can be tested without a microphone. */
internal interface SpeechAudioCapture {
    val bufferSize: Int
    fun start()
    fun read(buffer: ByteArray, count: Int): Int
    fun stop()
    fun release()
}

/**
 * Records mono 16 kHz PCM16 speech for `/assistant/asr`, bounded to [maxSeconds].
 * Call start/stop/cancel off the UI thread: device startup/shutdown and WAV writing
 * may block. Permissions belong to the caller. A returned file belongs to the caller.
 */
class WavSpeechRecorder internal constructor(
    private val cacheDirectory: File,
    private val sampleRate: Int,
    private val maxSeconds: Int,
    private val createCapture: (Int) -> SpeechAudioCapture?,
) {
    constructor(context: Context, sampleRate: Int = 16000, maxSeconds: Int = 60) : this(
        context.applicationContext.cacheDir, sampleRate, maxSeconds, ::createAndroidSpeechCapture,
    )

    init {
        require(sampleRate > 0 && maxSeconds > 0)
        require(sampleRate.toLong() * maxSeconds * 2 <= Int.MAX_VALUE)
    }

    private class CaptureSession(val capture: SpeechAudioCapture, val outputFile: File) {
        val pcm = ByteArrayOutputStream()
        val finished = CountDownLatch(1)
        val deviceLock = Any()
        var deviceStopped = false
        @Volatile var recording = true
        @Volatile var cancelled = false
        @Volatile var manuallyStopped = false
    }

    private val lock = Any()
    private var session: CaptureSession? = null

    val isRecording: Boolean get() = synchronized(lock) { session?.recording == true }

    /**
     * Returns false if the microphone cannot start. [onFinished] runs on the capture
     * thread after the limit/read failure has stopped and released the device.
     * Manual stop/cancel do not need this callback; the caller already owns completion.
     */
    fun start(onFinished: () -> Unit = {}): Boolean = synchronized(lock) {
        if (session != null) return@synchronized session?.recording == true
        val capture = try { createCapture(sampleRate) } catch (_: Exception) { null }
            ?: return@synchronized false
        try {
            capture.start()
        } catch (_: Exception) {
            try { capture.release() } catch (_: Exception) { }
            return@synchronized false
        }
        val current = CaptureSession(capture, File(cacheDirectory, "asr_${UUID.randomUUID()}.wav"))
        session = current
        Thread {
            try {
                val buffer = ByteArray(maxOf(2, capture.bufferSize))
                val maxBytes = maxSeconds * sampleRate * 2
                while (current.recording && current.pcm.size() < maxBytes) {
                    // AudioRecord byte reads must contain complete PCM16 frames.
                    val remaining = minOf(buffer.size, maxBytes - current.pcm.size())
                    val count = remaining - remaining % 2
                    val read = capture.read(buffer, count)
                    if (read <= 0 || read > count || read % 2 != 0) break
                    current.pcm.write(buffer, 0, read)
                }
            } catch (_: Exception) {
                // Preserve complete frames captured before an interrupted/failed read.
            } finally {
                current.recording = false
                stopDevice(current)
                synchronized(current.deviceLock) {
                    try { capture.release() } catch (_: Exception) { }
                }
                current.finished.countDown()
                if (!current.cancelled && !current.manuallyStopped) onFinished()
            }
        }.also { it.isDaemon = true; it.start() }
        true
    }

    /** Stops capture and returns the completed WAV, including after automatic completion. */
    fun stop(): File? {
        val current = synchronized(lock) {
            session?.takeUnless { it.manuallyStopped }?.also {
                it.manuallyStopped = true
                it.recording = false
            }
        } ?: return null
        try {
            stopDevice(current)
            val finished = try {
                current.finished.await(1500, TimeUnit.MILLISECONDS)
            } catch (_: InterruptedException) {
                Thread.currentThread().interrupt()
                false
            }
            // Never read/reset a buffer that may still be owned by the capture thread.
            if (!finished || current.cancelled) return null
            val data = current.pcm.toByteArray()
            if (data.size < sampleRate / 10 * 2) return null
            return try {
                FileOutputStream(current.outputFile).use { out ->
                    out.write(wavHeader(data.size, sampleRate))
                    out.write(data)
                }
                if (current.cancelled) { current.outputFile.delete(); null } else current.outputFile
            } catch (_: Exception) {
                current.outputFile.delete()
                null
            }
        } finally {
            synchronized(lock) { if (session === current) session = null }
        }
    }

    /**
     * Discards active capture/finalization without waiting for its worker or touching
     * its PCM buffer. Once stop() has returned a file, its cleanup belongs to the caller.
     */
    fun cancel() {
        val current = synchronized(lock) {
            session?.also { session = null; it.cancelled = true; it.recording = false }
        } ?: return
        stopDevice(current)
        current.outputFile.delete()
    }

    private fun stopDevice(current: CaptureSession) = synchronized(current.deviceLock) {
        if (!current.deviceStopped) {
            current.deviceStopped = true
            try { current.capture.stop() } catch (_: Exception) { }
        }
    }

    private fun wavHeader(pcmBytes: Int, rate: Int): ByteArray {
        val channels = 1
        val bitsPerSample = 16
        val byteRate = rate * channels * bitsPerSample / 8
        val blockAlign = channels * bitsPerSample / 8
        val header = ByteArray(44)
        fun putString(offset: Int, value: String) { value.forEachIndexed { i, c -> header[offset + i] = c.code.toByte() } }
        fun putIntLE(offset: Int, value: Int) {
            header[offset] = (value and 0xFF).toByte()
            header[offset + 1] = (value shr 8 and 0xFF).toByte()
            header[offset + 2] = (value shr 16 and 0xFF).toByte()
            header[offset + 3] = (value shr 24 and 0xFF).toByte()
        }
        fun putShortLE(offset: Int, value: Int) {
            header[offset] = (value and 0xFF).toByte()
            header[offset + 1] = (value shr 8 and 0xFF).toByte()
        }
        putString(0, "RIFF"); putIntLE(4, 36 + pcmBytes); putString(8, "WAVE")
        putString(12, "fmt "); putIntLE(16, 16); putShortLE(20, 1); putShortLE(22, channels)
        putIntLE(24, rate); putIntLE(28, byteRate); putShortLE(32, blockAlign); putShortLE(34, bitsPerSample)
        putString(36, "data"); putIntLE(40, pcmBytes)
        return header
    }
}

@SuppressLint("MissingPermission")
private fun createAndroidSpeechCapture(sampleRate: Int): SpeechAudioCapture? {
    val minBuffer = AudioRecord.getMinBufferSize(
        sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
    )
    if (minBuffer <= 0) return null
    val requestedSize = maxOf(minBuffer, sampleRate / 5 * 2)
    val captureBufferSize = requestedSize + requestedSize % 2
    val record = AudioRecord(
        MediaRecorder.AudioSource.VOICE_RECOGNITION,
        sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, captureBufferSize,
    )
    if (record.state != AudioRecord.STATE_INITIALIZED) {
        record.release()
        return null
    }
    return object : SpeechAudioCapture {
        override val bufferSize = captureBufferSize
        override fun start() = record.startRecording()
        override fun read(buffer: ByteArray, count: Int): Int = record.read(buffer, 0, count)
        override fun stop() = record.stop()
        override fun release() = record.release()
    }
}

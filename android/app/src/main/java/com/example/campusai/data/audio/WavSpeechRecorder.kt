package com.example.campusai.data.audio

import android.annotation.SuppressLint
import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.File
import java.io.FileOutputStream

/**
 * Records mono 16 kHz PCM16 speech to a WAV file suitable for the backend
 * `/assistant/asr` endpoint (WAV / PCM16LE / 16000 Hz / mono).
 *
 * The recorder captures on a background thread because `AudioRecord.read` blocks.
 * A hard cap ([maxSeconds], default 60s) keeps the upload within the backend limit
 * and avoids runaway memory/disk use. This class does not request permissions; the
 * caller must hold RECORD_AUDIO before calling [start].
 */
class WavSpeechRecorder(
    context: Context,
    private val sampleRate: Int = 16000,
    private val maxSeconds: Int = 60,
) {
    private val appContext = context.applicationContext
    private val outputFile = File(appContext.cacheDir, "asr_${System.currentTimeMillis()}.wav")

    @Volatile private var recording = false
    @Volatile private var cancelled = false
    private var thread: Thread? = null
    private var audioRecord: AudioRecord? = null
    private val pcm = java.io.ByteArrayOutputStream()

    val isRecording: Boolean get() = recording

    /** Starts capture. Returns false if the microphone could not be initialised. */
    @SuppressLint("MissingPermission")
    fun start(): Boolean {
        if (recording) return true
        val minBuffer = try {
            AudioRecord.getMinBufferSize(
                sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
            )
        } catch (_: Exception) {
            return false
        }
        if (minBuffer <= 0) return false
        val bufferSize = maxOf(minBuffer, sampleRate / 5 * 2) // ~200 ms of frames
        val record = try {
            AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                sampleRate,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                bufferSize,
            )
        } catch (_: Exception) {
            return false
        }
        if (record.state != AudioRecord.STATE_INITIALIZED) {
            record.release()
            return false
        }
        audioRecord = record
        pcm.reset()
        cancelled = false
        recording = true
        try {
            record.startRecording()
        } catch (_: Exception) {
            recording = false
            try { record.release() } catch (_: Exception) { }
            audioRecord = null
            return false
        }
        thread = Thread {
            val buffer = ByteArray(bufferSize)
            val maxBytes = maxSeconds * sampleRate * 2
            try {
                while (recording && pcm.size() < maxBytes) {
                    val read = record.read(buffer, 0, buffer.size)
                    if (read > 0) pcm.write(buffer, 0, read) else if (read < 0) break
                }
            } catch (_: Exception) {
                // Ignore read errors; stop() will finalise whatever was captured.
            }
        }.also { it.isDaemon = true; it.start() }
        return true
    }

    /**
     * Stops capture and writes a PCM16 WAV file. Returns the file, or null if the
     * recording was cancelled or too short to be useful (< ~0.3s).
     */
    fun stop(): File? {
        if (!recording) return null
        recording = false
        try { thread?.join(1500) } catch (_: InterruptedException) { }
        thread = null
        try { audioRecord?.stop() } catch (_: Exception) { }
        try { audioRecord?.release() } catch (_: Exception) { }
        audioRecord = null
        if (cancelled) { outputFile.delete(); return null }
        val data = pcm.toByteArray()
        pcm.reset()
        if (data.size < sampleRate / 10 * 2) { // < 0.1s of audio
            outputFile.delete()
            return null
        }
        return try {
            FileOutputStream(outputFile).use { out ->
                out.write(wavHeader(data.size, sampleRate))
                out.write(data)
            }
            outputFile
        } catch (_: Exception) {
            outputFile.delete()
            null
        }
    }

    /** Stops capture and deletes the partial file. */
    fun cancel() {
        cancelled = true
        recording = false
        try { thread?.join(1500) } catch (_: InterruptedException) { }
        thread = null
        try { audioRecord?.stop() } catch (_: Exception) { }
        try { audioRecord?.release() } catch (_: Exception) { }
        audioRecord = null
        pcm.reset()
        outputFile.delete()
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

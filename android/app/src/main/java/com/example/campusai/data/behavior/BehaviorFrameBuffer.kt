package com.example.campusai.data.behavior

import android.graphics.Bitmap
import com.example.campusai.data.camera.CameraFrame

data class BehaviorModelConfig(
    val frameCount: Int = 16,
    val inputWidth: Int = 192,
    val inputHeight: Int = 192,
    val sampleIntervalMs: Long = 200L,
    val confidenceThreshold: Float = 0.5f
)

class BehaviorFrameBuffer(
    val config: BehaviorModelConfig
) {
    private val frames = mutableListOf<Bitmap>()
    private var lastSampleTime = 0L

    @Synchronized
    fun addFrame(frame: CameraFrame): Boolean {
        val now = frame.timestampMs
        if (now - lastSampleTime < config.sampleIntervalMs) {
            return false
        }
        lastSampleTime = now

        val scaledBitmap = Bitmap.createScaledBitmap(
            frame.bitmap, 
            config.inputWidth, 
            config.inputHeight, 
            true
        )
        frames.add(scaledBitmap)

        if (frames.size > config.frameCount) {
            val removed = frames.removeAt(0)
            removed.recycle()
        }

        return frames.size == config.frameCount
    }

    @Synchronized
    fun getTemporalWindow(): List<Bitmap> {
        return frames.toList()
    }

    @Synchronized
    fun clear() {
        frames.forEach { it.recycle() }
        frames.clear()
        lastSampleTime = 0L
    }
}

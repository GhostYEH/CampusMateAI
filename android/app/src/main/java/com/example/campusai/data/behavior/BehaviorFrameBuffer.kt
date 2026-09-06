package com.example.campusai.data.behavior

import android.graphics.Bitmap
import com.example.campusai.data.camera.CameraFrame

data class BehaviorModelConfig(
    val frameCount: Int = 16,
    val inputWidth: Int = 224,
    val inputHeight: Int = 224,
    val sampleIntervalMs: Long = 400L,
    val confidenceThreshold: Float = 0.5f
) {
    companion object {
        // Production default and DIRECT_224 resize camera frames straight to 224x224,
        // so the engine's 224x224 preprocess becomes a no-op and the runtime path
        // matches training preprocessing exactly.
        val DIRECT_224 = BehaviorModelConfig(
            frameCount = 16,
            inputWidth = 224,
            inputHeight = 224,
            sampleIntervalMs = 400L,
            confidenceThreshold = 0.5f,
        )

        // Kept only for the pre-launch A/B comparison against the old production path.
        // Do not use this configuration for new production analyzers.
        val LEGACY_192 = BehaviorModelConfig(
            frameCount = 16,
            inputWidth = 192,
            inputHeight = 192,
            sampleIntervalMs = 200L,
            confidenceThreshold = 0.5f,
        )
    }
}

class BehaviorFrameBuffer(
    val config: BehaviorModelConfig
) {
    private val frames = mutableListOf<BufferedBehaviorFrame>()
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
        frames.add(
            BufferedBehaviorFrame(
                bitmap = scaledBitmap,
                sourceWidth = frame.bitmap.width,
                sourceHeight = frame.bitmap.height,
            ),
        )

        if (frames.size > config.frameCount) {
            val removed = frames.removeAt(0)
            removed.bitmap.recycle()
        }

        // V3.1.1: trigger inference on the first sampled frame instead of
        // waiting for the full frameCount window. The rolling window is still
        // capped at frameCount for the temporal snapshot handed to the engine.
        return frames.isNotEmpty()
    }

    @Synchronized
    fun getTemporalWindow(): List<Bitmap> {
        return frames.map(BufferedBehaviorFrame::bitmap)
    }

    @Synchronized
    fun latestFrame(): BufferedBehaviorFrame? = frames.lastOrNull()

    // V3.1.1 single-frame baseline: inference only needs the latest frame.
    // Returns a reference (no copy); callers own copying if they hand it to another thread.
    @Synchronized
    fun lastFrame(): Bitmap? {
        return frames.lastOrNull()?.bitmap
    }

    @Synchronized
    fun clear() {
        frames.forEach { it.bitmap.recycle() }
        frames.clear()
        lastSampleTime = 0L
    }
}

data class BufferedBehaviorFrame(
    val bitmap: Bitmap,
    val sourceWidth: Int,
    val sourceHeight: Int,
)

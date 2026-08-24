package com.example.campusai.data.behavior

import android.graphics.Bitmap
import android.graphics.RectF

interface BehaviorRecognitionEngine {
    val isAvailable: Boolean

    /** Called exactly once before any frames arrive. Must be idempotent. */
    fun initialize()

    /** Analyze a temporal window of frames. Caller retains ownership of the bitmap list. */
    fun analyzeTemporalWindow(frames: List<Bitmap>, timestampMs: Long): BehaviorPrediction

    /** ROI-aware path used by V3.4. Existing engines keep the legacy full-frame behavior. */
    fun analyzeTemporalWindow(
        frames: List<Bitmap>,
        timestampMs: Long,
        personBoundingBox: RectF?,
    ): BehaviorPrediction = analyzeTemporalWindow(frames, timestampMs)

    fun close()
}

class NoOpBehaviorRecognitionEngine : BehaviorRecognitionEngine {
    private var initialized = false

    override val isAvailable: Boolean = false

    override fun initialize() {
        initialized = true
    }

    override fun analyzeTemporalWindow(frames: List<Bitmap>, timestampMs: Long): BehaviorPrediction {
        return BehaviorPrediction(
            probabilities = emptyMap(),
            timestampMs = timestampMs,
            modelState = "MODEL_NOT_AVAILABLE",
        )
    }

    override fun close() {
        initialized = false
    }
}

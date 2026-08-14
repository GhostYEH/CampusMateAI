package com.example.campusai.data.behavior

import android.graphics.Bitmap

interface BehaviorRecognitionEngine {
    val isAvailable: Boolean

    /** Called exactly once before any frames arrive. Must be idempotent. */
    fun initialize()

    /** Analyze a temporal window of frames. Caller retains ownership of the bitmap list. */
    fun analyzeTemporalWindow(frames: List<Bitmap>, timestampMs: Long): BehaviorPrediction

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

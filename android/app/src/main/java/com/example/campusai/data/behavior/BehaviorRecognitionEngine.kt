package com.example.campusai.data.behavior

import android.graphics.Bitmap

interface BehaviorRecognitionEngine {
    fun initialize()
    fun analyzeTemporalWindow(frames: List<Bitmap>, timestampMs: Long): BehaviorPrediction
    fun close()
}

class NoOpBehaviorRecognitionEngine : BehaviorRecognitionEngine {
    override fun initialize() {}

    override fun analyzeTemporalWindow(frames: List<Bitmap>, timestampMs: Long): BehaviorPrediction {
        return BehaviorPrediction(
            probabilities = emptyMap(),
            timestampMs = timestampMs,
            modelState = "MODEL_NOT_AVAILABLE"
        )
    }

    override fun close() {}
}

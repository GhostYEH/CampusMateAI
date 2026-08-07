package com.example.campusai.data.behavior

import com.example.campusai.data.camera.CameraFrame
import com.example.campusai.data.camera.FrameAnalyzer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

class BehaviorAnalyzer(
    private val engine: BehaviorRecognitionEngine,
    config: BehaviorModelConfig = BehaviorModelConfig()
) : FrameAnalyzer {
    
    private val frameBuffer = BehaviorFrameBuffer(config)
    private val executor: ExecutorService = Executors.newSingleThreadExecutor()
    private val analyzing = AtomicBoolean(false)

    private val _predictions = MutableStateFlow(
        BehaviorPrediction(emptyMap(), 0L, "NOT_INITIALIZED")
    )
    val predictions: StateFlow<BehaviorPrediction> = _predictions.asStateFlow()

    override fun analyze(frame: CameraFrame) {
        if (!frameBuffer.addFrame(frame)) {
            return
        }

        if (analyzing.compareAndSet(false, true)) {
            val window = frameBuffer.getTemporalWindow()
            val timestamp = frame.timestampMs
            
            executor.execute {
                try {
                    val prediction = engine.analyzeTemporalWindow(window, timestamp)
                    _predictions.value = prediction
                } finally {
                    analyzing.set(false)
                }
            }
        }
    }

    fun reset() {
        frameBuffer.clear()
        _predictions.value = BehaviorPrediction(emptyMap(), 0L, "NOT_INITIALIZED")
    }

    fun dispose() {
        frameBuffer.clear()
        executor.shutdownNow()
        engine.close()
    }
}

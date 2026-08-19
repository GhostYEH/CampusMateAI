package com.example.campusai.data.behavior

import android.graphics.Bitmap
import android.util.Log
import com.example.campusai.BuildConfig
import com.example.campusai.data.camera.CameraFrame
import com.example.campusai.data.camera.FrameAnalyzer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.RejectedExecutionException
import java.util.concurrent.atomic.AtomicBoolean

class BehaviorAnalyzer(
    private val engine: BehaviorRecognitionEngine,
    config: BehaviorModelConfig = BehaviorModelConfig(),
) : FrameAnalyzer {

    private val frameBuffer = BehaviorFrameBuffer(config)
    private val executor: ExecutorService = Executors.newSingleThreadExecutor()
    private val analyzing = AtomicBoolean(false)
    private val disposed = AtomicBoolean(false)
    private val lifecycleLock = Any()
    private var initialized = false

    private val _predictions = MutableStateFlow(
        BehaviorPrediction(emptyMap(), 0L, "NOT_INITIALIZED"),
    )
    val predictions: StateFlow<BehaviorPrediction> = _predictions.asStateFlow()
    
    // Performance Baseline Metrics (Debug only)
    private var inferenceCount = 0
    private var inferenceDroppedCount = 0
    private var firstPredictionTimeMs = -1L
    private var lastInferenceStartTime = -1L
    private var totalInferenceIntervals = 0L
    private var initializationTimeMs = -1L

    override fun analyze(frame: CameraFrame) {
        synchronized(lifecycleLock) {
            if (disposed.get()) return

        // NoOp engine: do not buffer, do not resize, do not submit async work.
        if (!engine.isAvailable) {
            _predictions.value = BehaviorPrediction(
                emptyMap(),
                frame.timestampMs,
                "MODEL_NOT_AVAILABLE",
            )
            return
        }

            if (!frameBuffer.addFrame(frame)) {
                return
            }

            if (analyzing.compareAndSet(false, true)) {
                if (BuildConfig.DEBUG) {
                    val currentTime = System.currentTimeMillis()
                    if (lastInferenceStartTime > 0) {
                        totalInferenceIntervals += (currentTime - lastInferenceStartTime)
                    }
                    lastInferenceStartTime = currentTime
                }

                // V3.1.1 single-frame baseline: copy only the latest frame for inference.
                // The 16-frame rolling window is still maintained by BehaviorFrameBuffer
                // (see getTemporalWindow / lastFrame) for a future V4 TCN, but the ONNX
                // model only consumes the newest frame, so we no longer deep-copy the
                // whole window per inference.
                val latest = frameBuffer.lastFrame() ?: run {
                    analyzing.set(false)
                    return
                }
                val snapshot = listOf(
                    latest.copy(latest.config ?: Bitmap.Config.ARGB_8888, latest.isMutable)
                )
                val timestamp = frame.timestampMs

                try {
                    executor.execute {
                        try {
                            // shutdownNow() can return this task after dispose. In that
                            // case it is run only to release its owned snapshot; never
                            // call an engine that has already been closed.
                            if (disposed.get()) return@execute
                            val prediction = try {
                                engine.analyzeTemporalWindow(snapshot, timestamp)
                            } catch (_: Throwable) {
                                BehaviorPrediction(
                                    emptyMap(),
                                    timestamp,
                                    "INFERENCE_ERROR",
                                )
                            }
                            if (!disposed.get()) {
                                _predictions.value = prediction
                                
                                if (BuildConfig.DEBUG) {
                                    inferenceCount++
                                    if (firstPredictionTimeMs == -1L && initializationTimeMs > 0) {
                                        firstPredictionTimeMs = System.currentTimeMillis() - initializationTimeMs
                                    }
                                    
                                    val avgInterval = if (inferenceCount > 1) totalInferenceIntervals / (inferenceCount - 1) else 0
                                    
                                    if (inferenceCount % 10 == 0) {
                                        Log.d("BehaviorPerf", """
                                            [V3.1.1 Baseline]
                                            Inference Count: $inferenceCount
                                            Dropped/Busy Count: $inferenceDroppedCount
                                            Avg Interval: ${avgInterval}ms
                                            First Prediction Time: ${firstPredictionTimeMs}ms
                                            Pre-process Latency: ${prediction.debugPreprocessingLatencyMs}ms
                                            Inference Latency: ${prediction.debugInferenceLatencyMs}ms
                                        """.trimIndent())
                                    }
                                }
                            }
                        } finally {
                            // Inference owns the snapshot; recycle when done.
                            snapshot.forEach { it.recycle() }
                            analyzing.set(false)
                        }
                    }
                } catch (_: RejectedExecutionException) {
                    snapshot.forEach { it.recycle() }
                    analyzing.set(false)
                    if (BuildConfig.DEBUG) inferenceDroppedCount++
                }
            } else {
                if (BuildConfig.DEBUG) inferenceDroppedCount++
            }
        }
    }

    fun ensureInitialized() {
        synchronized(lifecycleLock) {
            if (disposed.get()) return
            if (!initialized) {
                if (BuildConfig.DEBUG) {
                    initializationTimeMs = System.currentTimeMillis()
                }
                engine.initialize()
                initialized = true
            }
        }
    }

    fun reset() {
        synchronized(lifecycleLock) {
            if (disposed.get()) return
            frameBuffer.clear()
            _predictions.value = BehaviorPrediction(emptyMap(), 0L, "NOT_INITIALIZED")
        }
    }

    fun dispose() {
        synchronized(lifecycleLock) {
            if (!disposed.compareAndSet(false, true)) return
            frameBuffer.clear()
            // A task removed from the executor queue would otherwise never reach its
            // finally block and would retain its inference-owned Bitmap snapshot.
            executor.shutdownNow().forEach(Runnable::run)
            engine.close()
            initialized = false
        }
    }
}

package com.example.campusai.data.behavior

import android.graphics.Bitmap
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
                // Snapshot the rolling buffer so inference owns its copies.
                val rawWindow = frameBuffer.getTemporalWindow()
                val snapshot = rawWindow.map { bitmap ->
                    bitmap.copy(bitmap.config ?: Bitmap.Config.ARGB_8888, bitmap.isMutable).also {
                        // copy() after the original — ownership now belongs to the inference task
                    }
                }
                val timestamp = frame.timestampMs

                try {
                    executor.execute {
                        try {
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
                }
            }
        }
    }

    fun ensureInitialized() {
        synchronized(lifecycleLock) {
            if (disposed.get()) return
            if (!initialized) {
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
            executor.shutdownNow()
            engine.close()
            initialized = false
        }
    }
}

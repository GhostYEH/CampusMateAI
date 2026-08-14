package com.example.campusai.data.behavior

import android.graphics.Bitmap
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
    @Suppress("UNUSED_PARAMETER") config: BehaviorModelConfig = BehaviorModelConfig(),
) : FrameAnalyzer {

    private val stabilizer = BehaviorPredictionStabilizer()
    private val executor: ExecutorService = Executors.newSingleThreadExecutor()
    private val analyzing = AtomicBoolean(false)
    @Volatile
    private var initialized = false
    @Volatile
    private var disposed = false

    private val _predictions = MutableStateFlow(
        BehaviorPrediction(emptyMap(), 0L, "NOT_INITIALIZED"),
    )
    val predictions: StateFlow<BehaviorPrediction> = _predictions.asStateFlow()

    override fun analyze(frame: CameraFrame) {
        if (disposed) {
            return
        }
        // NoOp engine: do not buffer, do not resize, do not submit async work.
        if (!engine.isAvailable) {
            _predictions.value = BehaviorPrediction(
                emptyMap(),
                frame.timestampMs,
                "MODEL_NOT_AVAILABLE",
            )
            return
        }

        if (analyzing.compareAndSet(false, true)) {
            // V1 is a single-frame ResNet. Copy exactly one current frame so
            // CameraFrame may be released immediately after this callback.
            val snapshot = frame.bitmap.takeUnless { it.isRecycled }?.copy(
                Bitmap.Config.ARGB_8888,
                false,
            )
            val timestamp = frame.timestampMs

            executor.execute {
                try {
                    if (snapshot == null || snapshot.isRecycled) {
                        _predictions.value = BehaviorPrediction(
                            emptyMap(),
                            timestamp,
                            "NO_FRAME",
                        )
                        return@execute
                    }
                    val rawPrediction = engine.analyzeTemporalWindow(listOf(snapshot), timestamp)
                    _predictions.value = if (rawPrediction.modelState == "READY_RGB_V1") {
                        val stabilized = stabilizer.stabilize(rawPrediction)
                        rawPrediction.copy(
                            probabilities = stabilized.probabilities,
                            stableBehavior = stabilized.stableBehavior,
                        )
                    } else {
                        stabilizer.reset()
                        rawPrediction
                    }
                } finally {
                    // Inference owns the snapshot; recycle when done.
                    if (snapshot != null && !snapshot.isRecycled) snapshot.recycle()
                    analyzing.set(false)
                }
            }
        }
    }

    fun ensureInitialized() {
        if (disposed) {
            return
        }
        if (!initialized) {
            _predictions.value = BehaviorPrediction(
                emptyMap(),
                System.currentTimeMillis(),
                "INITIALIZING",
            )
            engine.initialize()
            initialized = true
            if (!engine.isAvailable) {
                _predictions.value = BehaviorPrediction(
                    emptyMap(),
                    System.currentTimeMillis(),
                    "MODEL_NOT_AVAILABLE",
                )
            }
        }
    }

    fun reset() {
        stabilizer.reset()
        _predictions.value = BehaviorPrediction(emptyMap(), 0L, "NOT_INITIALIZED")
    }

    fun dispose() {
        disposed = true
        stabilizer.reset()
        executor.shutdownNow()
        engine.close()
        initialized = false
    }
}

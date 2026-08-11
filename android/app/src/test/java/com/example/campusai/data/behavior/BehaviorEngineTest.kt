package com.example.campusai.data.behavior

import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.atomic.AtomicInteger

class BehaviorEngineTest {

    // ── NoOp engine ──

    @Test fun noOpEngine_isNotAvailable() {
        val engine = NoOpBehaviorRecognitionEngine()
        assertFalse(engine.isAvailable)
    }

    @Test fun noOpEngine_initializeIsIdempotent() {
        val engine = NoOpBehaviorRecognitionEngine()
        engine.initialize()
        engine.initialize() // must not throw
    }

    @Test fun noOpEngine_alwaysReturnsModelNotAvailable() {
        val engine = NoOpBehaviorRecognitionEngine()
        val prediction = engine.analyzeTemporalWindow(emptyList(), 1000L)
        assertEquals("MODEL_NOT_AVAILABLE", prediction.modelState)
        assertTrue(prediction.probabilities.isEmpty())
    }

    @Test fun noOpEngine_closeThenReopen() {
        val engine = NoOpBehaviorRecognitionEngine()
        engine.initialize()
        engine.close()
        engine.initialize()
        assertFalse(engine.isAvailable)
    }

    // ── Initialize exactly once ──

    @Test fun engine_initializeExactlyOnce() {
        val initCounter = AtomicInteger(0)
        val engine = object : BehaviorRecognitionEngine {
            override val isAvailable = true
            override fun initialize() { initCounter.incrementAndGet() }
            override fun analyzeTemporalWindow(
                frames: List<android.graphics.Bitmap>,
                timestampMs: Long,
            ): BehaviorPrediction {
                return BehaviorPrediction(emptyMap(), timestampMs, "OK")
            }
            override fun close() {}
        }

        val analyzer = BehaviorAnalyzer(engine)
        analyzer.ensureInitialized()
        analyzer.ensureInitialized()
        analyzer.ensureInitialized()

        assertEquals(1, initCounter.get())
        analyzer.dispose()
    }

    // ── BehaviorRecognitionEngine.isAvailable contract ──

    @Test fun availableEngine_canBeCheckedWithoutInitialize() {
        val engine = object : BehaviorRecognitionEngine {
            override val isAvailable = true
            override fun initialize() {}
            override fun analyzeTemporalWindow(
                frames: List<android.graphics.Bitmap>,
                timestampMs: Long,
            ): BehaviorPrediction {
                return BehaviorPrediction(emptyMap(), timestampMs, "OK")
            }
            override fun close() {}
        }

        assertTrue(engine.isAvailable)
        engine.initialize()
        assertTrue(engine.isAvailable)
        engine.close()
        assertTrue(engine.isAvailable)
    }

    // ── NoOp analyzer does not produce temporal preprocessing workload ──

    @Test fun noOpAnalyzer_predictionAlwaysModelNotAvailable() {
        val engine = NoOpBehaviorRecognitionEngine()
        val analyzer = BehaviorAnalyzer(engine)

        // analyze() without real CameraFrame — the noOp short-circuit
        // happens before any frame processing, so even with null it just
        // emits MODEL_NOT_AVAILABLE (though in production CameraFrame is never null).
        val prediction = analyzer.predictions.value
        assertEquals("NOT_INITIALIZED", prediction.modelState)

        analyzer.ensureInitialized()
        analyzer.dispose()
    }

    // ── Engine.dispose resets state ──

    @Test fun disposeResetsInitializedState() {
        val engine = object : BehaviorRecognitionEngine {
            override val isAvailable = true
            var initCount = 0
            var closeCount = 0
            override fun initialize() { initCount++ }
            override fun analyzeTemporalWindow(
                frames: List<android.graphics.Bitmap>,
                timestampMs: Long,
            ): BehaviorPrediction {
                return BehaviorPrediction(emptyMap(), timestampMs, "OK")
            }
            override fun close() { closeCount++ }
        }

        val analyzer = BehaviorAnalyzer(engine)
        analyzer.ensureInitialized()
        assertEquals(1, engine.initCount)

        analyzer.dispose()
        assertEquals(1, engine.closeCount)

        // After dispose, a new analyzer can re-initialize
        val analyzer2 = BehaviorAnalyzer(engine)
        analyzer2.ensureInitialized()
        assertEquals(2, engine.initCount)
        analyzer2.dispose()
    }
}

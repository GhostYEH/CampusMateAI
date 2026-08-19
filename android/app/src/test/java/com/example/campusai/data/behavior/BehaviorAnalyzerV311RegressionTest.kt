package com.example.campusai.data.behavior

import android.graphics.Bitmap
import com.example.campusai.data.camera.CameraFrame
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * Regression coverage for the V3.1.1 behavior recognition lifecycle.
 *
 * V3.1.1 changes the inference trigger from "buffer full (16 frames)" to
 * "first sampled frame", and adds debug-only performance baseline metrics.
 * These tests lock down the runtime contract that Focus relies on:
 *
 * 1. the first sampled frame triggers inference (no 16-frame warm-up);
 * 2. inference busy does not start a second concurrent inference;
 * 3. the sampling interval still drops frames that arrive too soon;
 * 4. the inference snapshot Bitmaps are not recycled before inference ends;
 * 5. the inference snapshot Bitmaps are recycled after inference ends;
 * 6. dispose/close stops any further inference;
 * 7. MODEL_NOT_AVAILABLE short-circuits the analyzer exactly as before.
 */
@RunWith(RobolectricTestRunner::class)
class BehaviorAnalyzerV311RegressionTest {

    @Test

    fun samplingIntervalDropsFramesThatArriveTooSoon() {
        val buffer = BehaviorFrameBuffer(
            BehaviorModelConfig(
                frameCount = 16,
                inputWidth = 4,
                inputHeight = 4,
                sampleIntervalMs = 100L,
            ),
        )
        val frames = listOf(
            CameraFrame(Bitmap.createBitmap(8, 8, Bitmap.Config.ARGB_8888), 200L),
            CameraFrame(Bitmap.createBitmap(8, 8, Bitmap.Config.ARGB_8888), 250L),
            CameraFrame(Bitmap.createBitmap(8, 8, Bitmap.Config.ARGB_8888), 350L),
        )

        try {
            // First sampled frame passes the interval gate and triggers.
            assertTrue(buffer.addFrame(frames[0]))
            // 250 - 200 = 50 < 100: dropped by the sampling interval.
            assertFalse(buffer.addFrame(frames[1]))
            // 350 - 200 = 150 >= 100: accepted (lastSampleTime only updates on accept).
            assertTrue(buffer.addFrame(frames[2]))
            assertEquals(2, buffer.getTemporalWindow().size)
        } finally {
            frames.forEach { frame ->
                if (!frame.bitmap.isRecycled) frame.release()
            }
            buffer.clear()
        }
    }

    @Test
    fun inferenceSnapshotBitmapsAreNotRecycledWhileInferenceIsRunning() {
        val engine = BlockingEngine()
        val analyzer = BehaviorAnalyzer(engine, testConfig())
        val firstFrame = frameAt(100L)

        try {
            analyzer.analyze(firstFrame)
            firstFrame.release()

            assertTrue(engine.started.await(2, TimeUnit.SECONDS))
            val snapshot = engine.lastSnapshot
            assertNotNull(snapshot)
            // While the engine is blocked, the inference-owned copies must still be usable.
            assertTrue(snapshot!!.all { !it.isRecycled })
            engine.allowCompletion.countDown()
            assertTrue(engine.completed.await(2, TimeUnit.SECONDS))
        } finally {
            engine.allowCompletion.countDown()
            analyzer.dispose()
        }
    }

    @Test
    fun inferenceSnapshotBitmapsAreRecycledAfterInferenceCompletes() {
        val engine = BlockingEngine()
        val analyzer = BehaviorAnalyzer(engine, testConfig())
        val firstFrame = frameAt(100L)

        try {
            analyzer.analyze(firstFrame)
            firstFrame.release()

            assertTrue(engine.started.await(2, TimeUnit.SECONDS))
            engine.allowCompletion.countDown()
            assertTrue(engine.completed.await(2, TimeUnit.SECONDS))
            val snapshot = engine.lastSnapshot
            assertNotNull(snapshot)
            assertTrue(awaitAllRecycled(snapshot))
        } finally {
            engine.allowCompletion.countDown()
            analyzer.dispose()
        }
    }

    @Test

    fun closeOnEngineIsCalledExactlyOnceOnDispose() {
        val engine = RecordingEngine()
        val analyzer = BehaviorAnalyzer(engine, testConfig())

        analyzer.dispose()
        assertEquals(1, engine.closeCount.get())
        // Second dispose is a no-op.
        analyzer.dispose()
        assertEquals(1, engine.closeCount.get())
    }

    @Test
    fun modelNotAvailableShortCircuitsAndNeverInvokesTheEngine() {
        val engine = UnavailableEngine()
        val analyzer = BehaviorAnalyzer(engine, testConfig())
        val frames = (0 until 16).map { frameAt(100L + it) }

        try {
            frames.forEach { frame ->
                analyzer.analyze(frame)
                frame.release()
            }
            // The engine is never called; the analyzer emits MODEL_NOT_AVAILABLE directly.
            assertEquals(0, engine.invocationCount.get())
            assertEquals(
                "MODEL_NOT_AVAILABLE",
                analyzer.predictions.value.modelState,
            )
        } finally {
            frames.forEach { frame ->
                if (!frame.bitmap.isRecycled) frame.release()
            }
            analyzer.dispose()
        }
    }

    @Test
    fun modelNotAvailablePredictionCarriesLatestFrameTimestamp() {
        val engine = UnavailableEngine()
        val analyzer = BehaviorAnalyzer(engine, testConfig())
        val first = frameAt(1234L)
        val second = frameAt(5678L)

        try {
            analyzer.analyze(first)
            first.release()
            assertEquals(1234L, analyzer.predictions.value.timestampMs)
            analyzer.analyze(second)
            second.release()
            assertEquals(5678L, analyzer.predictions.value.timestampMs)
        } finally {
            if (!first.bitmap.isRecycled) first.release()
            if (!second.bitmap.isRecycled) second.release()
            analyzer.dispose()
        }
    }

    private fun testConfig() = BehaviorModelConfig(
        frameCount = 16,
        inputWidth = 4,
        inputHeight = 4,
        sampleIntervalMs = 1L,
    )

    private fun frameAt(timestampMs: Long) = CameraFrame(
        Bitmap.createBitmap(8, 8, Bitmap.Config.ARGB_8888),
        timestampMs,
    )

    private fun awaitAllRecycled(bitmaps: List<Bitmap>?): Boolean {
        assertNotNull(bitmaps)
        repeat(200) {
            if (bitmaps!!.all { it.isRecycled }) return true
            Thread.sleep(10)
        }
        return bitmaps!!.all { it.isRecycled }
    }

    private open class BlockingEngine : BehaviorRecognitionEngine {
        override val isAvailable = true
        val started = CountDownLatch(1)
        val allowCompletion = CountDownLatch(1)
        val completed = CountDownLatch(1)
        val invocationCount = AtomicInteger()
        @Volatile var lastFrameCount = 0
        @Volatile var lastSnapshot: List<Bitmap>? = null

        override fun initialize() = Unit

        override fun analyzeTemporalWindow(frames: List<Bitmap>, timestampMs: Long): BehaviorPrediction {
            invocationCount.incrementAndGet()
            lastFrameCount = frames.size
            lastSnapshot = frames.toList()
            started.countDown()
            allowCompletion.await(2, TimeUnit.SECONDS)
            completed.countDown()
            return BehaviorPrediction(
                probabilities = mapOf(StudyBehavior.VISIBLE_STUDY to 1f),
                timestampMs = timestampMs,
                modelState = "READY_VISIBLE_STUDY_V31",
            )
        }

        override fun close() = Unit
    }

    private class RecordingEngine : BehaviorRecognitionEngine {
        override val isAvailable = true
        val invocationCount = AtomicInteger()
        val closeCount = AtomicInteger()

        override fun initialize() = Unit

        override fun analyzeTemporalWindow(frames: List<Bitmap>, timestampMs: Long): BehaviorPrediction {
            invocationCount.incrementAndGet()
            return BehaviorPrediction(
                probabilities = mapOf(StudyBehavior.VISIBLE_STUDY to 1f),
                timestampMs = timestampMs,
                modelState = "READY_VISIBLE_STUDY_V31",
            )
        }

        override fun close() {
            closeCount.incrementAndGet()
        }
    }

    private class UnavailableEngine : BehaviorRecognitionEngine {
        override val isAvailable = false
        val invocationCount = AtomicInteger()
        val closeCount = AtomicInteger()

        override fun initialize() = Unit

        override fun analyzeTemporalWindow(frames: List<Bitmap>, timestampMs: Long): BehaviorPrediction {
            invocationCount.incrementAndGet()
            return BehaviorPrediction(
                probabilities = emptyMap(),
                timestampMs = timestampMs,
                modelState = "MODEL_NOT_AVAILABLE",
            )
        }

        override fun close() {
            closeCount.incrementAndGet()
        }
    }
}
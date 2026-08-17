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

@RunWith(RobolectricTestRunner::class)
class BehaviorAnalyzerTest {
    @Test
    fun frameBufferKeepsSixteenFrameWindowAndRecyclesEvictedFrame() {
        val buffer = BehaviorFrameBuffer(
            BehaviorModelConfig(
                frameCount = 16,
                inputWidth = 4,
                inputHeight = 4,
                sampleIntervalMs = 1L,
            ),
        )
        val frames = (0 until 17).map { frameAt(100L + it) }

        try {
            frames.take(15).forEach { frame ->
                assertFalse(buffer.addFrame(frame))
                frame.release()
            }
            val sixteenth = frames[15]
            assertTrue(buffer.addFrame(sixteenth))
            sixteenth.release()
            assertEquals(16, buffer.getTemporalWindow().size)
            val evicted = buffer.getTemporalWindow().first()

            val seventeenth = frames[16]
            assertTrue(buffer.addFrame(seventeenth))
            seventeenth.release()

            assertEquals(16, buffer.getTemporalWindow().size)
            assertTrue(evicted.isRecycled)
            val retained = buffer.getTemporalWindow()
            buffer.clear()
            assertTrue(retained.all { it.isRecycled })
        } finally {
            frames.forEach { frame ->
                if (!frame.bitmap.isRecycled) frame.release()
            }
            buffer.clear()
        }
    }

    @Test
    fun analyzerDoesNotInferBeforeSixteenFramesAndInfersAfterWindowIsReady() {
        val engine = BlockingEngine()
        val analyzer = BehaviorAnalyzer(engine, testConfig())
        val frames = (0 until 16).map { frameAt(100L + it) }

        try {
            frames.take(15).forEach { frame ->
                analyzer.analyze(frame)
                frame.release()
            }
            assertEquals(0, engine.invocationCount.get())
            assertFalse(engine.started.await(100, TimeUnit.MILLISECONDS))

            analyzer.analyze(frames[15])
            frames[15].release()

            assertTrue(engine.started.await(2, TimeUnit.SECONDS))
            assertEquals(1, engine.invocationCount.get())
            assertEquals(16, engine.lastFrameCount)
            engine.allowCompletion.countDown()
            assertTrue(engine.completed.await(2, TimeUnit.SECONDS))
            assertTrue(awaitAllRecycled(engine.lastSnapshot))
        } finally {
            engine.allowCompletion.countDown()
            analyzer.dispose()
        }
    }

    @Test
    fun analyzerDoesNotScheduleAnotherInferenceWhileBusy() {
        val engine = BlockingEngine()
        val analyzer = BehaviorAnalyzer(engine, testConfig())
        val frames = (0 until 32).map { frameAt(100L + it) }

        try {
            frames.forEach { frame ->
                analyzer.analyze(frame)
                frame.release()
            }

            assertTrue(engine.started.await(2, TimeUnit.SECONDS))
            assertEquals(1, engine.invocationCount.get())
            engine.allowCompletion.countDown()
            assertTrue(engine.completed.await(2, TimeUnit.SECONDS))
            Thread.sleep(50)
            assertEquals(1, engine.invocationCount.get())
        } finally {
            engine.allowCompletion.countDown()
            analyzer.dispose()
        }
    }

    @Test
    fun analyzerRecoversAfterEngineExceptionAndCanInferAgain() {
        val engine = ThrowOnceEngine()
        val analyzer = BehaviorAnalyzer(engine, testConfig())
        val frames = (0 until 17).map { frameAt(100L + it) }

        try {
            frames.take(16).forEach { frame ->
                analyzer.analyze(frame)
                frame.release()
            }
            assertTrue(engine.firstStarted.await(2, TimeUnit.SECONDS))
            assertTrue(engine.firstFinished.await(2, TimeUnit.SECONDS))
            assertEquals("INFERENCE_ERROR", analyzer.predictions.value.modelState)
            assertTrue(awaitAllRecycled(engine.firstSnapshot))

            analyzer.analyze(frames[16])
            frames[16].release()
            assertTrue(engine.secondFinished.await(2, TimeUnit.SECONDS))

            assertEquals(2, engine.invocationCount.get())
            assertTrue(awaitPredictionState(analyzer, "READY_VISIBLE_STUDY_V31"))
        } finally {
            analyzer.dispose()
        }
    }

    @Test
    fun disposeReleasesResourcesAndIgnoresFramesAfterLifecycleEnd() {
        val engine = BlockingEngine()
        val analyzer = BehaviorAnalyzer(engine, testConfig())
        val frames = (0 until 15).map { frameAt(100L + it) }

        try {
            frames.forEach { frame ->
                analyzer.analyze(frame)
                frame.release()
            }
            analyzer.dispose()
            assertEquals(1, engine.closeCount.get())

            val afterDispose = (0 until 16).map { frameAt(500L + it) }
            try {
                afterDispose.forEach { frame ->
                    analyzer.analyze(frame)
                    frame.release()
                }
            } finally {
                afterDispose.forEach { frame ->
                    if (!frame.bitmap.isRecycled) frame.release()
                }
            }
            assertEquals(0, engine.invocationCount.get())
        } finally {
            engine.allowCompletion.countDown()
            analyzer.dispose()
        }
        assertEquals(1, engine.closeCount.get())
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

    private fun awaitPredictionState(analyzer: BehaviorAnalyzer, expected: String): Boolean {
        repeat(200) {
            if (analyzer.predictions.value.modelState == expected) return true
            Thread.sleep(10)
        }
        return analyzer.predictions.value.modelState == expected
    }

    private class BlockingEngine : BehaviorRecognitionEngine {
        override val isAvailable = true
        val started = CountDownLatch(1)
        val allowCompletion = CountDownLatch(1)
        val completed = CountDownLatch(1)
        val invocationCount = AtomicInteger()
        val closeCount = AtomicInteger()
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

        override fun close() {
            closeCount.incrementAndGet()
        }
    }

    private class ThrowOnceEngine : BehaviorRecognitionEngine {
        override val isAvailable = true
        val firstStarted = CountDownLatch(1)
        val firstFinished = CountDownLatch(1)
        val secondFinished = CountDownLatch(1)
        val invocationCount = AtomicInteger()
        @Volatile var firstSnapshot: List<Bitmap>? = null

        override fun initialize() = Unit

        override fun analyzeTemporalWindow(frames: List<Bitmap>, timestampMs: Long): BehaviorPrediction {
            val invocation = invocationCount.incrementAndGet()
            if (invocation == 1) {
                firstSnapshot = frames.toList()
                firstStarted.countDown()
                firstFinished.countDown()
                error("synthetic inference failure")
            }
            secondFinished.countDown()
            return BehaviorPrediction(
                probabilities = mapOf(StudyBehavior.VISIBLE_STUDY to 1f),
                timestampMs = timestampMs,
                modelState = "READY_VISIBLE_STUDY_V31",
            )
        }

        override fun close() = Unit
    }
}

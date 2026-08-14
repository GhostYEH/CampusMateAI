package com.example.campusai.data.behavior

import android.graphics.Bitmap
import com.example.campusai.data.camera.CameraFrame
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class BehaviorAnalyzerTest {
    @Test
    fun firstFrameRunsV1InferenceWithOneLiveSnapshot() {
        val engine = BlockingEngine()
        val analyzer = BehaviorAnalyzer(engine)
        val source = Bitmap.createBitmap(8, 8, Bitmap.Config.ARGB_8888)
        val frame = CameraFrame(source, 100L)

        try {
            analyzer.analyze(frame)
            frame.release()
            assertTrue(engine.started.await(2, TimeUnit.SECONDS))
            assertEquals(1, engine.invocationCount.get())
            assertEquals(1, engine.lastFrameCount)
            assertTrue(source.isRecycled)
            assertFalse(engine.lastSnapshot!!.isRecycled)

            engine.allowCompletion.countDown()
            assertTrue(engine.completed.await(2, TimeUnit.SECONDS))
            assertTrue(awaitRecycled(engine.lastSnapshot!!))
        } finally {
            engine.allowCompletion.countDown()
            analyzer.dispose()
        }
    }

    @Test
    fun busyInferenceDoesNotQueueAdditionalFramesAndDisposeClosesEngine() {
        val engine = BlockingEngine()
        val analyzer = BehaviorAnalyzer(engine)
        val first = frameAt(100L)
        try {
            analyzer.analyze(first)
            first.release()
            assertTrue(engine.started.await(2, TimeUnit.SECONDS))

            val second = frameAt(200L)
            analyzer.analyze(second)
            second.release()
            val third = frameAt(300L)
            analyzer.analyze(third)
            third.release()
            assertEquals(1, engine.invocationCount.get())

            engine.allowCompletion.countDown()
            assertTrue(engine.completed.await(2, TimeUnit.SECONDS))
        } finally {
            engine.allowCompletion.countDown()
            analyzer.dispose()
        }
        assertEquals(1, engine.closeCount.get())
    }

    private fun frameAt(timestampMs: Long) = CameraFrame(
        Bitmap.createBitmap(8, 8, Bitmap.Config.ARGB_8888),
        timestampMs,
    )

    private fun awaitRecycled(bitmap: Bitmap): Boolean {
        repeat(100) {
            if (bitmap.isRecycled) return true
            Thread.sleep(10)
        }
        return bitmap.isRecycled
    }

    private class BlockingEngine : BehaviorRecognitionEngine {
        override val isAvailable = true
        val started = CountDownLatch(1)
        val allowCompletion = CountDownLatch(1)
        val completed = CountDownLatch(1)
        val invocationCount = AtomicInteger()
        val closeCount = AtomicInteger()
        @Volatile var lastFrameCount = 0
        @Volatile var lastSnapshot: Bitmap? = null

        override fun initialize() = Unit

        override fun analyzeTemporalWindow(frames: List<Bitmap>, timestampMs: Long): BehaviorPrediction {
            invocationCount.incrementAndGet()
            lastFrameCount = frames.size
            lastSnapshot = frames.single()
            started.countDown()
            allowCompletion.await(2, TimeUnit.SECONDS)
            completed.countDown()
            return BehaviorPrediction(
                mapOf(StudyBehavior.READING to .9f, StudyBehavior.WRITING to .1f),
                timestampMs,
                "READY_RGB_V1",
            )
        }

        override fun close() {
            closeCount.incrementAndGet()
        }
    }
}

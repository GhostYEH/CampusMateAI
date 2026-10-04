package com.example.campusai.data.behavior

import android.graphics.Bitmap
import android.graphics.RectF
import androidx.test.core.app.ApplicationProvider
import com.example.campusai.data.camera.CameraFrame
import java.util.concurrent.ExecutorService
import java.util.concurrent.TimeUnit
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.kotlin.any
import org.mockito.kotlin.mock
import org.mockito.kotlin.verify
import org.mockito.kotlin.times
import org.mockito.kotlin.whenever
import org.robolectric.RobolectricTestRunner
import org.tensorflow.lite.support.image.TensorImage
import org.tensorflow.lite.support.label.Category
import org.tensorflow.lite.task.vision.detector.Detection
import org.tensorflow.lite.task.vision.detector.ObjectDetector

@RunWith(RobolectricTestRunner::class)
class PersonAnalyzerTest {
    @Test
    fun firstEpochTimestampRunsDetectionAndSubsequentFramesAreThrottled() {
        val detector = mock<ObjectDetector>()
        whenever(detector.detect(any<TensorImage>())).thenReturn(emptyList())
        val analyzer = readyAnalyzer(detector)
        val firstTimestamp = 1_700_000_000_000L
        try {
            analyzeFrame(analyzer, firstTimestamp)
            assertEquals(firstTimestamp, analyzer.snapshot.value.timestampMs)
            analyzeFrame(analyzer, firstTimestamp + 100L)
            verify(detector, times(1)).detect(any<TensorImage>())
            analyzeFrame(analyzer, firstTimestamp + 500L)
            verify(detector, times(2)).detect(any<TensorImage>())
        } finally {
            analyzer.close()
        }
    }

    @Test
    fun backwardWallClockStepRunsDetectionAndStartsANewThrottleInterval() {
        val detector = mock<ObjectDetector>()
        whenever(detector.detect(any<TensorImage>())).thenReturn(emptyList())
        val analyzer = readyAnalyzer(detector)
        val firstTimestamp = 1_700_000_000_000L
        val adjustedTimestamp = firstTimestamp - 60_000L
        try {
            analyzeFrame(analyzer, firstTimestamp)
            analyzeFrame(analyzer, adjustedTimestamp)
            verify(detector, times(2)).detect(any<TensorImage>())
            assertEquals(adjustedTimestamp, analyzer.snapshot.value.timestampMs)
            analyzeFrame(analyzer, adjustedTimestamp + 100L)
            verify(detector, times(2)).detect(any<TensorImage>())
            analyzeFrame(analyzer, adjustedTimestamp + 500L)
            verify(detector, times(3)).detect(any<TensorImage>())
        } finally {
            analyzer.close()
        }
    }

    @Test
    fun highestConfidencePersonPopulatesTheSnapshotAndIgnoresOtherObjects() {
        val bestBox = RectF(1f, 0f, 4f, 4f)
        val detector = mock<ObjectDetector>()
        whenever(detector.detect(any<TensorImage>())).thenReturn(
            listOf(
                detection("person", 0.61f, RectF(0f, 0f, 2f, 3f)),
                detection("PERSON", 0.92f, bestBox),
                detection("chair", 0.99f, RectF(0f, 0f, 4f, 4f)),
            ),
        )
        val analyzer = readyAnalyzer(detector)
        try {
            analyzeFrame(analyzer, 1_700_000_000_000L)
            val snapshot = analyzer.snapshot.value
            assertEquals(PersonDetectorStatus.RUNNING, snapshot.status)
            assertTrue(snapshot.personDetected)
            assertEquals(0.92f, snapshot.personConfidence!!, 0.0001f)
            assertEquals(bestBox, snapshot.boundingBox)
        } finally {
            analyzer.close()
        }
    }

    private fun detection(label: String, score: Float, box: RectF): Detection {
        val category = mock<Category>()
        whenever(category.label).thenReturn(label)
        whenever(category.score).thenReturn(score)
        return mock<Detection>().also {
            whenever(it.categories).thenReturn(listOf(category))
            whenever(it.boundingBox).thenReturn(box)
        }
    }

    private fun readyAnalyzer(detector: ObjectDetector): PersonAnalyzer {
        val analyzer = PersonAnalyzer(ApplicationProvider.getApplicationContext())
        // Bypass native model loading, while exercising the real analyze scheduler.
        PersonAnalyzer::class.java.getDeclaredField("detector").apply {
            isAccessible = true
            set(analyzer, detector)
        }
        PersonAnalyzer::class.java.getDeclaredField("initialized").apply {
            isAccessible = true
            setBoolean(analyzer, true)
        }
        analyzer.start()
        return analyzer
    }

    private fun analyzeFrame(analyzer: PersonAnalyzer, timestampMs: Long) {
        val frame = CameraFrame(Bitmap.createBitmap(4, 4, Bitmap.Config.ARGB_8888), timestampMs)
        try {
            analyzer.analyze(frame)
            // Wait through the executor's finally block so throttle assertions cannot
            // accidentally pass just because the preceding inference is still busy.
            val executor = PersonAnalyzer::class.java.getDeclaredField("executor").run {
                isAccessible = true
                get(analyzer) as ExecutorService
            }
            executor.submit {}.get(2, TimeUnit.SECONDS)
        } finally {
            frame.release()
        }
    }
}

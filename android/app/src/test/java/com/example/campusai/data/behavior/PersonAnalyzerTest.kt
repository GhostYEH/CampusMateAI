package com.example.campusai.data.behavior

import android.graphics.Bitmap
import androidx.test.core.app.ApplicationProvider
import com.example.campusai.data.camera.CameraFrame
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.kotlin.any
import org.mockito.kotlin.doAnswer
import org.mockito.kotlin.mock
import org.mockito.kotlin.verify
import org.mockito.kotlin.times
import org.robolectric.RobolectricTestRunner
import org.tensorflow.lite.support.image.TensorImage
import org.tensorflow.lite.task.vision.detector.ObjectDetector

@RunWith(RobolectricTestRunner::class)
class PersonAnalyzerTest {
    @Test
    fun firstEpochTimestampRunsDetectionAndSubsequentFramesAreThrottled() {
        val analyzed = CountDownLatch(1)
        val detector = mock<ObjectDetector>()
        doAnswer {
            analyzed.countDown()
            emptyList<org.tensorflow.lite.task.vision.detector.Detection>()
        }.`when`(detector).detect(any<TensorImage>())
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
        val first = CameraFrame(Bitmap.createBitmap(4, 4, Bitmap.Config.ARGB_8888), 1_700_000_000_000L)
        val tooSoon = CameraFrame(Bitmap.createBitmap(4, 4, Bitmap.Config.ARGB_8888), first.timestampMs + 100L)
        try {
            analyzer.analyze(first)
            assertTrue("the first frame must not be skipped due to Long overflow", analyzed.await(2, TimeUnit.SECONDS))
            analyzer.analyze(tooSoon)
            verify(detector, times(1)).detect(any<TensorImage>())
        } finally {
            first.release()
            tooSoon.release()
            analyzer.close()
        }
    }
}

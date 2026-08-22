package com.example.campusai

import com.example.campusai.data.expression.ExpressionPerformanceStats
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ExpressionPerformanceStatsTest {
    @Test
    fun snapshotReportsPercentilesRatesAndDropCounts() {
        val stats = ExpressionPerformanceStats()
        stats.start(1_000L)
        stats.recordFrame(
            faceDetectionMs = 10,
            preprocessMs = 4,
            inferenceMs = 2,
            postprocessMs = 1,
            totalLatencyMs = 20,
            noFace = false,
            unknown = false,
        )
        stats.recordFrame(
            faceDetectionMs = 30,
            preprocessMs = 8,
            inferenceMs = 4,
            postprocessMs = 2,
            totalLatencyMs = 50,
            noFace = true,
            unknown = false,
        )
        stats.recordFrame(
            faceDetectionMs = 20,
            preprocessMs = 6,
            inferenceMs = 3,
            postprocessMs = 2,
            totalLatencyMs = 35,
            noFace = false,
            unknown = true,
        )
        stats.recordDroppedFrame()

        val snapshot = stats.snapshot(2_000L)

        assertEquals(3L, snapshot.processedFrames)
        assertEquals(1L, snapshot.droppedFrames)
        assertEquals(35.0, snapshot.totalLatencyAverageMs, 0.001)
        assertEquals(35.0, snapshot.totalLatencyP50Ms, 0.001)
        assertEquals(50.0, snapshot.totalLatencyP95Ms, 0.001)
        assertEquals(3.0, snapshot.fps, 0.001)
        assertEquals(1.0 / 3.0, snapshot.noFaceRate, 0.001)
        assertEquals(1.0 / 3.0, snapshot.unknownRate, 0.001)
        assertTrue(snapshot.sessionDurationMs >= 1_000L)
    }
}

package com.example.campusai.data.behavior

import android.graphics.Bitmap
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class HybridBehaviorRecognitionEngineTest {
    @Test
    fun singleFrameRunsEveryCallWhileTemporalRunsAtLowCadence() {
        val single = FakeEngine(singlePrediction())
        val temporal = FakeEngine(temporalPrediction(StudyBehavior.PHONE_USE))
        val hybrid = HybridBehaviorRecognitionEngine(single, temporal)
        hybrid.initialize()

        try {
            repeat(8) { index -> hybrid.analyzeTemporalWindow(listOf(frame()), index * 500L) }
            assertEquals(8, single.calls)
            assertEquals(1, temporal.calls)
            assertEquals(BehaviorTsmContract.INPUT_FRAME_COUNT, temporal.lastFrameCount)

            repeat(5) { index -> hybrid.analyzeTemporalWindow(listOf(frame()), 4_000L + index * 500L) }
            assertEquals(13, single.calls)
            assertEquals(1, temporal.calls)

            hybrid.analyzeTemporalWindow(listOf(frame()), 6_500L)
            assertEquals(2, temporal.calls)
        } finally {
            hybrid.close()
        }
    }

    @Test
    fun computerBecomesStableOnlyAfterTwoTemporalChecks() {
        val single = FakeEngine(singlePrediction())
        val temporal = FakeEngine(temporalPrediction(StudyBehavior.COMPUTER))
        val hybrid = HybridBehaviorRecognitionEngine(single, temporal)
        hybrid.initialize()

        try {
            var result = singlePrediction()
            repeat(8) { index -> result = hybrid.analyzeTemporalWindow(listOf(frame()), index * 500L) }
            assertFalse(result.stableBehavior == StudyBehavior.COMPUTER)

            repeat(6) { index -> result = hybrid.analyzeTemporalWindow(listOf(frame()), 4_000L + index * 500L) }
            assertEquals(StudyBehavior.COMPUTER, result.stableBehavior)
            assertEquals(BehaviorHybridPolicy.MODEL_STATE, result.modelState)
        } finally {
            hybrid.close()
        }
    }

    @Test
    fun unavailableTsmLeavesV34PredictionUntouched() {
        val expected = singlePrediction()
        val single = FakeEngine(expected)
        val temporal = FakeEngine(temporalPrediction(StudyBehavior.PHONE_USE), available = false)
        val hybrid = HybridBehaviorRecognitionEngine(single, temporal)
        hybrid.initialize()

        try {
            val result = hybrid.analyzeTemporalWindow(listOf(frame()), 5_000L)
            assertEquals(expected.probabilities, result.probabilities)
            assertEquals(expected.modelState, result.modelState)
            assertEquals(5_000L, result.timestampMs)
            assertEquals(0, temporal.calls)
            assertTrue(hybrid.isAvailable)
        } finally {
            hybrid.close()
        }
    }

    @Test
    fun v32FallbackBypassesIncompatibleTemporalFusion() {
        val expected = BehaviorPrediction(
            probabilities = mapOf(
                StudyBehavior.IDLE to 0.15f,
                StudyBehavior.VISIBLE_STUDY to 0.85f,
            ),
            timestampMs = 0L,
            modelState = "READY_VISIBLE_STUDY_V32",
        )
        val single = FakeEngine(expected)
        val temporal = FakeEngine(temporalPrediction(StudyBehavior.IDLE))
        val hybrid = HybridBehaviorRecognitionEngine(single, temporal)
        hybrid.initialize()

        try {
            var result = expected
            repeat(12) { index ->
                result = hybrid.analyzeTemporalWindow(listOf(frame()), index * 500L)
            }

            assertEquals(expected.probabilities, result.probabilities)
            assertEquals(expected.modelState, result.modelState)
            assertEquals(0, temporal.calls)
        } finally {
            hybrid.close()
        }
    }

    @Test
    fun v32FallbackClearsStaleTemporalEvidenceBeforeV34Resumes() {
        val single = FakeEngine(singlePrediction())
        val temporal = FakeEngine(temporalPrediction(StudyBehavior.PHONE_USE))
        val hybrid = HybridBehaviorRecognitionEngine(single, temporal)
        hybrid.initialize()

        try {
            repeat(8) { index ->
                hybrid.analyzeTemporalWindow(listOf(frame()), index * 500L)
            }
            assertEquals(1, temporal.calls)

            single.result = BehaviorPrediction(
                probabilities = mapOf(
                    StudyBehavior.IDLE to 0.20f,
                    StudyBehavior.VISIBLE_STUDY to 0.80f,
                ),
                timestampMs = 0L,
                modelState = "READY_VISIBLE_STUDY_V32",
            )
            hybrid.analyzeTemporalWindow(listOf(frame()), 4_000L)

            single.result = singlePrediction()
            val resumed = hybrid.analyzeTemporalWindow(listOf(frame()), 4_500L)

            assertEquals(BehaviorV34Contract.MODEL_STATE, resumed.modelState)
            assertEquals(StudyBehavior.IDLE, resumed.stableBehavior)
            assertEquals(1, temporal.calls)
        } finally {
            hybrid.close()
        }
    }

    @Test
    fun latestTemporalEvidenceStaysActiveBetweenTsmRuns() {
        val single = FakeEngine(
            BehaviorPrediction(
                probabilities = mapOf(
                    StudyBehavior.READING to 0.55f,
                    StudyBehavior.WRITING to 0.03f,
                    StudyBehavior.PHONE_USE to 0.40f,
                    StudyBehavior.IDLE to 0.02f,
                ),
                timestampMs = 0L,
                modelState = BehaviorV34Contract.MODEL_STATE,
                stableBehavior = StudyBehavior.READING,
            ),
        )
        val temporal = FakeEngine(temporalPrediction(StudyBehavior.PHONE_USE))
        val hybrid = HybridBehaviorRecognitionEngine(single, temporal)
        hybrid.initialize()

        try {
            var result = singlePrediction()
            repeat(8) { index -> result = hybrid.analyzeTemporalWindow(listOf(frame()), index * 500L) }
            assertEquals(StudyBehavior.PHONE_USE, result.stableBehavior)

            result = hybrid.analyzeTemporalWindow(listOf(frame()), 4_000L)
            assertEquals(1, temporal.calls)
            assertEquals(StudyBehavior.PHONE_USE, result.stableBehavior)
            assertEquals(BehaviorHybridPolicy.MODEL_STATE, result.modelState)
        } finally {
            hybrid.close()
        }
    }

    @Test
    fun resetDropsStaleFramesBeforeAResumedSession() {
        val single = FakeEngine(singlePrediction())
        val temporal = FakeEngine(temporalPrediction(StudyBehavior.PHONE_USE))
        val hybrid = HybridBehaviorRecognitionEngine(single, temporal)
        hybrid.initialize()

        try {
            repeat(8) { index -> hybrid.analyzeTemporalWindow(listOf(frame()), index * 500L) }
            assertEquals(1, temporal.calls)

            hybrid.reset()
            repeat(7) { index -> hybrid.analyzeTemporalWindow(listOf(frame()), 10_000L + index * 500L) }
            assertEquals(1, temporal.calls)
        } finally {
            hybrid.close()
        }
    }

    private fun frame() = Bitmap.createBitmap(4, 4, Bitmap.Config.ARGB_8888)

    private fun singlePrediction() = BehaviorPrediction(
        probabilities = mapOf(
            StudyBehavior.READING to 0.05f,
            StudyBehavior.WRITING to 0.05f,
            StudyBehavior.PHONE_USE to 0.10f,
            StudyBehavior.IDLE to 0.80f,
        ),
        timestampMs = 0L,
        modelState = BehaviorV34Contract.MODEL_STATE,
        stableBehavior = StudyBehavior.IDLE,
    )

    private fun temporalPrediction(top: StudyBehavior): BehaviorPrediction {
        val probabilities = BehaviorTsmContract.outputBehaviors.associateWith { behavior ->
            if (behavior == top) 0.90f else 0.025f
        }
        return BehaviorPrediction(probabilities, 0L, BehaviorTsmContract.MODEL_STATE, top)
    }

    private class FakeEngine(
        var result: BehaviorPrediction,
        private val available: Boolean = true,
    ) : BehaviorRecognitionEngine {
        var calls = 0
        var lastFrameCount = 0
        override val isAvailable: Boolean get() = available

        override fun initialize() = Unit

        override fun analyzeTemporalWindow(
            frames: List<Bitmap>,
            timestampMs: Long,
        ): BehaviorPrediction {
            calls++
            lastFrameCount = frames.size
            return result.copy(timestampMs = timestampMs)
        }

        override fun close() = Unit
    }
}

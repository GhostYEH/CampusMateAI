package com.example.campusai.data.behavior

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BehaviorPredictionTemporalSmootherTest {
    @Test
    fun firstPredictionPassesThroughWithoutWarmupDelay() {
        val smoother = BehaviorPredictionTemporalSmoother(
            BehaviorSmoothingConfig(emaAlpha = 0.35f),
        )
        val raw = prediction(
            idle = 0.2f,
            visibleStudy = 0.8f,
        )

        val result = smoother.smooth(raw)

        assertEquals(raw.probabilities, result.probabilities)
        assertEquals(raw.timestampMs, result.timestampMs)
        assertEquals(raw.modelState, result.modelState)
    }

    @Test
    fun oppositeProbabilitySpikeIsDampened() {
        val smoother = BehaviorPredictionTemporalSmoother(
            BehaviorSmoothingConfig(emaAlpha = 0.35f),
        )
        smoother.smooth(prediction(idle = 0.1f, visibleStudy = 0.9f))

        val result = smoother.smooth(prediction(idle = 0.9f, visibleStudy = 0.1f))
        val visibleStudy = result.probabilities.getValue(StudyBehavior.VISIBLE_STUDY)
        val idle = result.probabilities.getValue(StudyBehavior.IDLE)

        assertEquals(0.62f, visibleStudy, 0.001f)
        assertEquals(0.38f, idle, 0.001f)
        assertTrue("one spike must not immediately invert the smoothed result", visibleStudy > idle)
    }

    @Test
    fun modelStateChangeStartsASeparateSmoothingHistory() {
        val smoother = BehaviorPredictionTemporalSmoother()
        smoother.smooth(prediction(idle = 0.1f, visibleStudy = 0.9f, modelState = "READY_VISIBLE_STUDY_V32"))

        val result = smoother.smooth(
            prediction(
                idle = 0.9f,
                visibleStudy = 0.1f,
                modelState = "READY_VISIBLE_STUDY_V31",
            ),
        )

        assertEquals(0.9f, result.probabilities.getValue(StudyBehavior.IDLE), 0.001f)
        assertEquals(0.1f, result.probabilities.getValue(StudyBehavior.VISIBLE_STUDY), 0.001f)
    }

    @Test
    fun emptyPredictionClearsHistoryBeforeNextFrame() {
        val smoother = BehaviorPredictionTemporalSmoother()
        smoother.smooth(prediction(idle = 0.1f, visibleStudy = 0.9f))
        smoother.smooth(
            BehaviorPrediction(
                probabilities = emptyMap(),
                timestampMs = 2L,
                modelState = "INFERENCE_ERROR",
            ),
        )

        val result = smoother.smooth(prediction(idle = 0.9f, visibleStudy = 0.1f))

        assertEquals(0.9f, result.probabilities.getValue(StudyBehavior.IDLE), 0.001f)
        assertEquals(0.1f, result.probabilities.getValue(StudyBehavior.VISIBLE_STUDY), 0.001f)
    }

    private fun prediction(
        idle: Float,
        visibleStudy: Float,
        modelState: String = "READY_VISIBLE_STUDY_V32",
    ) = BehaviorPrediction(
        probabilities = mapOf(
            StudyBehavior.IDLE to idle,
            StudyBehavior.VISIBLE_STUDY to visibleStudy,
        ),
        timestampMs = 1L,
        modelState = modelState,
    )
}

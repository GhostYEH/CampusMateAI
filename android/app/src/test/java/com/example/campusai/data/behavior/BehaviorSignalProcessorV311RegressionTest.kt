package com.example.campusai.data.behavior

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * V3.1.1 added `debugInferenceLatencyMs` / `debugPreprocessingLatencyMs` to
 * BehaviorPrediction for performance baselining. These fields must not change
 * the product-layer behavior of BehaviorSignalProcessor or
 * LearningContinuityStateMachine, which only consume probabilities/modelState.
 *
 * Each test pairs a prediction without debug fields against one carrying V3.1.1
 * debug latencies and asserts the downstream state is identical.
 */
class BehaviorSignalProcessorV311RegressionTest {

    private val supportedState = "READY_VISIBLE_STUDY_V31"

    @Test
    fun debugLatencyFieldsDoNotChangeWarmupObservingState() {
        val processor = BehaviorSignalProcessor(
            BehaviorSignalConfig(startupWarmupMs = 1500L, stableBehaviorWindowMs = 2000L),
        )
        processor.beginBehaviorObservation(100L)

        val withoutDebug = BehaviorPrediction(
            probabilities = mapOf(StudyBehavior.VISIBLE_STUDY to 0.9f),
            timestampMs = 500L,
            modelState = supportedState,
        )
        val withDebug = BehaviorPrediction(
            probabilities = mapOf(StudyBehavior.VISIBLE_STUDY to 0.9f),
            timestampMs = 500L,
            modelState = supportedState,
            debugInferenceLatencyMs = 42L,
            debugPreprocessingLatencyMs = 7L,
        )

        assertEquals(
            processor.processDisplayState(withoutDebug),
            processor.processDisplayState(withDebug),
        )
    }

    @Test
    fun debugLatencyFieldsDoNotChangeStableStateAfterWarmup() {
        val processor = BehaviorSignalProcessor(
            BehaviorSignalConfig(startupWarmupMs = 1500L, stableBehaviorWindowMs = 2000L),
        )
        processor.beginBehaviorObservation(100L)

        val base = BehaviorPrediction(
            probabilities = mapOf(StudyBehavior.VISIBLE_STUDY to 0.9f),
            timestampMs = 1600L,
            modelState = supportedState,
        )
        val withDebug = base.copy(
            debugInferenceLatencyMs = 42L,
            debugPreprocessingLatencyMs = 7L,
        )

        assertEquals(
            BehaviorDisplayState.Stable(StudyBehavior.VISIBLE_STUDY, 0.9f),
            processor.processDisplayState(base),
        )
        // Reset and replay with debug fields; the stable state must be the same.
        processor.reset()
        processor.beginBehaviorObservation(100L)
        assertEquals(
            BehaviorDisplayState.Stable(StudyBehavior.VISIBLE_STUDY, 0.9f),
            processor.processDisplayState(withDebug),
        )
    }

    @Test
    fun debugLatencyFieldsDoNotChangeEventEmission() {
        val processor = BehaviorSignalProcessor(
            BehaviorSignalConfig(phoneUseThresholdMs = 3000L),
        )

        val withoutDebug = BehaviorPrediction(
            probabilities = mapOf(StudyBehavior.PHONE_USE to 0.8f),
            timestampMs = 5000L,
            modelState = "READY",
        )
        val withDebug = withoutDebug.copy(
            debugInferenceLatencyMs = 42L,
            debugPreprocessingLatencyMs = 7L,
        )

        // Prime the processor past the threshold without debug fields.
        processor.process(
            BehaviorPrediction(
                probabilities = mapOf(StudyBehavior.PHONE_USE to 0.8f),
                timestampMs = 1000L,
                modelState = "READY",
            ),
        )
        val eventsWithoutDebug = processor.process(withoutDebug)

        // Reset and replay with debug fields at the same timestamps.
        processor.reset()
        processor.process(
            BehaviorPrediction(
                probabilities = mapOf(StudyBehavior.PHONE_USE to 0.8f),
                timestampMs = 1000L,
                modelState = "READY",
                debugInferenceLatencyMs = 42L,
                debugPreprocessingLatencyMs = 7L,
            ),
        )
        val eventsWithDebug = processor.process(withDebug)

        assertEquals(eventsWithoutDebug, eventsWithDebug)
    }

    @Test
    fun modelNotAvailablePredictionIsIgnoredRegardlessOfDebugFields() {
        val processor = BehaviorSignalProcessor()
        processor.beginBehaviorObservation(100L)

        val withoutDebug = BehaviorPrediction(
            probabilities = mapOf(StudyBehavior.VISIBLE_STUDY to 0.9f),
            timestampMs = 500L,
            modelState = "MODEL_NOT_AVAILABLE",
        )
        val withDebug = withoutDebug.copy(
            debugInferenceLatencyMs = 42L,
            debugPreprocessingLatencyMs = 7L,
        )

        assertEquals(
            BehaviorDisplayState.Observing,
            processor.processDisplayState(withoutDebug),
        )
        assertEquals(
            BehaviorDisplayState.Observing,
            processor.processDisplayState(withDebug),
        )
    }
}
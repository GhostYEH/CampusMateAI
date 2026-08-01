package com.example.campusai

import com.example.campusai.data.focus.FocusEvent
import com.example.campusai.data.focus.FocusObservation
import com.example.campusai.data.focus.FocusObservationConfig
import com.example.campusai.data.focus.FocusState
import com.example.campusai.data.focus.FocusStateProcessor
import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.ExpressionResult
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FocusStateProcessorTest {
    private val config = FocusObservationConfig(
        noFaceWindowMs = 8_000, headTurnWindowMs = 4_000, lowEyeOpenWindowMs = 2_000,
        reminderCooldownMs = 180_000, headTurnDegrees = 22.0, lowEyeOpenProbability = .28,
    )

    @Test fun noFaceIsOnlyRecordedAfterWindow() {
        val processor = FocusStateProcessor(config)
        assertEquals(FocusState.FOCUSED, processor.process(FocusObservation(0, false)).state)
        assertEquals(FocusState.FOCUSED, processor.process(FocusObservation(7_999, false)).state)
        val output = processor.process(FocusObservation(8_000, false))
        assertEquals(FocusState.NO_FACE, output.state)
        assertTrue(output.events.contains(FocusEvent.NoFaceRecorded))
    }

    @Test fun headTurnNeedsContinuousWindowAndAccumulatesDuration() {
        val processor = FocusStateProcessor(config)
        processor.process(FocusObservation(0, true, headEulerAngleY = 24.0))
        assertEquals(FocusState.FOCUSED, processor.process(FocusObservation(3_999, true, headEulerAngleY = 24.0)).state)
        assertEquals(FocusState.POSSIBLY_DISTRACTED, processor.process(FocusObservation(4_000, true, headEulerAngleY = 24.0)).state)
        processor.process(FocusObservation(6_000, true, headEulerAngleY = 0.0))
        assertEquals(6, processor.finish(6_000, 6, "test").possibleDistractionDurationSeconds)
    }

    @Test fun lowEyesUsesCooldownAndLowConfidenceDoesNotPrompt() {
        val processor = FocusStateProcessor(config)
        processor.process(FocusObservation(0, true, leftEyeOpenProbability = .2, rightEyeOpenProbability = .2))
        val suggested = processor.process(FocusObservation(2_000, true, leftEyeOpenProbability = .2, rightEyeOpenProbability = .2))
        assertEquals(FocusState.BREAK_SUGGESTED, suggested.state)
        assertTrue(suggested.events.contains(FocusEvent.BreakSuggested))
        processor.process(FocusObservation(3_000, true, leftEyeOpenProbability = .8, rightEyeOpenProbability = .8))
        val stillCooling = processor.process(FocusObservation(5_000, true, leftEyeOpenProbability = .2, rightEyeOpenProbability = .2))
        assertFalse(stillCooling.events.contains(FocusEvent.BreakSuggested))
        val unknown = ExpressionResult(ExpressionLabel.UNKNOWN, .2, emptyMap(), 7_000, false, "test", facePresent = true)
        assertEquals(FocusState.UNAVAILABLE, processor.process(FocusObservation(7_000, true, expression = unknown, inferenceAvailable = false)).state)
    }
}

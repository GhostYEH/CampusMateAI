package com.example.campusai

import com.example.campusai.data.expression.ExpressionMath
import com.example.campusai.data.expression.ExpressionSignalConfig
import com.example.campusai.data.expression.ExpressionSignalProcessor
import com.example.campusai.data.model.ExpressionLabel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ExpressionSignalProcessorTest {
    private fun probabilities(
        top: ExpressionLabel,
        confidence: Double,
    ): Map<ExpressionLabel, Double> {
        val remainder = (1.0 - confidence) / (ExpressionMath.modelLabels.size - 1)
        return ExpressionMath.modelLabels.associateWith {
            if (it == top) confidence else remainder
        }
    }

    @Test
    fun lowConfidenceBecomesUnknownAndCannotStabilize() {
        val processor = ExpressionSignalProcessor(
            ExpressionSignalConfig(minimumConfidence = 0.6),
            "test",
        )
        val result = processor.process(probabilities(ExpressionLabel.SAD, 0.45), 1000L)
        assertEquals(ExpressionLabel.UNKNOWN, result.label)
        assertFalse(result.isStable)
        assertFalse(processor.shouldOfferNeutralSuggestion(result, 1000L))
    }

    @Test
    fun repeatedFramesMustMeetCountAndDuration() {
        val processor = ExpressionSignalProcessor(
            ExpressionSignalConfig(
                emaAlpha = 1.0,
                minimumConfidence = 0.5,
                minimumStableFrames = 3,
                minimumStableDurationMs = 500,
            ),
            "test",
        )
        assertFalse(processor.process(probabilities(ExpressionLabel.NEUTRAL, 0.8), 1000).isStable)
        assertFalse(processor.process(probabilities(ExpressionLabel.NEUTRAL, 0.8), 1200).isStable)
        assertFalse(processor.process(probabilities(ExpressionLabel.NEUTRAL, 0.8), 1400).isStable)
        assertTrue(processor.process(probabilities(ExpressionLabel.NEUTRAL, 0.8), 1600).isStable)
    }

    @Test
    fun noFaceAndCooldownAreEnforced() {
        val processor = ExpressionSignalProcessor(
            ExpressionSignalConfig(
                emaAlpha = 1.0,
                minimumConfidence = 0.5,
                minimumStableFrames = 1,
                minimumStableDurationMs = 0,
                suggestionCooldownMs = 1000,
            ),
            "test",
        )
        val stable = processor.process(probabilities(ExpressionLabel.HAPPY, 0.9), 1000)
        assertTrue(stable.isStable)
        assertTrue(processor.shouldOfferNeutralSuggestion(stable, 1000))
        assertFalse(processor.shouldOfferNeutralSuggestion(stable, 1500))
        assertTrue(processor.shouldOfferNeutralSuggestion(stable, 2000))
        val noFace = processor.process(emptyMap(), 2100, hasFace = false)
        assertEquals(ExpressionLabel.NO_FACE, noFace.label)
        assertFalse(noFace.isStable)
    }

    @Test
    fun classSpecificThresholdOverridesGlobalFallback() {
        val processor = ExpressionSignalProcessor(
            ExpressionSignalConfig(
                emaAlpha = 1.0,
                minimumConfidence = 0.7,
                classThresholds = mapOf(
                    ExpressionLabel.HAPPY to 0.3,
                    ExpressionLabel.FEAR to 0.93,
                ),
            ),
            "test",
        )

        val happy = processor.process(probabilities(ExpressionLabel.HAPPY, 0.5), 1000L)
        assertEquals(ExpressionLabel.HAPPY, happy.label)

        processor.reset()
        val fear = processor.process(probabilities(ExpressionLabel.FEAR, 0.8), 1000L)
        assertEquals(ExpressionLabel.UNKNOWN, fear.label)
    }

    @Test
    fun missingClassThresholdsKeepLegacyGlobalThresholdBehavior() {
        val processor = ExpressionSignalProcessor(
            ExpressionSignalConfig(emaAlpha = 1.0, minimumConfidence = 0.7),
            "legacy",
        )

        assertEquals(
            ExpressionLabel.UNKNOWN,
            processor.process(probabilities(ExpressionLabel.HAPPY, 0.6), 1000L).label,
        )
    }
}

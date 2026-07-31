package com.example.campusai

import com.example.campusai.data.expression.ExpressionMath
import com.example.campusai.data.model.ExpressionLabel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ExpressionMathTest {
    @Test
    fun modelLabelOrderMatchesTrainingExportContract() {
        assertEquals(
            listOf(
                ExpressionLabel.ANGRY,
                ExpressionLabel.DISGUST,
                ExpressionLabel.FEAR,
                ExpressionLabel.HAPPY,
                ExpressionLabel.NEUTRAL,
                ExpressionLabel.SAD,
                ExpressionLabel.SURPRISE,
            ),
            ExpressionMath.modelLabels,
        )
    }

    @Test
    fun softmaxIsStableAndSumsToOne() {
        val result = ExpressionMath.softmax(floatArrayOf(1001f, 1000f, 999f))
        assertEquals(1.0, result.sum(), 1e-9)
        assertTrue(result[0] > result[1])
        assertTrue(result[1] > result[2])
    }

    @Test
    fun pixelNormalizationMatchesTrainingFormula() {
        assertEquals(-1f, ExpressionMath.normalizePixel(0, 0.5, 0.5), 1e-6f)
        assertEquals(1f, ExpressionMath.normalizePixel(255, 0.5, 0.5), 1e-6f)
    }
}

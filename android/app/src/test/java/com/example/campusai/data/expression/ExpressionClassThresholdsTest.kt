package com.example.campusai.data.expression

import com.example.campusai.data.model.ExpressionLabel
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(manifest = Config.NONE)
class ExpressionClassThresholdsTest {
    @Test
    fun preservesDisabledClassSentinelAndRegularThresholds() {
        val thresholds = parseExpressionClassThresholds(
            JSONObject("""{"class_thresholds":{"fear":1.01,"happy":0.3}}"""),
        )
        assertEquals(1.01, thresholds.getValue(ExpressionLabel.FEAR), 0.0)
        assertEquals(0.3, thresholds.getValue(ExpressionLabel.HAPPY), 0.0)
    }

    @Test
    fun absentThresholdsKeepGlobalFallback() {
        assertTrue(parseExpressionClassThresholds(JSONObject("{}")).isEmpty())
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsNegativeThresholdRatherThanAcceptingEveryPrediction() {
        parseExpressionClassThresholds(JSONObject("""{"class_thresholds":{"fear":-0.1}}"""))
    }
}

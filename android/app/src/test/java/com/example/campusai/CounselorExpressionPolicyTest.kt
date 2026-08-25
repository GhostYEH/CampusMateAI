package com.example.campusai

import com.example.campusai.data.expression.CounselorExpressionPolicy
import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.ExpressionResult
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CounselorExpressionPolicyTest {
    private fun result(
        label: ExpressionLabel,
        confidence: Double,
        timestamp: Long = 9_500L,
        stable: Boolean = true,
    ) = ExpressionResult(label, confidence, emptyMap(), timestamp, stable, "test")

    @Test fun sadRequiresPrecisionThresholdAndFreshSignal() {
        assertFalse(CounselorExpressionPolicy.isUsable(result(ExpressionLabel.SAD, .67), 10_000L))
        assertTrue(CounselorExpressionPolicy.isUsable(result(ExpressionLabel.SAD, .68), 10_000L))
        assertFalse(CounselorExpressionPolicy.isUsable(result(ExpressionLabel.SAD, .90, 4_999L), 10_000L))
    }

    @Test fun sadGreetingExpressesCareWithoutClaimingCertainty() {
        val greeting = requireNotNull(
            CounselorExpressionPolicy.greeting(result(ExpressionLabel.SAD, .82), 10_000L),
        )

        assertTrue(greeting.contains("可能"))
        assertTrue(greeting.contains("别难过"))
        assertFalse(greeting.contains("你就是"))
    }
}

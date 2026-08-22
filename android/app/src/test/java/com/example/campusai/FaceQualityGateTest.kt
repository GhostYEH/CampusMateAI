package com.example.campusai

import com.example.campusai.data.expression.FaceQualityGate
import com.example.campusai.data.expression.FaceQualityMetrics
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FaceQualityGateTest {
    private val gate = FaceQualityGate(
        FaceQualityGate.Config(
            minimumFaceWidthPx = 100,
            maximumAbsPitchDegrees = 25.0,
            maximumAbsYawDegrees = 25.0,
            maximumAbsRollDegrees = 25.0,
            minimumSharpness = 18.0,
        ),
    )

    @Test
    fun rejectsSmallFacesBeforeInference() {
        val decision = gate.evaluate(
            FaceQualityMetrics(
                faceWidthPx = 80,
                pitchDegrees = 0.0,
                yawDegrees = 0.0,
                rollDegrees = 0.0,
                sharpness = 100.0,
            ),
        )

        assertTrue(!decision.accepted)
        assertEquals(FaceQualityGate.Reason.FACE_TOO_SMALL, decision.reason)
    }

    @Test
    fun rejectsLargeHeadPoseAndBlur() {
        assertEquals(
            FaceQualityGate.Reason.POSE_TOO_LARGE,
            gate.evaluate(FaceQualityMetrics(120, 0.0, 30.0, 0.0, 100.0)).reason,
        )
        assertEquals(
            FaceQualityGate.Reason.TOO_BLURRY,
            gate.evaluate(FaceQualityMetrics(120, 0.0, 0.0, 0.0, 5.0)).reason,
        )
    }

    @Test
    fun acceptsUsableFaceMetrics() {
        val decision = gate.evaluate(FaceQualityMetrics(120, 5.0, -8.0, 4.0, 50.0))

        assertTrue(decision.accepted)
        assertEquals(null, decision.reason)
    }
}

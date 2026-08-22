package com.example.campusai.data.expression

import android.graphics.Bitmap
import com.google.mlkit.vision.face.Face
import kotlin.math.abs
import kotlin.math.max

data class FaceQualityMetrics(
    val faceWidthPx: Int,
    val pitchDegrees: Double,
    val yawDegrees: Double,
    val rollDegrees: Double,
    val sharpness: Double,
)

class FaceQualityGate(
    private val config: Config = Config(),
) {
    data class Config(
        val minimumFaceWidthPx: Int = 100,
        val maximumAbsPitchDegrees: Double = 25.0,
        val maximumAbsYawDegrees: Double = 25.0,
        val maximumAbsRollDegrees: Double = 25.0,
        val minimumSharpness: Double = 18.0,
    )

    enum class Reason {
        FACE_TOO_SMALL,
        POSE_TOO_LARGE,
        TOO_BLURRY,
    }

    data class Decision(
        val accepted: Boolean,
        val reason: Reason? = null,
    )

    fun evaluate(metrics: FaceQualityMetrics): Decision {
        if (metrics.faceWidthPx < config.minimumFaceWidthPx) {
            return Decision(false, Reason.FACE_TOO_SMALL)
        }
        if (
            abs(metrics.pitchDegrees) > config.maximumAbsPitchDegrees ||
            abs(metrics.yawDegrees) > config.maximumAbsYawDegrees ||
            abs(metrics.rollDegrees) > config.maximumAbsRollDegrees
        ) {
            return Decision(false, Reason.POSE_TOO_LARGE)
        }
        if (metrics.sharpness < config.minimumSharpness) {
            return Decision(false, Reason.TOO_BLURRY)
        }
        return Decision(true)
    }

    fun evaluate(face: Face, faceBitmap: Bitmap): Decision = evaluate(
        FaceQualityMetrics(
            faceWidthPx = face.boundingBox.width(),
            pitchDegrees = face.headEulerAngleX.toDouble(),
            yawDegrees = face.headEulerAngleY.toDouble(),
            rollDegrees = face.headEulerAngleZ.toDouble(),
            sharpness = sharpness(faceBitmap),
        ),
    )

    /** A low-cost edge-energy score; it is used only as an abstention gate. */
    fun sharpness(bitmap: Bitmap): Double {
        if (bitmap.width < 2 || bitmap.height < 2) return 0.0
        val stride = max(1, max(bitmap.width, bitmap.height) / 64)
        var energy = 0.0
        var samples = 0
        var y = 0
        while (y + stride < bitmap.height) {
            var x = 0
            while (x + stride < bitmap.width) {
                val current = luminance(bitmap.getPixel(x, y))
                val right = luminance(bitmap.getPixel(x + stride, y))
                val down = luminance(bitmap.getPixel(x, y + stride))
                energy += (current - right) * (current - right)
                energy += (current - down) * (current - down)
                samples += 2
                x += stride
            }
            y += stride
        }
        return if (samples == 0) 0.0 else energy / samples
    }

    private fun luminance(pixel: Int): Double {
        val red = pixel shr 16 and 0xFF
        val green = pixel shr 8 and 0xFF
        val blue = pixel and 0xFF
        return 0.299 * red + 0.587 * green + 0.114 * blue
    }
}

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
    val faceCount: Int = 1,
    val brightness: Double = 128.0,
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
        val minimumBrightness: Double = 40.0,
        val maximumBrightness: Double = 225.0,
    )

    enum class Reason {
        MULTIPLE_FACES,
        FACE_TOO_SMALL,
        POSE_TOO_LARGE,
        TOO_BLURRY,
        UNSAFE_EXPOSURE,
    }

    data class Decision(
        val accepted: Boolean,
        val reason: Reason? = null,
    )

    fun evaluate(metrics: FaceQualityMetrics): Decision {
        if (metrics.faceCount != 1) {
            return Decision(false, Reason.MULTIPLE_FACES)
        }
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
        if (metrics.brightness !in config.minimumBrightness..config.maximumBrightness) {
            return Decision(false, Reason.UNSAFE_EXPOSURE)
        }
        return Decision(true)
    }

    fun evaluate(face: Face, faceBitmap: Bitmap, faceCount: Int = 1): Decision = evaluate(
        FaceQualityMetrics(
            faceWidthPx = face.boundingBox.width(),
            pitchDegrees = face.headEulerAngleX.toDouble(),
            yawDegrees = face.headEulerAngleY.toDouble(),
            rollDegrees = face.headEulerAngleZ.toDouble(),
            sharpness = sharpness(faceBitmap),
            faceCount = faceCount,
            brightness = averageBrightness(faceBitmap),
        ),
    )

    fun averageBrightness(bitmap: Bitmap): Double {
        if (bitmap.width == 0 || bitmap.height == 0) return 0.0
        val stride = max(1, max(bitmap.width, bitmap.height) / 64)
        var total = 0.0
        var samples = 0
        var y = 0
        while (y < bitmap.height) {
            var x = 0
            while (x < bitmap.width) {
                total += luminance(bitmap.getPixel(x, y))
                samples++
                x += stride
            }
            y += stride
        }
        return if (samples == 0) 0.0 else total / samples
    }

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

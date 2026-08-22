package com.example.campusai.data.behavior

import android.graphics.Bitmap
import com.example.campusai.data.camera.CameraFrame
import kotlin.math.abs
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Ignore
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * Compares the two runtime preprocessing paths that reach the ONNX behavior model:
 *
 *   legacy  : camera image -> resize 192x192 -> resize 224x224 -> /255 -> ImageNet norm -> NCHW
 *   direct  : camera image -> resize 224x224 -> /255 -> ImageNet norm -> NCHW
 *
 * Training preprocessing (docs/behavior-recognition.md section 3) is the direct path:
 * resize 224x224, RGB, /255, ImageNet mean/std, NCHW. The legacy path inserts an extra
 * 192x192 downscale that training never did, so legacy is a train/inference mismatch.
 *
 * The tensor test uses a pure-Kotlin bilinear resizer on a synthetic high-frequency
 * checkerboard. It proves only the mathematical fact that the two resize chains produce
 * different input tensors. It does NOT load the ONNX model and does NOT use real camera
 * images (none exist in the repo). Logit / probability / class comparisons need real-
 * device A/B data and are left as a documented placeholder.
 */
@RunWith(RobolectricTestRunner::class)
class BehaviorPreprocessingPathComparisonTest {

    @Test
    fun legacyDoubleResizeProducesDifferentTensorThanDirect224() {
        val source = checkerboardRgb(size = 640, cell = 20)

        val legacyResized = bilinearResizeRgb(
            bilinearResizeRgb(source, 640, 640, LEGACY_INTERMEDIATE, LEGACY_INTERMEDIATE),
            LEGACY_INTERMEDIATE,
            LEGACY_INTERMEDIATE,
            MODEL_SIZE,
            MODEL_SIZE,
        )
        val directResized = bilinearResizeRgb(source, 640, 640, MODEL_SIZE, MODEL_SIZE)

        val legacyTensor = toNchwTensor(legacyResized, MODEL_SIZE, MODEL_SIZE)
        val directTensor = toNchwTensor(directResized, MODEL_SIZE, MODEL_SIZE)

        assertEquals(legacyTensor.size, directTensor.size)

        val maxDiff = maxAbsDiff(legacyTensor, directTensor)
        val meanDiff = meanAbsDiff(legacyTensor, directTensor)
        val differingElements = countDiffering(legacyTensor, directTensor, 1e-4f)

        assertTrue(
            "max abs diff $maxDiff must exceed 0.05; otherwise double resize is a no-op",
            maxDiff > 0.05f,
        )
        assertTrue(
            "mean abs diff $meanDiff must exceed 0.01",
            meanDiff > 0.01f,
        )
        assertTrue(
            "a large fraction of elements should differ; got $differingElements/${legacyTensor.size}",
            differingElements > legacyTensor.size / 4,
        )
    }

    @Test
    fun direct224ConfigReachesFrameBufferWhileLegacyDefaultStays192() {
        val legacyDefault = BehaviorModelConfig()
        assertEquals(192, legacyDefault.inputWidth)
        assertEquals(192, legacyDefault.inputHeight)

        val direct = BehaviorModelConfig.DIRECT_224
        assertEquals(224, direct.inputWidth)
        assertEquals(224, direct.inputHeight)

        val buffer = BehaviorFrameBuffer(direct)
        val frame = CameraFrame(
            Bitmap.createBitmap(640, 480, Bitmap.Config.ARGB_8888),
            1000L,
        )
        try {
            buffer.addFrame(frame)
            val window = buffer.getTemporalWindow()
            assertEquals(1, window.size)
            assertEquals(224, window[0].width)
            assertEquals(224, window[0].height)
        } finally {
            buffer.clear()
            frame.release()
        }
    }

    @Test
    fun legacyConfigStillDoubleResizesThrough192() {
        val legacy = BehaviorModelConfig()
        val buffer = BehaviorFrameBuffer(legacy)
        val frame = CameraFrame(
            Bitmap.createBitmap(640, 480, Bitmap.Config.ARGB_8888),
            1000L,
        )
        try {
            buffer.addFrame(frame)
            val window = buffer.getTemporalWindow()
            assertEquals(1, window.size)
            assertEquals(192, window[0].width)
            assertEquals(192, window[0].height)
        } finally {
            buffer.clear()
            frame.release()
        }
    }

    @Ignore(
        "Needs real front-camera frames + ONNX model + human labels. " +
            "Repo has no real test images; do not fabricate logit/probability/class conclusions. " +
            "Fill in during pre-launch real-person A/B."
    )
    @Test
    fun logitsProbabilityAndPredictedClassDifferBetweenLegacyAndDirect224() {
        // Pre-launch A/B procedure:
        // 1. Capture N real front-camera frames (balanced idle / visible_study).
        // 2. For each frame run OnnxBehaviorRecognitionEngine twice:
        //    - BehaviorModelConfig()        (legacy 192 -> 224)
        //    - BehaviorModelConfig.DIRECT_224 (direct 224)
        // 3. Record per-frame: logits[0..1], softmax(idle, visible_study), argmax class.
        // 4. Compare: top-1 flip count, mean probability shift, agreement with human labels,
        //    and confusion matrices for both paths.
        // 5. Only flip the production construction site to DIRECT_224 if direct is
        //    >= legacy on human-label agreement without regressing confidence calibration.
    }

    private fun checkerboardRgb(size: Int, cell: Int): FloatArray {
        val rgb = FloatArray(size * size * 3)
        for (y in 0 until size) {
            for (x in 0 until size) {
                val on = ((x / cell) + (y / cell)) % 2 == 0
                val value = if (on) 255.0f else 0.0f
                val index = (y * size + x) * 3
                rgb[index] = value
                rgb[index + 1] = value
                rgb[index + 2] = value
            }
        }
        return rgb
    }

    private fun bilinearResizeRgb(
        source: FloatArray,
        srcWidth: Int,
        srcHeight: Int,
        dstWidth: Int,
        dstHeight: Int,
    ): FloatArray {
        val destination = FloatArray(dstHeight * dstWidth * 3)
        val xRatio = (srcWidth - 1).toFloat() / (dstWidth - 1).toFloat()
        val yRatio = (srcHeight - 1).toFloat() / (dstHeight - 1).toFloat()
        for (dstY in 0 until dstHeight) {
            val sourceY = dstY * yRatio
            val y0 = sourceY.toInt()
            val y1 = if (y0 + 1 < srcHeight) y0 + 1 else y0
            val fractionalY = sourceY - y0
            for (dstX in 0 until dstWidth) {
                val sourceX = dstX * xRatio
                val x0 = sourceX.toInt()
                val x1 = if (x0 + 1 < srcWidth) x0 + 1 else x0
                val fractionalX = sourceX - x0
                for (channel in 0 until 3) {
                    val p00 = source[(y0 * srcWidth + x0) * 3 + channel]
                    val p10 = source[(y0 * srcWidth + x1) * 3 + channel]
                    val p01 = source[(y1 * srcWidth + x0) * 3 + channel]
                    val p11 = source[(y1 * srcWidth + x1) * 3 + channel]
                    val top = p00 + (p10 - p00) * fractionalX
                    val bottom = p01 + (p11 - p01) * fractionalX
                    destination[(dstY * dstWidth + dstX) * 3 + channel] =
                        top + (bottom - top) * fractionalY
                }
            }
        }
        return destination
    }

    private fun toNchwTensor(rgb: FloatArray, width: Int, height: Int): FloatArray {
        val pixelCount = width * height
        val tensor = FloatArray(3 * pixelCount)
        for (index in 0 until pixelCount) {
            val red = rgb[index * 3] / 255.0f
            val green = rgb[index * 3 + 1] / 255.0f
            val blue = rgb[index * 3 + 2] / 255.0f
            tensor[index] = (red - MEAN_R) / STD_R
            tensor[pixelCount + index] = (green - MEAN_G) / STD_G
            tensor[2 * pixelCount + index] = (blue - MEAN_B) / STD_B
        }
        return tensor
    }

    private fun maxAbsDiff(a: FloatArray, b: FloatArray): Float {
        var max = 0.0f
        for (i in a.indices) {
            val diff = abs(a[i] - b[i])
            if (diff > max) max = diff
        }
        return max
    }

    private fun meanAbsDiff(a: FloatArray, b: FloatArray): Float {
        var sum = 0.0
        for (i in a.indices) {
            sum += abs(a[i] - b[i])
        }
        return (sum / a.size).toFloat()
    }

    private fun countDiffering(a: FloatArray, b: FloatArray, epsilon: Float): Int {
        var count = 0
        for (i in a.indices) {
            if (abs(a[i] - b[i]) > epsilon) count++
        }
        return count
    }

    private companion object {
        const val MODEL_SIZE = 224
        const val LEGACY_INTERMEDIATE = 192
        const val MEAN_R = 0.485f
        const val MEAN_G = 0.456f
        const val MEAN_B = 0.406f
        const val STD_R = 0.229f
        const val STD_G = 0.224f
        const val STD_B = 0.225f
    }
}

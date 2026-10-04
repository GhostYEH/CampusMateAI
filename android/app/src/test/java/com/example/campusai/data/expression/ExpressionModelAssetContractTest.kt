package com.example.campusai.data.expression

import androidx.test.core.app.ApplicationProvider
import android.app.Application
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.security.MessageDigest

@RunWith(RobolectricTestRunner::class)
@Config(manifest = Config.NONE)
class ExpressionModelAssetContractTest {
    @Test
    fun packagedTenLabelMetadataMatchesLabelsPreprocessingAndModelDigest() {
        val context = ApplicationProvider.getApplicationContext<Application>()
        val metadata = JSONObject(context.assets.open("model_metadata.json").bufferedReader().use { it.readText() })
        val preprocessing = JSONObject(context.assets.open("preprocessing.json").bufferedReader().use { it.readText() })
        val modelBytes = context.assets.open("expression_model.tflite").use { it.readBytes() }
        val labels = context.assets.open("labels.txt").bufferedReader().use { it.readLines().filter(String::isNotBlank) }
        val expectedOrder = listOf(
            "angry", "disgust", "fear", "happy", "neutral", "sad", "surprise",
            "boredom", "confusion", "frustration",
        )
        val metadataOrder = metadata.getJSONArray("output_order")
        val calibration = metadata.getJSONObject("confidence_calibration")
        val scales = calibration.getJSONArray("state_scales")
        val biases = calibration.getJSONArray("state_biases")
        val inputShape = metadata.getJSONArray("input_shape")

        assertEquals(10, metadata.getInt("output_size"))
        assertEquals("logits", metadata.getString("output_type"))
        assertEquals(expectedOrder, List(metadataOrder.length()) { metadataOrder.getString(it) })
        assertEquals(expectedOrder, labels)
        assertEquals(4, metadata.getInt("state_window_frames"))
        assertEquals(5_000L, metadata.getLong("state_window_max_age_ms"))
        val expressionTemperature = calibration.getDouble("expression_temperature")
        assertTrue(expressionTemperature > 0.0)
        assertFalse(expressionTemperature.isInfinite())
        assertEquals(3, scales.length())
        assertEquals(3, biases.length())
        repeat(3) { index ->
            val scale = scales.getDouble(index)
            val bias = biases.getDouble(index)
            assertTrue(scale >= 0.0)
            assertFalse(scale.isNaN() || scale.isInfinite())
            assertFalse(bias.isNaN() || bias.isInfinite())
        }
        assertEquals(listOf(1, 96, 96, 3), List(inputShape.length()) { inputShape.getInt(it) })
        assertEquals("NHWC", preprocessing.getString("input_layout"))
        assertEquals(96, preprocessing.getInt("input_size"))
        assertEquals(3, preprocessing.getInt("input_channels"))
        assertEquals("grayscale_replicated", preprocessing.getString("input_color_mode"))
        assertEquals(metadata.getString("model_version"), preprocessing.getString("model_version"))
        val exportedThresholds = metadata.getJSONObject("class_thresholds")
        val preprocessingThresholds = preprocessing.getJSONObject("class_thresholds")
        expectedOrder.take(7).forEach { label ->
            assertEquals(exportedThresholds.getDouble(label), preprocessingThresholds.getDouble(label), 0.0)
        }
        assertEquals(modelBytes.size, metadata.getInt("model_size_bytes"))
        assertEquals(metadata.getString("model_sha256"), sha256(modelBytes))
    }

    private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes)
        .joinToString("") { "%02x".format(it.toInt() and 0xff) }
}

package com.example.campusai.data.expression

import android.content.Context
import android.graphics.Bitmap
import com.example.campusai.data.model.ExpressionLabel
import org.json.JSONObject
import org.tensorflow.lite.Interpreter
import java.io.Closeable
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.channels.FileChannel

data class ExpressionPreprocessing(
    val inputSize: Int,
    val inputChannels: Int,
    val inputColorMode: String,
    val mean: DoubleArray,
    val std: DoubleArray,
    val confidenceThreshold: Double,
    val modelVersion: String,
)

class ExpressionModelRunner(
    private val context: Context,
    private val modelAsset: String = "expression_model.tflite",
    private val preprocessingAsset: String = "preprocessing.json",
) : Closeable {
    lateinit var preprocessing: ExpressionPreprocessing
        private set
    private var interpreter: Interpreter? = null

    fun initialize() {
        if (interpreter != null) return
        preprocessing = readPreprocessing()
        val descriptor = context.assets.openFd(modelAsset)
        val mapped = descriptor.createInputStream().channel.use { channel ->
            channel.map(FileChannel.MapMode.READ_ONLY, descriptor.startOffset, descriptor.declaredLength)
        }
        descriptor.close()
        interpreter = Interpreter(mapped, Interpreter.Options().apply { setNumThreads(4) })
        validateModelContract()
    }

    fun run(faceBitmap: Bitmap): Map<ExpressionLabel, Double> {
        val config = preprocessing
        val resized = Bitmap.createScaledBitmap(
            faceBitmap,
            config.inputSize,
            config.inputSize,
            true,
        )
        val input = ByteBuffer.allocateDirect(
            4 * config.inputSize * config.inputSize * config.inputChannels,
        ).order(ByteOrder.nativeOrder())
        val pixels = IntArray(config.inputSize * config.inputSize)
        resized.getPixels(pixels, 0, config.inputSize, 0, 0, config.inputSize, config.inputSize)
        for (pixel in pixels) {
            val red = pixel shr 16 and 0xFF
            val green = pixel shr 8 and 0xFF
            val blue = pixel and 0xFF
            val grayscale = (0.299 * red + 0.587 * green + 0.114 * blue).toInt()
            if (config.inputChannels == 1) {
                input.putFloat(ExpressionMath.normalizePixel(grayscale, config.mean[0], config.std[0]))
            } else {
                // The FER-style training pipeline converts grayscale source images
                // to 3 identical channels before ImageNet normalization. Keep the
                // camera path identical instead of leaking RGB information that
                // was never seen during training.
                val values = if (config.inputColorMode == "grayscale_replicated") {
                    IntArray(config.inputChannels) { grayscale }
                } else {
                    intArrayOf(red, green, blue)
                }
                repeat(config.inputChannels) { channel ->
                    input.putFloat(
                        ExpressionMath.normalizePixel(
                            values[channel],
                            config.mean[channel],
                            config.std[channel],
                        ),
                    )
                }
            }
        }
        if (resized !== faceBitmap) resized.recycle()
        input.rewind()
        val output = Array(1) { FloatArray(ExpressionMath.modelLabels.size) }
        checkNotNull(interpreter) { "Expression model is not initialized" }.run(input, output)
        return ExpressionMath.toProbabilityMap(ExpressionMath.softmax(output[0]))
    }

    override fun close() {
        interpreter?.close()
        interpreter = null
    }

    private fun readPreprocessing(): ExpressionPreprocessing {
        val json = context.assets.open(preprocessingAsset).bufferedReader().use { it.readText() }
        val root = JSONObject(json)
        val meanJson = root.getJSONArray("mean")
        val stdJson = root.getJSONArray("std")
        return ExpressionPreprocessing(
            inputSize = root.getInt("input_size"),
            inputChannels = root.getInt("input_channels"),
            inputColorMode = root.optString(
                "input_color_mode",
                if (root.getInt("input_channels") == 1) "grayscale" else "rgb",
            ),
            mean = DoubleArray(meanJson.length()) { meanJson.getDouble(it) },
            std = DoubleArray(stdJson.length()) { stdJson.getDouble(it) },
            confidenceThreshold = root.getDouble("confidence_threshold"),
            modelVersion = root.getString("model_version"),
        )
    }

    private fun validateModelContract() {
        val loaded = checkNotNull(interpreter)
        val inputTensor = loaded.getInputTensor(0)
        val outputTensor = loaded.getOutputTensor(0)
        check(inputTensor.dataType() == org.tensorflow.lite.DataType.FLOAT32) {
            "Expression model input must be FLOAT32, got ${inputTensor.dataType()}"
        }
        check(outputTensor.dataType() == org.tensorflow.lite.DataType.FLOAT32) {
            "Expression model output must be FLOAT32, got ${outputTensor.dataType()}"
        }
        check(inputTensor.shape().contentEquals(intArrayOf(1, preprocessing.inputSize, preprocessing.inputSize, preprocessing.inputChannels))) {
            "Expression model input shape does not match preprocessing metadata"
        }
        check(outputTensor.shape().contentEquals(intArrayOf(1, ExpressionMath.modelLabels.size))) {
            "Expression model output shape does not match the class contract"
        }
        check(preprocessing.mean.size == preprocessing.inputChannels &&
            preprocessing.std.size == preprocessing.inputChannels) {
            "Preprocessing mean/std length does not match input channels"
        }
    }
}

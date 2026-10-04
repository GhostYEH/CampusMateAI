package com.example.campusai.data.expression

import android.content.Context
import android.graphics.Bitmap
import android.os.SystemClock
import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.LearningStateLabel
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
    val classThresholds: Map<ExpressionLabel, Double>,
    val modelVersion: String,
    val outputSize: Int = 7,
    val outputOrder: List<String> = emptyList(),
    val outputType: String = "probabilities",
    val expressionTemperature: Double = 1.0,
    val stateScales: DoubleArray = doubleArrayOf(1.0, 1.0, 1.0),
    val stateBiases: DoubleArray = doubleArrayOf(0.0, 0.0, 0.0),
    val stateWindowFrames: Int = 4,
    val stateWindowMaxAgeMs: Long = 5_000L,
)

data class ExpressionModelRun(
    val probabilities: Map<ExpressionLabel, Double>,
    val learningStateLogits: FloatArray = floatArrayOf(),
    val preprocessMs: Long,
    val inferenceMs: Long,
    val postprocessMs: Long,
)

internal fun parseExpressionClassThresholds(root: JSONObject): Map<ExpressionLabel, Double> {
    val json = root.optJSONObject("class_thresholds") ?: return emptyMap()
    return ExpressionMath.modelLabels.mapNotNull { label ->
        val key = label.name.lowercase(java.util.Locale.US)
        if (!json.has(key)) {
            null
        } else {
            val threshold = json.getDouble(key)
            require(threshold.isFinite() && threshold >= 0.0) {
                "Expression class threshold must be finite and non-negative: $key"
            }
            // Calibration uses values above 1 to disable classes with insufficient precision.
            label to threshold
        }
    }.toMap()
}

class ExpressionModelRunner(
    private val context: Context,
    private val modelAsset: String = "expression_model.tflite",
    private val preprocessingAsset: String = "preprocessing.json",
    private val metadataAsset: String = "model_metadata.json",
) : Closeable {
    lateinit var preprocessing: ExpressionPreprocessing
        private set
    private var interpreter: Interpreter? = null
    private var inputBuffer: ByteBuffer? = null
    private var pixelsBuffer: IntArray? = null
    private var outputBuffer: Array<FloatArray>? = null

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
        return runTimed(faceBitmap).probabilities
    }

    fun runTimed(faceBitmap: Bitmap): ExpressionModelRun {
        val config = preprocessing
        val preprocessStartedAt = SystemClock.elapsedRealtimeNanos()
        val resized = Bitmap.createScaledBitmap(
            faceBitmap,
            config.inputSize,
            config.inputSize,
            true,
        )
        val input = inputBuffer ?: ByteBuffer.allocateDirect(
            4 * config.inputSize * config.inputSize * config.inputChannels,
        ).order(ByteOrder.nativeOrder()).also { inputBuffer = it }
        input.clear()
        val pixels = pixelsBuffer ?: IntArray(config.inputSize * config.inputSize).also { pixelsBuffer = it }
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
                repeat(config.inputChannels) { channel ->
                    val value = if (config.inputColorMode == "grayscale_replicated") {
                        grayscale
                    } else {
                        when (channel) {
                            0 -> red
                            1 -> green
                            else -> blue
                        }
                    }
                    input.putFloat(
                        ExpressionMath.normalizePixel(
                            value,
                            config.mean[channel],
                            config.std[channel],
                        ),
                    )
                }
            }
        }
        if (resized !== faceBitmap) resized.recycle()
        input.rewind()
        val preprocessMs = elapsedMs(preprocessStartedAt)

        val inferenceStartedAt = SystemClock.elapsedRealtimeNanos()
        val output = outputBuffer ?: Array(1) { FloatArray(preprocessing.outputSize) }
            .also { outputBuffer = it }
        output[0].fill(0f)
        checkNotNull(interpreter) { "Expression model is not initialized" }.run(input, output)
        val inferenceMs = elapsedMs(inferenceStartedAt)

        val postprocessStartedAt = SystemClock.elapsedRealtimeNanos()
        val expressionLogits = output[0].copyOfRange(0, ExpressionMath.modelLabels.size)
        val probabilities = ExpressionMath.toProbabilityMap(
            ExpressionMath.calibratedExpressionProbabilities(expressionLogits, config.expressionTemperature),
        )
        val stateLogits = if (config.outputSize == TEN_OUTPUTS) {
            output[0].copyOfRange(ExpressionMath.modelLabels.size, TEN_OUTPUTS)
        } else {
            floatArrayOf()
        }
        return ExpressionModelRun(
            probabilities = probabilities,
            learningStateLogits = stateLogits,
            preprocessMs = preprocessMs,
            inferenceMs = inferenceMs,
            postprocessMs = elapsedMs(postprocessStartedAt),
        )
    }

    override fun close() {
        interpreter?.close()
        interpreter = null
        inputBuffer = null
        pixelsBuffer = null
        outputBuffer = null
    }

    private fun readPreprocessing(): ExpressionPreprocessing {
        val json = context.assets.open(preprocessingAsset).bufferedReader().use { it.readText() }
        val root = JSONObject(json)
        val metadata = runCatching {
            context.assets.open(metadataAsset).bufferedReader().use { JSONObject(it.readText()) }
        }.getOrNull()
        val meanJson = root.getJSONArray("mean")
        val stdJson = root.getJSONArray("std")
        val outputSize = metadata?.optInt("output_size", ExpressionMath.modelLabels.size)
            ?: ExpressionMath.modelLabels.size
        val expectedOrder = (ExpressionMath.modelLabels.map { it.name.lowercase(java.util.Locale.US) } +
            ExpressionMath.learningStateLabels.map { it.name.lowercase(java.util.Locale.US) })
        val outputOrder = metadata?.optJSONArray("output_order")?.let { array ->
            List(array.length()) { array.getString(it) }
        }.orEmpty()
        val calibration = metadata?.optJSONObject("confidence_calibration")
        if (outputSize == TEN_OUTPUTS) {
            require(metadata != null && calibration != null &&
                calibration.has("expression_temperature") && calibration.has("state_scales") &&
                calibration.has("state_biases") && metadata.has("output_order") &&
                metadata.has("output_type") && metadata.has("state_window_frames") &&
                metadata.has("state_window_max_age_ms")) {
                "Ten-output model metadata is missing its output or confidence calibration contract"
            }
        }
        val classThresholds = if (outputSize == TEN_OUTPUTS) {
            metadata?.let(::parseExpressionClassThresholds).orEmpty().ifEmpty {
                parseExpressionClassThresholds(root)
            }
        } else {
            parseExpressionClassThresholds(root).ifEmpty {
                metadata?.let(::parseExpressionClassThresholds).orEmpty()
            }
        }
        val expressionTemperature = calibration?.optDouble("expression_temperature", 1.0) ?: 1.0
        val stateScales = calibration?.optJSONArray("state_scales")?.let { values ->
            DoubleArray(values.length()) { values.getDouble(it) }
        } ?: doubleArrayOf(1.0, 1.0, 1.0)
        val stateBiases = calibration?.optJSONArray("state_biases")?.let { values ->
            DoubleArray(values.length()) { values.getDouble(it) }
        } ?: doubleArrayOf(0.0, 0.0, 0.0)
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
            classThresholds = classThresholds,
            modelVersion = metadata?.optString("model_version")?.takeIf { !it.isNullOrBlank() }
                ?: root.getString("model_version"),
            outputSize = outputSize,
            outputOrder = outputOrder.ifEmpty { if (outputSize == ExpressionMath.modelLabels.size) expectedOrder.take(7) else emptyList() },
            outputType = metadata?.optString("output_type", if (outputSize == TEN_OUTPUTS) "logits" else "probabilities")
                ?: if (outputSize == TEN_OUTPUTS) "logits" else "probabilities",
            expressionTemperature = expressionTemperature,
            stateScales = stateScales,
            stateBiases = stateBiases,
            stateWindowFrames = metadata?.optInt("state_window_frames", 4) ?: 4,
            stateWindowMaxAgeMs = metadata?.optLong("state_window_max_age_ms", 5_000L) ?: 5_000L,
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
        check(preprocessing.outputSize in setOf(ExpressionMath.modelLabels.size, TEN_OUTPUTS)) {
            "Expression model output_size must be 7 (legacy) or 10"
        }
        check(outputTensor.shape().contentEquals(intArrayOf(1, preprocessing.outputSize))) {
            "Expression model output shape does not match the class contract"
        }
        if (preprocessing.outputSize == TEN_OUTPUTS) {
            val expectedOrder = ExpressionMath.modelLabels.map { it.name.lowercase(java.util.Locale.US) } +
                ExpressionMath.learningStateLabels.map { it.name.lowercase(java.util.Locale.US) }
            check(preprocessing.outputType == "logits" && preprocessing.outputOrder == expectedOrder) {
                "Ten-output model metadata must declare the fixed ten-label raw-logit order"
            }
            check(preprocessing.stateWindowFrames == DEFAULT_STATE_WINDOW_FRAMES &&
                preprocessing.stateWindowMaxAgeMs == DEFAULT_STATE_WINDOW_MAX_AGE_MS) {
                "Ten-output state window metadata is invalid"
            }
            check(preprocessing.expressionTemperature.isFinite() && preprocessing.expressionTemperature > 0.0 &&
                preprocessing.stateScales.size == ExpressionMath.learningStateLabels.size &&
                preprocessing.stateBiases.size == ExpressionMath.learningStateLabels.size &&
                preprocessing.stateScales.all { it.isFinite() && it >= 0.0 } &&
                preprocessing.stateBiases.all { it.isFinite() }) {
                "Ten-output confidence calibration metadata is invalid"
            }
        }
        check(preprocessing.mean.size == preprocessing.inputChannels &&
            preprocessing.std.size == preprocessing.inputChannels) {
            "Preprocessing mean/std length does not match input channels"
        }
    }

    private fun elapsedMs(startedAtNanos: Long): Long =
        ((SystemClock.elapsedRealtimeNanos() - startedAtNanos) / 1_000_000L).coerceAtLeast(0L)

    private companion object {
        const val TEN_OUTPUTS = 10
        const val DEFAULT_STATE_WINDOW_FRAMES = 4
        const val DEFAULT_STATE_WINDOW_MAX_AGE_MS = 5_000L
    }
}

package com.example.campusai.data.behavior

import android.content.Context
import android.graphics.Bitmap
import android.util.Log
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer

/**
 * V1 RGB behavior recognition engine.
 *
 * Model:
 *   ResNet18
 *   input  = [1, 3, 224, 224] float32 NCHW RGB
 *   output = [1, 2] logits
 *
 * Classes:
 *   0 = read
 *   1 = write
 *
 * V1 is intentionally single-frame:
 * BehaviorAnalyzer may provide a temporal window, but this engine
 * uses only the newest frame.
 */
class OnnxBehaviorRecognitionEngine(
    private val context: Context,
) : BehaviorRecognitionEngine {

    private var environment: OrtEnvironment? = null
    private var session: OrtSession? = null
    private var inputTensor: OnnxTensor? = null
    private var inputBuffer: FloatBuffer? = null

    private val pixelBuffer = IntArray(PIXEL_COUNT)

    @Volatile
    private var ready = false

    override val isAvailable: Boolean
        get() = ready

    @Synchronized
    override fun initialize() {
        if (ready) {
            return
        }

        var createdSession: OrtSession? = null
        var createdTensor: OnnxTensor? = null

        try {
            val env = environment ?: OrtEnvironment.getEnvironment().also {
                environment = it
            }
            val modelFile = ensureModelFile()

            createdSession =
                env.createSession(modelFile.absolutePath)

            val buffer = ByteBuffer
                .allocateDirect(INPUT_FLOAT_COUNT * Float.SIZE_BYTES)
                .order(ByteOrder.nativeOrder())
                .asFloatBuffer()

            createdTensor = OnnxTensor.createTensor(
                env,
                buffer,
                INPUT_SHAPE,
            )

            session = createdSession
            inputBuffer = buffer
            inputTensor = createdTensor

            ready = true

            Log.i(
                TAG,
                "RGB behavior model initialized. " +
                    "inputs=${createdSession.inputNames}, " +
                    "outputs=${createdSession.outputNames}",
            )
        } catch (error: Throwable) {
            ready = false

            try {
                createdTensor?.close()
            } catch (_: Throwable) {
            }

            try {
                createdSession?.close()
            } catch (_: Throwable) {
            }

            session = null
            inputTensor = null
            inputBuffer = null

            Log.e(
                TAG,
                "Failed to initialize RGB behavior model",
                error,
            )
        }
    }

    @Synchronized
    override fun analyzeTemporalWindow(
        frames: List<Bitmap>,
        timestampMs: Long,
    ): BehaviorPrediction {

        if (!ready) {
            return BehaviorPrediction(
                probabilities = emptyMap(),
                timestampMs = timestampMs,
                modelState = "MODEL_NOT_AVAILABLE",
            )
        }

        val frame = frames.lastOrNull()
            ?: return BehaviorPrediction(
                probabilities = emptyMap(),
                timestampMs = timestampMs,
                modelState = "NO_FRAME",
            )

        val currentSession = session
            ?: return unavailablePrediction(timestampMs)

        val currentTensor = inputTensor
            ?: return unavailablePrediction(timestampMs)

        return try {
            preprocess(frame)

            currentSession.run(
                mapOf(INPUT_NAME to currentTensor),
            ).use { result ->

                val outputTensor =
                    result.get(0) as OnnxTensor

                val logits =
                    outputTensor.floatBuffer
                        ?: error("RGB model output is not float")

                if (logits.remaining() < 2) {
                    error(
                        "Expected 2 logits, got ${logits.remaining()}",
                    )
                }

                val readLogit = logits.get(0)
                val writeLogit = logits.get(1)

                val probabilities =
                    BehaviorModelMath.softmax2(
                        readLogit,
                        writeLogit,
                    )

                BehaviorPrediction(
                    probabilities = mapOf(
                        StudyBehavior.READING to probabilities[0],
                        StudyBehavior.WRITING to probabilities[1],
                    ),
                    timestampMs = timestampMs,
                    modelState = "READY_RGB_V1",
                )
            }
        } catch (error: Throwable) {
            Log.e(
                TAG,
                "RGB behavior inference failed",
                error,
            )

            BehaviorPrediction(
                probabilities = emptyMap(),
                timestampMs = timestampMs,
                modelState = "INFERENCE_ERROR",
            )
        }
    }

    /**
     * Reproduces Python validation preprocessing:
     *
     * RGB
     * resize 224x224
     * uint8 / 255
     * ImageNet normalization
     * NCHW
     */
    private fun preprocess(bitmap: Bitmap) {
        val buffer = inputBuffer
            ?: error("Input buffer is unavailable")

        val scaled = Bitmap.createScaledBitmap(
            bitmap,
            INPUT_WIDTH,
            INPUT_HEIGHT,
            true,
        )

        try {
            scaled.getPixels(
                pixelBuffer,
                0,
                INPUT_WIDTH,
                0,
                0,
                INPUT_WIDTH,
                INPUT_HEIGHT,
            )

            for (index in 0 until PIXEL_COUNT) {
                val pixel = pixelBuffer[index]

                val red =
                    ((pixel ushr 16) and 0xFF) / 255.0f

                val green =
                    ((pixel ushr 8) and 0xFF) / 255.0f

                val blue =
                    (pixel and 0xFF) / 255.0f

                buffer.put(
                    index,
                    (red - MEAN_R) / STD_R,
                )

                buffer.put(
                    PIXEL_COUNT + index,
                    (green - MEAN_G) / STD_G,
                )

                buffer.put(
                    (2 * PIXEL_COUNT) + index,
                    (blue - MEAN_B) / STD_B,
                )
            }
        } finally {
            // createScaledBitmap may return the original bitmap.
            // BehaviorAnalyzer owns/recycles that original, so never
            // recycle it here.
            if (scaled !== bitmap && !scaled.isRecycled) {
                scaled.recycle()
            }
        }
    }

    /**
     * Assets are inside the APK. Copy once to app-private storage
     * so ORT can open the model by filesystem path without allocating
     * another ~43 MB byte[] on every initialization.
     */
    private fun ensureModelFile(): File {
        val directory = File(
            context.noBackupFilesDir,
            "behavior_models",
        )

        if (!directory.exists() && !directory.mkdirs()) {
            error(
                "Could not create behavior model directory: $directory",
            )
        }

        val modelFile = File(
            directory,
            INTERNAL_MODEL_FILENAME,
        )

        if (
            modelFile.isFile &&
            modelFile.length() > 0L
        ) {
            return modelFile
        }

        val temporaryFile = File(
            directory,
            "$INTERNAL_MODEL_FILENAME.tmp",
        )

        context.assets.open(ASSET_PATH).use { input ->
            temporaryFile.outputStream().use { output ->
                input.copyTo(output)
            }
        }

        if (modelFile.exists()) {
            modelFile.delete()
        }

        if (!temporaryFile.renameTo(modelFile)) {
            temporaryFile.copyTo(
                modelFile,
                overwrite = true,
            )
            temporaryFile.delete()
        }

        return modelFile
    }

    private fun unavailablePrediction(
        timestampMs: Long,
    ): BehaviorPrediction {
        return BehaviorPrediction(
            probabilities = emptyMap(),
            timestampMs = timestampMs,
            modelState = "MODEL_NOT_AVAILABLE",
        )
    }

    @Synchronized
    override fun close() {
        ready = false

        try {
            inputTensor?.close()
        } catch (error: Throwable) {
            Log.w(TAG, "Failed closing input tensor", error)
        }

        try {
            session?.close()
        } catch (error: Throwable) {
            Log.w(TAG, "Failed closing ORT session", error)
        }

        inputTensor = null
        inputBuffer = null
        session = null
    }

    companion object {
        private const val TAG =
            "OnnxBehaviorEngine"

        private const val ASSET_PATH =
            "models/behavior/rgb_resnet18.onnx"

        // Change this filename when replacing the model in a future V2.
        private const val INTERNAL_MODEL_FILENAME =
            "rgb_resnet18_v1.onnx"

        private const val INPUT_NAME =
            "input"

        private const val INPUT_WIDTH =
            224

        private const val INPUT_HEIGHT =
            224

        private const val PIXEL_COUNT =
            INPUT_WIDTH * INPUT_HEIGHT

        private const val INPUT_FLOAT_COUNT =
            3 * PIXEL_COUNT

        private val INPUT_SHAPE =
            longArrayOf(1, 3, INPUT_HEIGHT.toLong(), INPUT_WIDTH.toLong())

        private const val MEAN_R = 0.485f
        private const val MEAN_G = 0.456f
        private const val MEAN_B = 0.406f

        private const val STD_R = 0.229f
        private const val STD_G = 0.224f
        private const val STD_B = 0.225f
    }
}

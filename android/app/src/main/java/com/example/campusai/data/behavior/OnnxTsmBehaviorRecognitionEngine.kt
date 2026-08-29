package com.example.campusai.data.behavior

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import ai.onnxruntime.TensorInfo
import android.content.Context
import android.graphics.Bitmap
import android.util.Log
import com.example.campusai.BuildConfig
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer

/** Eight-frame TSM MobileNetV2 runtime. Input normalization is embedded in ONNX. */
class OnnxTsmBehaviorRecognitionEngine(private val context: Context) : BehaviorRecognitionEngine {
    private var environment: OrtEnvironment? = null
    private var session: OrtSession? = null
    private var inputTensor: OnnxTensor? = null
    private var inputBuffer: FloatBuffer? = null
    private val pixelBuffer = IntArray(PIXEL_COUNT)
    @Volatile private var ready = false

    override val isAvailable: Boolean get() = ready

    @Synchronized
    override fun initialize() {
        if (ready) return
        closeSession()
        try {
            val env = environment ?: OrtEnvironment.getEnvironment().also { environment = it }
            val loadedSession = env.createSession(ensureModelFile().absolutePath)
            validateContract(loadedSession)
            session = loadedSession
            val buffer = ByteBuffer.allocateDirect(INPUT_FLOAT_COUNT * Float.SIZE_BYTES)
                .order(ByteOrder.nativeOrder())
                .asFloatBuffer()
            inputBuffer = buffer
            inputTensor = OnnxTensor.createTensor(env, buffer, INPUT_SHAPE)
            ready = true
            Log.i(TAG, "TSM behavior model initialized")
        } catch (error: Throwable) {
            ready = false
            closeSession()
            Log.w(TAG, "TSM unavailable; V3.4 remains active", error)
        }
    }

    @Synchronized
    override fun analyzeTemporalWindow(
        frames: List<Bitmap>,
        timestampMs: Long,
    ): BehaviorPrediction {
        if (!ready) return BehaviorPrediction(emptyMap(), timestampMs, "MODEL_NOT_AVAILABLE")
        if (frames.size != BehaviorTsmContract.INPUT_FRAME_COUNT) {
            return BehaviorPrediction(emptyMap(), timestampMs, "TSM_NEEDS_8_FRAMES")
        }
        val activeSession = session ?: return BehaviorPrediction(emptyMap(), timestampMs, "MODEL_NOT_AVAILABLE")
        val tensor = inputTensor ?: return BehaviorPrediction(emptyMap(), timestampMs, "MODEL_NOT_AVAILABLE")
        return try {
            val preprocessStart = if (BuildConfig.DEBUG) System.currentTimeMillis() else 0L
            preprocess(frames)
            val preprocessLatency = if (BuildConfig.DEBUG) System.currentTimeMillis() - preprocessStart else -1L
            val inferenceStart = if (BuildConfig.DEBUG) System.currentTimeMillis() else 0L
            activeSession.run(mapOf(INPUT_NAME to tensor)).use { output ->
                val logitsBuffer = (output.get(0) as OnnxTensor).floatBuffer
                    ?: error("TSM output is not float")
                require(logitsBuffer.remaining() >= OUTPUT_SIZE) {
                    "Expected $OUTPUT_SIZE TSM logits, got ${logitsBuffer.remaining()}"
                }
                val probabilities = BehaviorTsmContract.decode(
                    FloatArray(OUTPUT_SIZE) { logitsBuffer.get(it) },
                )
                val top = probabilities.maxByOrNull { it.value }?.key ?: StudyBehavior.UNCERTAIN
                BehaviorPrediction(
                    probabilities = probabilities,
                    timestampMs = timestampMs,
                    modelState = BehaviorTsmContract.MODEL_STATE,
                    stableBehavior = top,
                    debugInferenceLatencyMs = if (BuildConfig.DEBUG) {
                        System.currentTimeMillis() - inferenceStart
                    } else -1L,
                    debugPreprocessingLatencyMs = preprocessLatency,
                )
            }
        } catch (error: Throwable) {
            Log.e(TAG, "TSM inference failed", error)
            BehaviorPrediction(emptyMap(), timestampMs, "INFERENCE_ERROR")
        }
    }

    private fun preprocess(frames: List<Bitmap>) {
        val buffer = inputBuffer ?: error("TSM input buffer is unavailable")
        frames.forEachIndexed { frameIndex, bitmap ->
            val scaled = Bitmap.createScaledBitmap(bitmap, INPUT_WIDTH, INPUT_HEIGHT, true)
            try {
                scaled.getPixels(pixelBuffer, 0, INPUT_WIDTH, 0, 0, INPUT_WIDTH, INPUT_HEIGHT)
                val frameOffset = frameIndex * CHANNELS * PIXEL_COUNT
                for (pixelIndex in 0 until PIXEL_COUNT) {
                    val pixel = pixelBuffer[pixelIndex]
                    buffer.put(frameOffset + pixelIndex, ((pixel ushr 16) and 0xFF).toFloat())
                    buffer.put(frameOffset + PIXEL_COUNT + pixelIndex, ((pixel ushr 8) and 0xFF).toFloat())
                    buffer.put(frameOffset + 2 * PIXEL_COUNT + pixelIndex, (pixel and 0xFF).toFloat())
                }
            } finally {
                if (scaled !== bitmap && !scaled.isRecycled) scaled.recycle()
            }
        }
    }

    private fun validateContract(loadedSession: OrtSession) {
        val input = loadedSession.inputInfo[INPUT_NAME]?.info as? TensorInfo
            ?: error("Missing TSM input '$INPUT_NAME'")
        require(input.shape.size == INPUT_SHAPE.size && input.shape.drop(1) == INPUT_SHAPE.drop(1)) {
            "Unexpected TSM input shape ${input.shape.contentToString()}"
        }
        val output = loadedSession.outputInfo[OUTPUT_NAME]?.info as? TensorInfo
            ?: error("Missing TSM output '$OUTPUT_NAME'")
        require(output.shape.size == 2 && output.shape.last() == OUTPUT_SIZE.toLong()) {
            "Unexpected TSM output shape ${output.shape.contentToString()}"
        }
    }

    private fun ensureModelFile(): File {
        val directory = File(context.noBackupFilesDir, "behavior_models")
        if (!directory.exists() && !directory.mkdirs()) error("Could not create $directory")
        val modelFile = File(directory, INTERNAL_FILENAME)
        if (modelFile.isFile && modelFile.length() == EXPECTED_FILE_SIZE) return modelFile
        val temporary = File(directory, "$INTERNAL_FILENAME.tmp")
        context.assets.open(ASSET_PATH).use { input ->
            temporary.outputStream().use { output -> input.copyTo(output) }
        }
        require(temporary.length() == EXPECTED_FILE_SIZE) {
            "Unexpected TSM asset size ${temporary.length()}"
        }
        if (modelFile.exists()) modelFile.delete()
        if (!temporary.renameTo(modelFile)) {
            temporary.copyTo(modelFile, overwrite = true)
            temporary.delete()
        }
        return modelFile
    }

    @Synchronized
    override fun close() {
        ready = false
        closeSession()
    }

    private fun closeSession() {
        try { inputTensor?.close() } catch (error: Throwable) { Log.w(TAG, "Failed closing TSM input", error) }
        try { session?.close() } catch (error: Throwable) { Log.w(TAG, "Failed closing TSM session", error) }
        inputTensor = null
        inputBuffer = null
        session = null
    }

    private companion object {
        const val TAG = "OnnxTsmBehavior"
        const val ASSET_PATH = "models/behavior/campusmate_tsm_mobilenetv2_v4.onnx"
        const val INTERNAL_FILENAME = "campusmate_tsm_mobilenetv2_v4_f5acc4e5.onnx"
        const val EXPECTED_FILE_SIZE = 9_092_286L
        const val INPUT_NAME = "frames"
        const val OUTPUT_NAME = "logits"
        const val INPUT_WIDTH = 224
        const val INPUT_HEIGHT = 224
        const val CHANNELS = 3
        const val PIXEL_COUNT = INPUT_WIDTH * INPUT_HEIGHT
        const val INPUT_FLOAT_COUNT = BehaviorTsmContract.INPUT_FRAME_COUNT * CHANNELS * PIXEL_COUNT
        const val OUTPUT_SIZE = 5
        val INPUT_SHAPE = longArrayOf(
            1,
            BehaviorTsmContract.INPUT_FRAME_COUNT.toLong(),
            CHANNELS.toLong(),
            INPUT_HEIGHT.toLong(),
            INPUT_WIDTH.toLong(),
        )
    }
}

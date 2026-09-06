package com.example.campusai.data.behavior

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import ai.onnxruntime.TensorInfo
import android.content.Context
import android.graphics.Bitmap
import android.graphics.RectF
import android.util.Log
import com.example.campusai.BuildConfig
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer

/** V3.4-first ONNX engine with an explicit V3.2 full-frame fallback. */
class OnnxBehaviorRecognitionEngine(private val context: Context) : BehaviorRecognitionEngine {
    private var environment: OrtEnvironment? = null
    private var v34Session: OrtSession? = null
    private var v32Session: OrtSession? = null
    private var inputTensor: OnnxTensor? = null
    private var inputBuffer: FloatBuffer? = null
    private val pixelBuffer = IntArray(PIXEL_COUNT)
    @Volatile private var ready = false

    override val isAvailable: Boolean get() = ready

    @Synchronized
    override fun initialize() {
        if (ready) return
        closeSessions()
        try {
            val env = environment ?: OrtEnvironment.getEnvironment().also { environment = it }
            v34Session = openValidatedSession(env, V34_MODEL)
            v32Session = openValidatedSession(env, V32_MODEL)
            if (v34Session == null && v32Session == null) error("No behavior model could be loaded")
            val buffer = ByteBuffer.allocateDirect(INPUT_FLOAT_COUNT * Float.SIZE_BYTES)
                .order(ByteOrder.nativeOrder()).asFloatBuffer()
            inputBuffer = buffer
            inputTensor = OnnxTensor.createTensor(env, buffer, INPUT_SHAPE)
            ready = true
            Log.i(TAG, "Behavior models initialized: v34=${v34Session != null}, v32=${v32Session != null}")
        } catch (error: Throwable) {
            ready = false
            closeSessions()
            Log.e(TAG, "Failed to initialize behavior models", error)
        }
    }

    override fun analyzeTemporalWindow(frames: List<Bitmap>, timestampMs: Long): BehaviorPrediction =
        analyzeTemporalWindow(frames, timestampMs, null)

    @Synchronized
    override fun analyzeTemporalWindow(
        frames: List<Bitmap>,
        timestampMs: Long,
        modelInputPersonBoundingBox: RectF?,
    ): BehaviorPrediction {
        if (!ready) return unavailablePrediction(timestampMs)
        val frame = frames.lastOrNull() ?: return BehaviorPrediction(emptyMap(), timestampMs, "NO_FRAME")
        val roi = modelInputPersonBoundingBox?.let {
            BehaviorRoi.from(it.left, it.top, it.right, it.bottom, frame.width, frame.height)
        }
        val selected = BehaviorModelSelection.select(
            v34Available = v34Session != null,
            v32Available = v32Session != null,
            hasPersonRoi = roi != null,
        )
        val spec = when (selected) {
            BehaviorRuntimeModel.V34 -> V34_MODEL
            BehaviorRuntimeModel.V32 -> V32_MODEL
            BehaviorRuntimeModel.UNAVAILABLE -> return unavailablePrediction(timestampMs)
        }
        val session = when (selected) {
            BehaviorRuntimeModel.V34 -> v34Session
            BehaviorRuntimeModel.V32 -> v32Session
            BehaviorRuntimeModel.UNAVAILABLE -> null
        } ?: return unavailablePrediction(timestampMs)
        val tensor = inputTensor ?: return unavailablePrediction(timestampMs)
        val inferenceBitmap = if (selected == BehaviorRuntimeModel.V34 && roi != null) {
            Bitmap.createBitmap(frame, roi.left, roi.top, roi.width, roi.height)
        } else frame

        return try {
            val preprocessStart = if (BuildConfig.DEBUG) System.currentTimeMillis() else 0L
            preprocess(inferenceBitmap, timestampMs)
            val preprocessLatency = if (BuildConfig.DEBUG) System.currentTimeMillis() - preprocessStart else -1L
            val inferenceStart = if (BuildConfig.DEBUG) System.currentTimeMillis() else 0L
            session.run(mapOf(INPUT_NAME to tensor)).use { result ->
                val outputTensor = result.get(0) as OnnxTensor
                val logitsBuffer = outputTensor.floatBuffer ?: error("Behavior model output is not float")
                if (logitsBuffer.remaining() < spec.outputSize) {
                    error("Expected ${spec.outputSize} logits, got ${logitsBuffer.remaining()}")
                }
                val logits = FloatArray(spec.outputSize) { logitsBuffer.get(it) }
                val inferenceLatency = if (BuildConfig.DEBUG) System.currentTimeMillis() - inferenceStart else -1L
                if (selected == BehaviorRuntimeModel.V34) {
                    val decoded = BehaviorV34Contract.decode(logits)
                    BehaviorPrediction(
                        probabilities = decoded.probabilities,
                        timestampMs = timestampMs,
                        modelState = spec.readyState,
                        stableBehavior = decoded.acceptedBehavior,
                        debugInferenceLatencyMs = inferenceLatency,
                        debugPreprocessingLatencyMs = preprocessLatency,
                    )
                } else {
                    val probabilities = BehaviorModelMath.softmax(logits)
                    BehaviorPrediction(
                        probabilities = mapOf(
                            StudyBehavior.IDLE to probabilities[0],
                            StudyBehavior.VISIBLE_STUDY to probabilities[1],
                        ),
                        timestampMs = timestampMs,
                        modelState = spec.readyState,
                        debugInferenceLatencyMs = inferenceLatency,
                        debugPreprocessingLatencyMs = preprocessLatency,
                    )
                }
            }
        } catch (error: Throwable) {
            Log.e(TAG, "Behavior inference failed for ${spec.readyState}", error)
            BehaviorPrediction(emptyMap(), timestampMs, "INFERENCE_ERROR")
        } finally {
            if (inferenceBitmap !== frame && !inferenceBitmap.isRecycled) inferenceBitmap.recycle()
        }
    }

    private fun preprocess(bitmap: Bitmap, timestampMs: Long) {
        val buffer = inputBuffer ?: error("Input buffer is unavailable")
        val scaled = Bitmap.createScaledBitmap(bitmap, INPUT_WIDTH, INPUT_HEIGHT, true)
        try {
            BehaviorInputDebugExporter.export(context, bitmap, scaled, timestampMs)
            scaled.getPixels(pixelBuffer, 0, INPUT_WIDTH, 0, 0, INPUT_WIDTH, INPUT_HEIGHT)
            for (index in 0 until PIXEL_COUNT) {
                val pixel = pixelBuffer[index]
                val red = ((pixel ushr 16) and 0xFF) / 255.0f
                val green = ((pixel ushr 8) and 0xFF) / 255.0f
                val blue = (pixel and 0xFF) / 255.0f
                buffer.put(index, (red - MEAN_R) / STD_R)
                buffer.put(PIXEL_COUNT + index, (green - MEAN_G) / STD_G)
                buffer.put((2 * PIXEL_COUNT) + index, (blue - MEAN_B) / STD_B)
            }
        } finally {
            if (scaled !== bitmap && !scaled.isRecycled) scaled.recycle()
        }
    }

    private fun openValidatedSession(env: OrtEnvironment, spec: BehaviorModelSpec): OrtSession? = try {
        env.createSession(ensureModelFile(spec).absolutePath).also { validateContract(it, spec) }
    } catch (error: Throwable) {
        Log.w(TAG, "Unable to load ${spec.readyState}; fallback remains available", error)
        null
    }

    private fun validateContract(session: OrtSession, spec: BehaviorModelSpec) {
        val input = session.inputInfo[INPUT_NAME]?.info as? TensorInfo
            ?: error("Missing float tensor input '$INPUT_NAME'")
        require(input.shape.contentEquals(INPUT_SHAPE)) {
            "Unexpected ${spec.readyState} input shape ${input.shape.contentToString()}"
        }
        val output = session.outputInfo.values.singleOrNull()?.info as? TensorInfo
            ?: error("Expected one tensor output")
        require(output.shape.contentEquals(longArrayOf(1, spec.outputSize.toLong()))) {
            "Unexpected ${spec.readyState} output shape ${output.shape.contentToString()}"
        }
    }

    private fun ensureModelFile(spec: BehaviorModelSpec): File {
        val directory = File(context.noBackupFilesDir, "behavior_models")
        if (!directory.exists() && !directory.mkdirs()) error("Could not create $directory")
        val modelFile = File(directory, spec.internalFilename)
        if (modelFile.isFile && modelFile.length() > 0L) return modelFile
        val temporary = File(directory, "${spec.internalFilename}.tmp")
        context.assets.open(spec.assetPath).use { input ->
            temporary.outputStream().use { output -> input.copyTo(output) }
        }
        if (modelFile.exists()) modelFile.delete()
        if (!temporary.renameTo(modelFile)) {
            temporary.copyTo(modelFile, overwrite = true)
            temporary.delete()
        }
        return modelFile
    }

    private fun unavailablePrediction(timestampMs: Long) =
        BehaviorPrediction(emptyMap(), timestampMs, "MODEL_NOT_AVAILABLE")

    @Synchronized
    override fun close() {
        ready = false
        closeSessions()
    }

    private fun closeSessions() {
        try { inputTensor?.close() } catch (error: Throwable) { Log.w(TAG, "Failed closing input", error) }
        try { v34Session?.close() } catch (error: Throwable) { Log.w(TAG, "Failed closing V3.4", error) }
        try { v32Session?.close() } catch (error: Throwable) { Log.w(TAG, "Failed closing V3.2", error) }
        inputTensor = null
        inputBuffer = null
        v34Session = null
        v32Session = null
    }

    private data class BehaviorModelSpec(
        val assetPath: String,
        val internalFilename: String,
        val readyState: String,
        val outputSize: Int,
    )

    companion object {
        private const val TAG = "OnnxBehaviorEngine"
        private val V34_MODEL = BehaviorModelSpec(
            "models/behavior/campusmate_behavior_v34.onnx",
            "campusmate_behavior_v34.onnx",
            BehaviorV34Contract.MODEL_STATE,
            4,
        )
        private val V32_MODEL = BehaviorModelSpec(
            "models/behavior/campusmate_visible_study_v32.onnx",
            "campusmate_visible_study_v32.onnx",
            "READY_VISIBLE_STUDY_V32",
            2,
        )
        private const val INPUT_NAME = "input"
        private const val INPUT_WIDTH = 224
        private const val INPUT_HEIGHT = 224
        private const val PIXEL_COUNT = INPUT_WIDTH * INPUT_HEIGHT
        private const val INPUT_FLOAT_COUNT = 3 * PIXEL_COUNT
        private val INPUT_SHAPE = longArrayOf(1, 3, INPUT_HEIGHT.toLong(), INPUT_WIDTH.toLong())
        private const val MEAN_R = 0.485f
        private const val MEAN_G = 0.456f
        private const val MEAN_B = 0.406f
        private const val STD_R = 0.229f
        private const val STD_G = 0.224f
        private const val STD_B = 0.225f
    }
}

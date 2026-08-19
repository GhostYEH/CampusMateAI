package com.example.campusai.data.behavior

import android.content.Context
import android.graphics.RectF
import android.util.Log
import com.example.campusai.data.camera.CameraFrame
import com.example.campusai.data.camera.FrameAnalyzer
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.tensorflow.lite.support.image.TensorImage
import org.tensorflow.lite.task.core.BaseOptions
import org.tensorflow.lite.task.vision.detector.ObjectDetector

/** Configuration is intentionally independent from behavior-recognition thresholds. */
data class PersonDetectorConfig(
    val confidenceThreshold: Float = 0.45f,
    val inferenceIntervalMs: Long = 500L,
    val personHoldMs: Long = 2_000L,
    val numThreads: Int = 2,
)

data class PersonDetectionSnapshot(
    val status: PersonDetectorStatus = PersonDetectorStatus.OFF,
    val personDetected: Boolean = false,
    val personConfidence: Float? = null,
    val boundingBox: RectF? = null,
    val timestampMs: Long = 0L,
    val errorCategory: PersonDetectorErrorCategory? = null,
    val error: String? = null,
)

enum class PersonDetectorStatus {
    OFF,
    INITIALIZING,
    READY,
    RUNNING,
    ERROR,
}

enum class PersonDetectorErrorCategory {
    MODEL_OR_METADATA,
    TFLITE_RUNTIME,
    NATIVE_LIBRARY,
    INFERENCE,
    UNKNOWN,
}

/** Low-frequency detector that reuses the existing upright, mirrored camera frame. */
class PersonAnalyzer(
    private val context: Context,
    val config: PersonDetectorConfig = PersonDetectorConfig(),
) : FrameAnalyzer {
    private val executor: ExecutorService = Executors.newSingleThreadExecutor()
    private val inferenceInFlight = AtomicBoolean(false)
    private val _snapshot = MutableStateFlow(PersonDetectionSnapshot())
    val snapshot: StateFlow<PersonDetectionSnapshot> = _snapshot.asStateFlow()

    @Volatile private var running = false
    @Volatile private var initialized = false
    @Volatile private var detector: ObjectDetector? = null
    private var lastInferenceAtMs = Long.MIN_VALUE

    @Synchronized
    fun ensureInitialized() {
        if (initialized) return
        _snapshot.value = PersonDetectionSnapshot(status = PersonDetectorStatus.INITIALIZING)
        try {
            val baseOptions = BaseOptions.builder().setNumThreads(config.numThreads).build()
            val options = ObjectDetector.ObjectDetectorOptions.builder()
                .setBaseOptions(baseOptions)
                .setScoreThreshold(config.confidenceThreshold)
                .setMaxResults(MAX_RESULTS)
                .build()
            detector = ObjectDetector.createFromFileAndOptions(context, MODEL_ASSET_PATH, options)
            initialized = true
            _snapshot.value = PersonDetectionSnapshot(status = PersonDetectorStatus.READY)
        } catch (error: Throwable) {
            val category = error.category()
            val summary = error.safeSummary()
            safeLogError("Person detector initialization failed [$category]: ${error.javaClass.name}: $summary", error)
            detector = null
            _snapshot.value = PersonDetectionSnapshot(
                status = PersonDetectorStatus.ERROR,
                errorCategory = category,
                error = summary,
            )
        }
    }

    fun start() {
        running = initialized && detector != null
        if (running) _snapshot.value = _snapshot.value.copy(status = PersonDetectorStatus.RUNNING, error = null)
    }

    fun pause() {
        running = false
        if (initialized) _snapshot.value = _snapshot.value.copy(status = PersonDetectorStatus.READY)
    }

    override fun analyze(frame: CameraFrame) {
        val currentDetector = detector ?: return
        val timestampMs = frame.timestampMs
        if (!running || timestampMs - lastInferenceAtMs < config.inferenceIntervalMs ||
            !inferenceInFlight.compareAndSet(false, true)
        ) return
        lastInferenceAtMs = timestampMs
        frame.retain()
        executor.execute {
            try {
                val person = currentDetector.detect(TensorImage.fromBitmap(frame.bitmap))
                    .flatMap { detection ->
                        detection.categories
                            .filter { it.label.equals(PERSON_LABEL, ignoreCase = true) }
                            .map { DetectedPerson(it.score, detection.boundingBox) }
                    }
                    .maxByOrNull { it.confidence }
                _snapshot.value = PersonDetectionSnapshot(
                    status = PersonDetectorStatus.RUNNING,
                    personDetected = person != null,
                    personConfidence = person?.confidence,
                    boundingBox = person?.boundingBox,
                    timestampMs = timestampMs,
                )
            } catch (error: Throwable) {
                val category = error.category()
                val summary = error.safeSummary()
                safeLogError("Person detector inference failed [$category]: ${error.javaClass.name}: $summary", error)
                _snapshot.value = _snapshot.value.copy(
                    status = PersonDetectorStatus.ERROR,
                    personDetected = false,
                    personConfidence = null,
                    boundingBox = null,
                    timestampMs = timestampMs,
                    errorCategory = category,
                    error = summary,
                )
            } finally {
                frame.release()
                inferenceInFlight.set(false)
            }
        }
    }

    @Synchronized
    fun close() {
        running = false
        inferenceInFlight.set(false)
        try { detector?.close() } catch (_: Throwable) { }
        detector = null
        initialized = false
        executor.shutdownNow()
        _snapshot.value = PersonDetectionSnapshot(status = PersonDetectorStatus.OFF)
    }

    private data class DetectedPerson(val confidence: Float, val boundingBox: RectF)

    private fun Throwable.category(): PersonDetectorErrorCategory {
        val details = generateSequence(this) { it.cause }
            .joinToString(" ") { "${it.javaClass.name} ${it.message.orEmpty()}" }
            .lowercase()
        return when {
            "unsatisfiedlink" in details || "jni" in details || "native" in details -> PersonDetectorErrorCategory.NATIVE_LIBRARY
            "metadata" in details || "label" in details || "model" in details || "asset" in details -> PersonDetectorErrorCategory.MODEL_OR_METADATA
            "tensorflow" in details || "litert" in details || "noclassdef" in details || "nosuchmethod" in details -> PersonDetectorErrorCategory.TFLITE_RUNTIME
            else -> PersonDetectorErrorCategory.UNKNOWN
        }
    }

    private fun Throwable.safeSummary(): String =
        (message ?: javaClass.simpleName).replace(Regex("[\\r\\n]+"), " ").take(180)

    private fun safeLogError(message: String, error: Throwable) {
        try {
            Log.e(TAG, message, error)
        } catch (_: RuntimeException) {
            // Local JVM tests do not provide Android's Log implementation.
        }
    }

    private companion object {
        const val TAG = "PersonAnalyzer"
        const val MODEL_ASSET_PATH = "models/person/efficientdet_lite0_int8.tflite"
        const val PERSON_LABEL = "person"
        const val MAX_RESULTS = 3
    }
}

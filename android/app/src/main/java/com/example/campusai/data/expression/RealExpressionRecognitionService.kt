package com.example.campusai.data.expression

import android.app.Application
import android.graphics.Bitmap
import android.graphics.Rect
import android.os.SystemClock
import com.example.campusai.data.camera.CameraFrame
import com.example.campusai.data.camera.FrameDropAwareAnalyzer
import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.ExpressionResult
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.Face
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

class RealExpressionRecognitionService(
    private val application: Application,
) : ObservableExpressionRecognitionService, FrameDropAwareAnalyzer {
    private var analysisExecutor: ExecutorService = Executors.newSingleThreadExecutor()
    private var processor: ExpressionSignalProcessor? = null
    private var runner: ExpressionModelRunner? = null
    private val analyzing = AtomicBoolean(false)
    private var running = false
    private var lastAnalyzedAt = 0L
    private val initializationMutex = Mutex()
    private val inferenceLock = Any()
    val performanceStats = ExpressionPerformanceStats()
    private val faceQualityGate = FaceQualityGate()

    private val detector = FaceDetection.getClient(
        FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
            .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_NONE)
            .setContourMode(FaceDetectorOptions.CONTOUR_MODE_NONE)
            .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_ALL)
            .setMinFaceSize(0.18f)
            .enableTracking()
            .build(),
    )

    private val _status = MutableStateFlow<ExpressionServiceStatus>(ExpressionServiceStatus.Off)
    override val status: StateFlow<ExpressionServiceStatus> = _status.asStateFlow()
    private val _results = MutableStateFlow(
        ExpressionResult(
            ExpressionLabel.UNKNOWN,
            0.0,
            emptyMap(),
            System.currentTimeMillis(),
            false,
            "not-loaded",
        ),
    )
    override val modeLabel = "本机 LiteRT"

    override fun results(): Flow<ExpressionResult> = _results

    override fun onFrameDropped() {
        if (running) performanceStats.recordDroppedFrame()
    }

    fun performanceSnapshot(nowMs: Long = SystemClock.elapsedRealtime()): ExpressionPerformanceSnapshot =
        performanceStats.snapshot(nowMs)

    override suspend fun initialize() {
        initializationMutex.withLock {
            if (runner != null) return@withLock
            _status.value = ExpressionServiceStatus.Initializing
            try {
                ensureResources()
                val modelRunner = ExpressionModelRunner(application).also { it.initialize() }
                runner = modelRunner
                processor = ExpressionSignalProcessor(
                    ExpressionSignalConfig(
                        minimumConfidence = modelRunner.preprocessing.confidenceThreshold,
                        classThresholds = modelRunner.preprocessing.classThresholds,
                    ),
                    modelRunner.preprocessing.modelVersion,
                )
                _status.value = ExpressionServiceStatus.Ready
            } catch (error: Exception) {
                _status.value = ExpressionServiceStatus.Error(
                error.message ?: "表情模型加载失败",
                )
                throw error
            }
        }
    }

    override suspend fun start() {
        if (runner == null) initialize()
        performanceStats.start(SystemClock.elapsedRealtime())
        running = true
        _status.value = ExpressionServiceStatus.Running
    }

    override suspend fun pause() {
        running = false
        processor?.reset()
        _status.value = ExpressionServiceStatus.Paused
    }

    override suspend fun stop() {
        running = false
        processor?.reset()
        _status.value = ExpressionServiceStatus.Ready
    }

    override suspend fun dispose() {
        running = false
        synchronized(inferenceLock) {
            runner?.close()
            runner = null
            processor = null
        }
        detector.close()
        analysisExecutor.shutdownNow()
        _status.value = ExpressionServiceStatus.Off
    }

    override fun analyze(frame: CameraFrame) {
        val now = SystemClock.elapsedRealtime()
        if (!running) {
            return
        }
        if (now - lastAnalyzedAt < ANALYSIS_INTERVAL_MS ||
            !analyzing.compareAndSet(false, true)
        ) {
            performanceStats.recordDroppedFrame()
            return
        }
        lastAnalyzedAt = now
        val totalStartedAtNanos = SystemClock.elapsedRealtimeNanos()
        frame.retain()
        val bitmap = frame.bitmap

        detector.process(InputImage.fromBitmap(bitmap, 0))
            .addOnSuccessListener(analysisExecutor) { faces ->
                if (!running) return@addOnSuccessListener
                val faceDetectionMs = elapsedMs(totalStartedAtNanos)
                if (faces.isEmpty()) {
                    val postprocessStartedAt = SystemClock.elapsedRealtimeNanos()
                    emitNoFace()
                    performanceStats.recordFrame(
                        faceDetectionMs = faceDetectionMs,
                        preprocessMs = 0L,
                        inferenceMs = 0L,
                        postprocessMs = elapsedMs(postprocessStartedAt),
                        totalLatencyMs = elapsedMs(totalStartedAtNanos),
                        noFace = true,
                        unknown = false,
                    )
                } else {
                    infer(
                        bitmap = bitmap,
                        face = selectLargestFace(faces),
                        faceCount = faces.size,
                        totalStartedAtNanos = totalStartedAtNanos,
                        faceDetectionMs = faceDetectionMs,
                    )
                }
            }
            .addOnFailureListener(analysisExecutor) { error ->
                _status.value = ExpressionServiceStatus.Error(
                    error.message ?: "人脸检测失败",
                )
                performanceStats.recordFrame(
                    faceDetectionMs = elapsedMs(totalStartedAtNanos),
                    preprocessMs = 0L,
                    inferenceMs = 0L,
                    postprocessMs = 0L,
                    totalLatencyMs = elapsedMs(totalStartedAtNanos),
                    noFace = false,
                    unknown = true,
                )
            }
            .addOnCompleteListener(analysisExecutor) {
                frame.release()
                analyzing.set(false)
            }
    }

    private fun infer(
        bitmap: Bitmap,
        face: Face,
        faceCount: Int,
        totalStartedAtNanos: Long,
        faceDetectionMs: Long,
    ) {
        try {
            val crop = paddedCrop(face.boundingBox, bitmap.width, bitmap.height)
            val faceBitmap = Bitmap.createBitmap(
                bitmap,
                crop.left,
                crop.top,
                crop.width(),
                crop.height(),
            )
            try {
                val qualityStartedAt = SystemClock.elapsedRealtimeNanos()
                val quality = faceQualityGate.evaluate(face, faceBitmap, faceCount)
                val qualityMs = elapsedMs(qualityStartedAt)
                if (!quality.accepted) {
                    val postprocessStartedAt = SystemClock.elapsedRealtimeNanos()
                    val result = checkNotNull(processor).process(
                        emptyMap(),
                        System.currentTimeMillis(),
                        hasFace = true,
                    )
                    _results.value = result.copy(
                        facePresent = true,
                        headEulerAngleX = face.headEulerAngleX.toDouble(),
                        headEulerAngleY = face.headEulerAngleY.toDouble(),
                        headEulerAngleZ = face.headEulerAngleZ.toDouble(),
                        leftEyeOpenProbability = face.leftEyeOpenProbability?.toDouble(),
                        rightEyeOpenProbability = face.rightEyeOpenProbability?.toDouble(),
                    )
                    _status.value = ExpressionServiceStatus.LowConfidence
                    performanceStats.recordFrame(
                        faceDetectionMs = faceDetectionMs,
                        preprocessMs = qualityMs,
                        inferenceMs = 0L,
                        postprocessMs = elapsedMs(postprocessStartedAt),
                        totalLatencyMs = elapsedMs(totalStartedAtNanos),
                        noFace = false,
                        unknown = true,
                    )
                    return
                }

                val processed = synchronized(inferenceLock) {
                    val modelRun = checkNotNull(runner).runTimed(faceBitmap)
                    val processorStartedAt = SystemClock.elapsedRealtimeNanos()
                    val result = checkNotNull(processor).process(
                        modelRun.probabilities,
                        System.currentTimeMillis(),
                        hasFace = true,
                    )
                    Triple(modelRun, result, elapsedMs(processorStartedAt))
                }
                val modelRun = processed.first
                val result = processed.second
                _results.value = result.copy(
                    facePresent = true,
                    headEulerAngleX = face.headEulerAngleX.toDouble(),
                    headEulerAngleY = face.headEulerAngleY.toDouble(),
                    headEulerAngleZ = face.headEulerAngleZ.toDouble(),
                    leftEyeOpenProbability = face.leftEyeOpenProbability?.toDouble(),
                    rightEyeOpenProbability = face.rightEyeOpenProbability?.toDouble(),
                )
                _status.value = when (result.label) {
                    ExpressionLabel.UNKNOWN -> ExpressionServiceStatus.LowConfidence
                    else -> ExpressionServiceStatus.Running
                }
                performanceStats.recordFrame(
                    faceDetectionMs = faceDetectionMs,
                    preprocessMs = qualityMs + modelRun.preprocessMs,
                    inferenceMs = modelRun.inferenceMs,
                    postprocessMs = modelRun.postprocessMs + processed.third,
                    totalLatencyMs = elapsedMs(totalStartedAtNanos),
                    noFace = false,
                    unknown = result.label == ExpressionLabel.UNKNOWN,
                )
            } finally {
                faceBitmap.recycle()
            }
        } catch (error: Exception) {
            _status.value = ExpressionServiceStatus.Error(
                error.message ?: "表情推理失败",
            )
            performanceStats.recordFrame(
                faceDetectionMs = faceDetectionMs,
                preprocessMs = 0L,
                inferenceMs = 0L,
                postprocessMs = 0L,
                totalLatencyMs = elapsedMs(totalStartedAtNanos),
                noFace = false,
                unknown = true,
            )
        }
    }

    private fun emitNoFace() {
        val result = processor?.process(
            emptyMap(),
            System.currentTimeMillis(),
            hasFace = false,
        ) ?: return
        _results.value = result.copy(facePresent = false)
        _status.value = ExpressionServiceStatus.NoFace
    }

    private fun selectLargestFace(faces: List<Face>): Face =
        faces.maxBy { it.boundingBox.width() * it.boundingBox.height() }

    private fun paddedCrop(box: Rect, width: Int, height: Int): Rect {
        val paddingX = (box.width() * 0.16).toInt()
        val paddingY = (box.height() * 0.20).toInt()
        return Rect(
            (box.left - paddingX).coerceIn(0, width - 1),
            (box.top - paddingY).coerceIn(0, height - 1),
            (box.right + paddingX).coerceIn(1, width),
            (box.bottom + paddingY).coerceIn(1, height),
        )
    }

    private fun ensureResources() {
        if (analysisExecutor.isShutdown) {
            analysisExecutor = Executors.newSingleThreadExecutor()
        }
    }

    private fun elapsedMs(startedAtNanos: Long): Long =
        ((SystemClock.elapsedRealtimeNanos() - startedAtNanos) / 1_000_000L).coerceAtLeast(0L)

    companion object {
        private const val ANALYSIS_INTERVAL_MS = 200L
    }
}

package com.example.campusai.data.expression

import android.app.Application
import android.graphics.Bitmap
import android.graphics.Rect
import android.os.SystemClock
import com.example.campusai.data.camera.CameraFrame
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
) : ObservableExpressionRecognitionService {
    private var analysisExecutor: ExecutorService = Executors.newSingleThreadExecutor()
    private var processor: ExpressionSignalProcessor? = null
    private var runner: ExpressionModelRunner? = null
    private val analyzing = AtomicBoolean(false)
    private var running = false
    private var lastAnalyzedAt = 0L
    private val initializationMutex = Mutex()
    private val inferenceLock = Any()

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
        if (!running || now - lastAnalyzedAt < ANALYSIS_INTERVAL_MS ||
            !analyzing.compareAndSet(false, true)
        ) {
            return
        }
        lastAnalyzedAt = now
        frame.retain()
        val bitmap = frame.bitmap
        
        detector.process(InputImage.fromBitmap(bitmap, 0))
            .addOnSuccessListener(analysisExecutor) { faces ->
                if (!running) return@addOnSuccessListener
                if (faces.isEmpty()) {
                    emitNoFace()
                } else {
                    infer(bitmap, selectLargestFace(faces))
                }
            }
            .addOnFailureListener(analysisExecutor) { error ->
                _status.value = ExpressionServiceStatus.Error(
                    error.message ?: "人脸检测失败",
                )
            }
            .addOnCompleteListener(analysisExecutor) {
                frame.release()
                analyzing.set(false)
            }
    }

    private fun infer(bitmap: Bitmap, face: Face) {
        try {
            val crop = paddedCrop(face.boundingBox, bitmap.width, bitmap.height)
            val faceBitmap = Bitmap.createBitmap(
                bitmap,
                crop.left,
                crop.top,
                crop.width(),
                crop.height(),
            )
            val result = try {
                synchronized(inferenceLock) {
                    val probabilities = checkNotNull(runner).run(faceBitmap)
                    checkNotNull(processor).process(
                        probabilities,
                        System.currentTimeMillis(),
                        hasFace = true,
                    )
                }
            } finally {
                faceBitmap.recycle()
            }
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
        } catch (error: Exception) {
            _status.value = ExpressionServiceStatus.Error(
                error.message ?: "表情推理失败",
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

    companion object {
        private const val ANALYSIS_INTERVAL_MS = 200L
    }
}

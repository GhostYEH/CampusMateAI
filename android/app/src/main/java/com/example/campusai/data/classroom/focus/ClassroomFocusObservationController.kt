package com.example.campusai.data.classroom.focus

import android.Manifest
import android.app.Application
import android.content.pm.PackageManager
import android.net.Uri
import android.os.SystemClock
import android.util.Size
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.CameraState
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.Observer
import com.example.campusai.BuildConfig
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetector
import com.google.mlkit.vision.face.FaceDetectorOptions
import java.util.Locale
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * 原生课堂「课堂观察」的 Android 适配层。
 *
 * 只做三件事：
 * 1. 在用户开启后用 CameraX 前置摄像头做约 4 次/秒的 `ImageAnalysis`；
 * 2. 用 ML Kit 人脸检测返回人脸数量与头部角度，用 Y 平面估算亮度；
 * 3. 把检测结果交给 `ClassroomFocusObservation` 纯规则，并在关闭/切后台/换课时
 *    解绑摄像头、关闭检测器、清空时间窗。
 *
 * 不申请音频、不展示预览、不把帧或结果发往后端。每个 Controller 只允许一个
 * 活跃观察会话；会话对象持有自己的分析链与代次，关闭后重开的旧回调不能写入新会话。
 */
data class ClassroomFocusUiState(
    val enabled: Boolean = false,
    val busy: Boolean = false,
    val status: ClassroomFocusStatus? = null,
    val reason: ClassroomFocusReason? = null,
    val notice: String? = null,
    val fatal: Boolean = false,
    val latestWindow: ClassroomObservationWindow? = null,
    val windowCount: Int = 0,
)

class ClassroomFocusObservationController(
    private val application: Application,
    private val lifecycleOwner: LifecycleOwner,
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val _state = MutableStateFlow(ClassroomFocusUiState())
    val state: StateFlow<ClassroomFocusUiState> = _state.asStateFlow()

    private val analysisExecutor = Executors.newSingleThreadExecutor()
    private val sessionGate = ClassroomObservationSessionGate()

    @Volatile
    private var currentSession: Session? = null

    @Volatile
    private var disposed = false

    private var pendingStage: String? = null

    private class Session(val id: Long) {
        val processing = AtomicBoolean(false)
        val lastFrameAt = AtomicLong(0L)
        val lastSampleAt = AtomicLong(0L)
        val lowLightSince = AtomicLong(0L)

        var observation = ClassroomFocusState()
        var provider: ProcessCameraProvider? = null
        var analysis: ImageAnalysis? = null
        var camera: Camera? = null
        var detector: FaceDetector? = null
        var cameraStateObserver: Observer<CameraState>? = null
        var watchdogJob: Job? = null
        var activityJob: Job? = null
        var watchdogReason: ClassroomFocusReason? = null
        var watchdogReportedAt = 0L
    }

    fun start() {
        if (disposed || _state.value.enabled || _state.value.busy) return
        if (ContextCompat.checkSelfPermission(application, Manifest.permission.CAMERA) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            permissionDenied()
            return
        }

        val session = Session(sessionGate.open())
        currentSession = session
        _state.update {
            it.copy(
                busy = true,
                status = null,
                reason = null,
                notice = null,
                fatal = false,
            )
        }

        val options = FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
            .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_NONE)
            .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_NONE)
            .setMinFaceSize(ClassroomFocusObservationConfig.MIN_FACE_SIZE)
            .build()

        val future = ProcessCameraProvider.getInstance(application)
        future.addListener({
            if (!isCurrent(session)) return@addListener
            val cameraProvider = try {
                future.get()
            } catch (error: Exception) {
                failStart(session, startFailureReason(error))
                return@addListener
            }
            val newDetector = try {
                FaceDetection.getClient(options)
            } catch (_: Exception) {
                failStart(session, ClassroomFocusReason.MODEL_UNAVAILABLE)
                return@addListener
            }
            val useCase = try {
                ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .setResolutionSelector(
                        ResolutionSelector.Builder()
                            .setResolutionStrategy(
                                ResolutionStrategy(
                                    Size(320, 240),
                                    ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER,
                                ),
                            )
                            .build(),
                    )
                    .build()
            } catch (_: Exception) {
                runCatching { newDetector.close() }
                failStart(session, ClassroomFocusReason.START_FAILED)
                return@addListener
            }

            try {
                useCase.setAnalyzer(analysisExecutor) { image -> analyze(session, image) }
                val camera = cameraProvider.bindToLifecycle(
                    lifecycleOwner,
                    CameraSelector.DEFAULT_FRONT_CAMERA,
                    useCase,
                )
                session.provider = cameraProvider
                session.analysis = useCase
                session.camera = camera
                session.detector = newDetector

                val now = now()
                session.lastFrameAt.set(now)
                session.lastSampleAt.set(0L)
                session.lowLightSince.set(0L)
                session.observation = ClassroomFocusObservation
                    .begin(now, session.id)
                    .copy(stage = pendingStage)
                _state.update {
                    it.copy(
                        enabled = true,
                        busy = false,
                        status = ClassroomFocusStatus.OBSERVING,
                        reason = null,
                        notice = null,
                        fatal = false,
                        latestWindow = null,
                        windowCount = 0,
                    )
                }
                observeCameraState(session, camera)
                startWatchdog(session)
                startActivityCollection(session)
            } catch (error: Exception) {
                runCatching { useCase.clearAnalyzer() }
                runCatching { cameraProvider.unbind(useCase) }
                runCatching { newDetector.close() }
                failStart(session, startFailureReason(error))
            }
        }, ContextCompat.getMainExecutor(application))
    }

    fun permissionDenied() {
        stop()
        if (disposed) return
        _state.value = ClassroomFocusUiState(
            status = ClassroomFocusStatus.UNAVAILABLE,
            reason = ClassroomFocusReason.PERMISSION_DENIED,
            fatal = true,
        )
    }

    fun stop(notice: String? = null) {
        val session = currentSession
        currentSession = null
        sessionGate.close()
        session?.let { teardown(it) }
        session?.let { it.observation = ClassroomFocusObservation.stop() }
        if (!disposed) {
            _state.value = ClassroomFocusUiState(notice = notice)
        }
    }

    fun record(type: ClassroomFocusEventType) {
        val session = currentSession ?: return
        if (!_state.value.enabled) return
        recordInternal(session, type)
    }

    /**
     * 课堂阶段由播放器按当前页/讲解状态提供，只作为窗口事实，不推断注意力。
     */
    fun updateStage(stage: String?) {
        pendingStage = stage?.takeIf { it.isNotBlank() }
        val session = currentSession ?: return
        if (session.observation.phase == ClassroomFocusPhase.IDLE) return
        session.observation = session.observation.copy(stage = pendingStage)
    }

    /** Debug 复盘入口；Release 构建直接返回 null，不产生文件。 */
    suspend fun export(format: ClassroomObservationExportFormat): Uri? {
        if (!BuildConfig.DEBUG) return null
        val session = currentSession ?: return null
        val atMs = now()
        val windows = withContext(Dispatchers.Main.immediate) {
            if (!isCurrent(session)) {
                emptyList()
            } else {
                ClassroomFocusObservation.windowsForExport(session.observation, atMs)
            }
        }
        if (windows.isEmpty()) return null
        return withContext(Dispatchers.IO) {
            ClassroomObservationDebugExporter.write(application, format, windows)
        }
    }

    fun dispose() {
        if (disposed) return
        disposed = true
        stop()
        analysisExecutor.shutdownNow()
        scope.cancel()
    }

    private fun recordInternal(session: Session, type: ClassroomFocusEventType) {
        val at = now()
        session.observation = ClassroomFocusObservation.recordEvent(
            state = session.observation,
            type = type,
            atMs = at,
            source = ClassroomFocusEventSource.STUDENT,
        )
        publishStatus(session)
    }

    private fun startWatchdog(session: Session) {
        session.watchdogJob?.cancel()
        session.watchdogJob = scope.launch {
            while (isActive) {
                delay(500)
                if (!isCurrent(session) || !_state.value.enabled) continue
                val last = session.lastFrameAt.get()
                if (last <= 0L) continue
                val at = now()
                val gap = at - last
                val reason = when {
                    gap >= ClassroomFocusObservationConfig.VIDEO_FREEZE_MS ->
                        ClassroomFocusReason.VIDEO_FROZEN
                    gap >= ClassroomFocusObservationConfig.SAMPLE_GAP_MS ->
                        ClassroomFocusReason.SAMPLING_INTERRUPTED
                    else -> null
                }
                if (reason == null) {
                    session.watchdogReason = null
                    session.watchdogReportedAt = 0L
                    continue
                }
                if (reason == session.watchdogReason &&
                    at - session.watchdogReportedAt < 1_000L
                ) {
                    continue
                }
                session.watchdogReason = reason
                session.watchdogReportedAt = at
                session.observation = ClassroomFocusObservation.noteInvalidSample(
                    state = session.observation,
                    atMs = at,
                    reason = reason,
                    stage = pendingStage,
                    sessionId = session.id,
                )
                session.observation = ClassroomFocusObservation.markUnavailable(
                    session.observation,
                    reason,
                    at,
                )
                publishStatus(session)
            }
        }
    }

    private fun startActivityCollection(session: Session) {
        session.activityJob?.cancel()
        session.activityJob = scope.launch {
            ClassroomFocusActivityBus.events.collect { type ->
                if (isCurrent(session)) recordInternal(session, type)
            }
        }
    }

    /**
     * 在单线程分析器里运行。所有状态写回都经 [scope] 切回主线程；
     * 每个会话自己的 `processing` 保证 ML Kit 异步推理未完成时直接丢弃新帧。
     * 旧会话的回调只操作旧会话对象，不会清掉新会话的忙标志或时间窗。
     */
    private fun analyze(session: Session, image: ImageProxy) {
        val at = now()
        session.lastFrameAt.set(at)
        if (!isCurrent(session)) {
            image.close()
            return
        }
        if (at - session.lastSampleAt.get() < ClassroomFocusObservationConfig.SAMPLE_INTERVAL_MS ||
            !session.processing.compareAndSet(false, true)
        ) {
            image.close()
            return
        }
        session.lastSampleAt.set(at)

        val luma = averageLuma(image)
        if (luma != null && luma < ClassroomFocusObservationConfig.LOW_LIGHT_LUMA_THRESHOLD) {
            val previous = session.lowLightSince.get()
            if (previous == 0L) session.lowLightSince.set(at)
            val lowLightFor = if (previous == 0L) 0L else at - previous
            val shouldMark = lowLightFor >= ClassroomFocusObservationConfig.LOW_LIGHT_GRACE_MS
            session.processing.set(false)
            image.close()
            scope.launch {
                if (!isCurrent(session)) return@launch
                session.observation = ClassroomFocusObservation.noteInvalidSample(
                    state = session.observation,
                    atMs = at,
                    reason = ClassroomFocusReason.LOW_LIGHT,
                    stage = pendingStage,
                    sessionId = session.id,
                )
                if (shouldMark) {
                    session.observation = ClassroomFocusObservation.markUnavailable(
                        session.observation,
                        ClassroomFocusReason.LOW_LIGHT,
                        at,
                    )
                }
                publishStatus(session)
            }
            return
        }
        session.lowLightSince.set(0L)

        val detector = session.detector
        val mediaImage = image.image
        if (detector == null || mediaImage == null) {
            image.close()
            session.processing.set(false)
            return
        }

        val input = try {
            InputImage.fromMediaImage(mediaImage, image.imageInfo.rotationDegrees)
        } catch (_: Exception) {
            image.close()
            session.processing.set(false)
            scope.launch {
                if (!isCurrent(session)) return@launch
                session.observation = ClassroomFocusObservation.noteInvalidSample(
                    state = session.observation,
                    atMs = at,
                    reason = ClassroomFocusReason.DETECTION_FAILED,
                    stage = pendingStage,
                    sessionId = session.id,
                )
                session.observation = ClassroomFocusObservation.markUnavailable(
                    session.observation,
                    ClassroomFocusReason.DETECTION_FAILED,
                    at,
                )
                publishStatus(session)
            }
            return
        }

        try {
            detector.process(input)
                .addOnSuccessListener { faces ->
                    session.processing.set(false)
                    if (!isCurrent(session)) return@addOnSuccessListener
                    val face = faces.singleOrNull()
                    // 采样时刻使用帧进入分析链的时间（`at`），而不是 ML Kit 回调完成
                    // 的时间。异步检测可能跨过 10 秒窗口边界；按回调时间归档会把本应
                    // 属于前一窗口的帧推入后一窗口。
                    applySample(
                        session = session,
                        atMs = at,
                        faceCount = faces.size,
                        yawDegrees = face?.headEulerAngleY?.toDouble(),
                        pitchDegrees = face?.headEulerAngleX?.toDouble(),
                    )
                }
                .addOnFailureListener {
                    session.processing.set(false)
                    if (!isCurrent(session)) return@addOnFailureListener
                    // 检测失败也按帧采样时刻归档，避免异步失败把无效采样推入后一窗口。
                    val failedAt = at
                    scope.launch {
                        if (!isCurrent(session)) return@launch
                        session.observation = ClassroomFocusObservation.noteInvalidSample(
                            state = session.observation,
                            atMs = failedAt,
                            reason = ClassroomFocusReason.DETECTION_FAILED,
                            stage = pendingStage,
                            sessionId = session.id,
                        )
                        session.observation = ClassroomFocusObservation.markUnavailable(
                            session.observation,
                            ClassroomFocusReason.DETECTION_FAILED,
                            failedAt,
                        )
                        publishStatus(session)
                    }
                }
                .addOnCompleteListener {
                    image.close()
                }
        } catch (_: Exception) {
            image.close()
            session.processing.set(false)
            scope.launch {
                if (!isCurrent(session)) return@launch
                session.observation = ClassroomFocusObservation.noteInvalidSample(
                    state = session.observation,
                    atMs = at,
                    reason = ClassroomFocusReason.DETECTION_FAILED,
                    stage = pendingStage,
                    sessionId = session.id,
                )
                session.observation = ClassroomFocusObservation.markUnavailable(
                    session.observation,
                    ClassroomFocusReason.DETECTION_FAILED,
                    at,
                )
                publishStatus(session)
            }
        }
    }

    private fun applySample(
        session: Session,
        atMs: Long,
        faceCount: Int,
        yawDegrees: Double?,
        pitchDegrees: Double?,
    ) {
        scope.launch {
            if (!isCurrent(session) || session.observation.phase == ClassroomFocusPhase.IDLE) {
                return@launch
            }
            session.observation = ClassroomFocusObservation.applySample(
                state = session.observation,
                atMs = atMs,
                faceCount = faceCount,
                yawDegrees = yawDegrees,
                pitchDegrees = pitchDegrees,
                stage = pendingStage,
                sessionId = session.id,
            )
            publishStatus(session)
        }
    }

    private fun observeCameraState(session: Session, camera: Camera) {
        val observer = Observer<CameraState> { cameraState ->
            val error = cameraState.error ?: return@Observer
            if (!isCurrent(session)) return@Observer
            val reason = cameraErrorReason(error.code)
            scope.launch {
                if (!isCurrent(session)) return@launch
                val at = now()
                session.observation = ClassroomFocusObservation.noteInvalidSample(
                    state = session.observation,
                    atMs = at,
                    reason = reason,
                    stage = pendingStage,
                    sessionId = session.id,
                )
                session.observation = ClassroomFocusObservation.markUnavailable(
                    session.observation,
                    reason,
                    at,
                )
                publishStatus(session)
            }
        }
        session.cameraStateObserver = observer
        camera.cameraInfo.cameraState.observe(lifecycleOwner, observer)
    }

    private fun publishStatus(session: Session) {
        if (!isCurrent(session)) return
        val at = now()
        val status = ClassroomFocusObservation.statusOf(session.observation, at)
        val reason = ClassroomFocusObservation.reasonOf(session.observation, at)
        val latest = ClassroomFocusObservation.latestWindow(session.observation)
        val windowCount = session.observation.windows.size
        val current = _state.value
        if (current.status == status && current.reason == reason &&
            current.latestWindow == latest && current.windowCount == windowCount
        ) {
            return
        }
        _state.update {
            it.copy(
                enabled = session.observation.phase != ClassroomFocusPhase.IDLE,
                busy = false,
                status = status,
                reason = reason,
                fatal = false,
                latestWindow = latest,
                windowCount = windowCount,
            )
        }
    }

    private fun failStart(session: Session, reason: ClassroomFocusReason) {
        if (!isCurrent(session)) {
            teardown(session)
            return
        }
        currentSession = null
        sessionGate.close()
        teardown(session)
        session.observation = ClassroomFocusObservation.stop()
        if (!disposed) {
            _state.value = ClassroomFocusUiState(
                status = ClassroomFocusStatus.UNAVAILABLE,
                reason = reason,
                fatal = true,
            )
        }
    }

    /** 必须在主线程调用；先让会话失效，再解绑、移除观察者并关闭检测器。 */
    private fun teardown(session: Session) {
        session.watchdogJob?.cancel()
        session.watchdogJob = null
        session.activityJob?.cancel()
        session.activityJob = null

        session.analysis?.clearAnalyzer()
        session.cameraStateObserver?.let { observer ->
            runCatching {
                session.camera?.cameraInfo?.cameraState?.removeObserver(observer)
            }
        }
        session.cameraStateObserver = null
        session.camera = null

        val provider = session.provider
        val analysis = session.analysis
        session.provider = null
        session.analysis = null
        if (provider != null && analysis != null) {
            runCatching { provider.unbind(analysis) }
        }

        val detector = session.detector
        session.detector = null
        runCatching { detector?.close() }

        session.processing.set(false)
        session.lastFrameAt.set(0L)
        session.lastSampleAt.set(0L)
        session.lowLightSince.set(0L)
        session.watchdogReason = null
        session.watchdogReportedAt = 0L
    }

    private fun averageLuma(image: ImageProxy): Double? {
        val plane = image.planes.firstOrNull() ?: return null
        val width = image.width
        val height = image.height
        val rowStride = plane.rowStride
        val pixelStride = plane.pixelStride
        if (width <= 0 || height <= 0 || rowStride <= 0 || pixelStride <= 0) return null
        val buffer = plane.buffer
        var sum = 0L
        var count = 0
        var row = 0
        while (row < height) {
            val rowStart = row * rowStride
            var column = 0
            while (column < width) {
                val index = rowStart + column * pixelStride
                if (index < buffer.limit()) {
                    sum += buffer.get(index).toInt() and 0xFF
                    count += 1
                }
                column += 4
            }
            row += 4
        }
        return if (count == 0) null else sum.toDouble() / count
    }

    private fun startFailureReason(error: Exception): ClassroomFocusReason {
        val chain = generateSequence(error as Throwable?) { it.cause }.toList()
        if (chain.any { it is SecurityException }) return ClassroomFocusReason.PERMISSION_DENIED
        val message = chain.mapNotNull { it.message }
            .joinToString(" ")
            .lowercase(Locale.ROOT)
        return when {
            message.contains("in use") ||
                message.contains("camera_in_use") ||
                message.contains("max_cameras") -> ClassroomFocusReason.CAMERA_BUSY
            error is IllegalArgumentException -> ClassroomFocusReason.CAMERA_UNAVAILABLE
            else -> ClassroomFocusReason.START_FAILED
        }
    }

    private fun cameraErrorReason(code: Int): ClassroomFocusReason = when (code) {
        CameraState.ERROR_CAMERA_IN_USE,
        CameraState.ERROR_MAX_CAMERAS_IN_USE -> ClassroomFocusReason.CAMERA_BUSY
        CameraState.ERROR_CAMERA_DISABLED -> ClassroomFocusReason.CAMERA_UNAVAILABLE
        else -> ClassroomFocusReason.CAMERA_UNAVAILABLE
    }

    private fun isCurrent(session: Session): Boolean =
        currentSession === session && sessionGate.isCurrent(session.id)

    private fun now(): Long = SystemClock.elapsedRealtime()
}

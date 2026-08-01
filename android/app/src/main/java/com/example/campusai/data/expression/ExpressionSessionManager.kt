package com.example.campusai.data.expression

import androidx.camera.view.PreviewView
import androidx.lifecycle.LifecycleOwner
import com.example.campusai.data.focus.FocusObservation
import com.example.campusai.data.focus.FocusObservationConfig
import com.example.campusai.data.focus.FocusState
import com.example.campusai.data.focus.FocusStateProcessor
import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.ExpressionResult
import com.example.campusai.data.model.FocusSessionSummary
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** Activity-owned coordinator: one model/service instance, camera only while Focus is eligible. */
class ExpressionSessionManager(
    private val createService: (Boolean) -> ExpressionRecognitionService,
    initialUseMock: Boolean,
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Default),
    private val observationConfig: FocusObservationConfig = FocusObservationConfig(),
) {
    private val mutex = Mutex()
    private var useMock = initialUseMock
    private var service: ExpressionRecognitionService? = null
    private var previewOwner: LifecycleOwner? = null
    private var previewView: PreviewView? = null
    private var assistanceEnabled = false
    private var cameraPermissionGranted = false
    private var timerRunning = false
    private var pageVisible = false
    private var appForeground = true
    private var processor = FocusStateProcessor(observationConfig)
    private var latestResult = initialResult()

    private val _status = MutableStateFlow<ExpressionServiceStatus>(ExpressionServiceStatus.Off)
    val status: StateFlow<ExpressionServiceStatus> = _status.asStateFlow()
    private val _result = MutableStateFlow(latestResult)
    val result: StateFlow<ExpressionResult> = _result.asStateFlow()
    private val _focusState = MutableStateFlow(FocusState.UNAVAILABLE)
    val focusState: StateFlow<FocusState> = _focusState.asStateFlow()
    private val _gentleReminder = MutableStateFlow<String?>(null)
    val gentleReminder: StateFlow<String?> = _gentleReminder.asStateFlow()
    val modeLabel: String get() = (service as? ObservableExpressionRecognitionService)?.modeLabel ?: if (useMock) "Mock 表情模型" else "本机 LiteRT"

    suspend fun setUseMock(enabled: Boolean) = mutex.withLock {
        if (useMock == enabled) return@withLock
        service?.dispose()
        service = null
        useMock = enabled
        latestResult = initialResult()
        _result.value = latestResult
        _status.value = ExpressionServiceStatus.Off
        _focusState.value = FocusState.UNAVAILABLE
        syncLocked()
    }

    suspend fun updateEligibility(
        enabled: Boolean = assistanceEnabled,
        permissionGranted: Boolean = cameraPermissionGranted,
        running: Boolean = timerRunning,
        visible: Boolean = pageVisible,
        foreground: Boolean = appForeground,
    ) = mutex.withLock {
        assistanceEnabled = enabled
        cameraPermissionGranted = permissionGranted
        timerRunning = running
        pageVisible = visible
        appForeground = foreground
        syncLocked()
    }

    fun attachPreview(owner: LifecycleOwner, view: PreviewView) {
        previewOwner = owner
        previewView = view
        (service as? CameraExpressionRecognitionService)?.bindCamera(owner, view)
    }

    suspend fun detachPreview() = mutex.withLock {
        (service as? CameraExpressionRecognitionService)?.unbindCamera()
        previewOwner = null
        previewView = null
    }

    suspend fun beginFocusSession() = mutex.withLock {
        processor = FocusStateProcessor(observationConfig)
        _gentleReminder.value = null
    }

    suspend fun finishFocusSession(actualFocusMinutes: Int): FocusSessionSummary = mutex.withLock {
        val summary = processor.finish(
            now = System.currentTimeMillis(),
            actualFocusMinutes = actualFocusMinutes,
            modelVersion = latestResult.modelVersion,
        )
        _gentleReminder.value = null
        summary
    }

    suspend fun release() = mutex.withLock {
        (service as? CameraExpressionRecognitionService)?.unbindCamera()
        service?.dispose()
        service = null
        _status.value = ExpressionServiceStatus.Off
        _focusState.value = FocusState.UNAVAILABLE
    }

    private suspend fun syncLocked() {
        val shouldRun = assistanceEnabled && cameraPermissionGranted && timerRunning && pageVisible && appForeground
        if (!shouldRun) {
            (service as? CameraExpressionRecognitionService)?.unbindCamera()
            service?.pause()
            _focusState.value = if (assistanceEnabled) FocusState.UNAVAILABLE else FocusState.UNAVAILABLE
            return
        }
        val target = service ?: createService(useMock).also { created ->
            service = created
            if (created is ObservableExpressionRecognitionService) {
                scope.launch { created.status.collectLatest { _status.value = it } }
            }
            scope.launch {
                created.results().collectLatest { result ->
                    latestResult = result
                    _result.value = result
                    val output = processor.process(
                        FocusObservation(
                            timestamp = result.timestamp,
                            facePresent = result.facePresent,
                            headEulerAngleX = result.headEulerAngleX,
                            headEulerAngleY = result.headEulerAngleY,
                            headEulerAngleZ = result.headEulerAngleZ,
                            leftEyeOpenProbability = result.leftEyeOpenProbability,
                            rightEyeOpenProbability = result.rightEyeOpenProbability,
                            expression = result,
                            inferenceAvailable = result.label != ExpressionLabel.UNKNOWN || result.facePresent,
                        ),
                    )
                    _focusState.value = output.state
                    if (output.events.any { it is com.example.campusai.data.focus.FocusEvent.BreakSuggested }) {
                        _gentleReminder.value = "这是辅助观察结果，建议休息片刻，再继续学习。"
                    }
                }
            }
        }
        target.initialize()
        (target as? CameraExpressionRecognitionService)?.let { cameraService ->
            previewOwner?.let { owner -> previewView?.let { view -> cameraService.bindCamera(owner, view) } }
        }
        target.start()
    }

    private fun initialResult() = ExpressionResult(
        label = ExpressionLabel.UNKNOWN,
        confidence = 0.0,
        probabilities = emptyMap(),
        timestamp = System.currentTimeMillis(),
        isStable = false,
        modelVersion = "not-loaded",
    )
}

package com.example.campusai.data.expression

import androidx.camera.view.PreviewView
import androidx.lifecycle.LifecycleOwner
import android.app.Application
import com.example.campusai.data.behavior.BehaviorAnalyzer
import com.example.campusai.data.behavior.BehaviorPrediction
import com.example.campusai.data.behavior.BehaviorRecognitionEngine
import com.example.campusai.data.behavior.BehaviorSignalProcessor
import com.example.campusai.data.behavior.FocusSupervisor
import com.example.campusai.data.behavior.NoOpBehaviorRecognitionEngine
import com.example.campusai.data.behavior.OnnxBehaviorRecognitionEngine
import com.example.campusai.data.camera.CameraErrorListener
import com.example.campusai.data.focus.FocusObservation
import com.example.campusai.data.focus.FocusObservationConfig
import com.example.campusai.data.focus.FocusState
import com.example.campusai.data.focus.FocusStateProcessor
import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.ExpressionResult
import com.example.campusai.data.model.FocusMode
import com.example.campusai.data.model.FocusSessionSummary
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Activity-owned coordinator: one model/service instance, camera only while Focus is eligible.
 *
 * Lifecycle:
 * - [attachLifecycle] / [detachLifecycle] manage the CameraX LifecycleOwner independently.
 * - [attachPreview] / [detachPreview] manage the PreviewView independently.
 * - Analysis runs when eligible (assistance + permission + timer + page + foreground)
 *   AND focusMode == FOCUS. Breaks pause video analysis.
 * - Preview visibility is orthogonal to analysis.
 */
class ExpressionSessionManager(
    private val application: Application,
    private val createService: (Boolean) -> ExpressionRecognitionService,
    initialUseMock: Boolean,
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Default),
    private val observationConfig: FocusObservationConfig = FocusObservationConfig(),
    createBehaviorEngine: ((Application) -> BehaviorRecognitionEngine)? = null,
) {
    private val mutex = Mutex()
    private val cameraPipeline = com.example.campusai.data.camera.FocusCameraPipeline(application)
    private var useMock = initialUseMock
    private var service: ExpressionRecognitionService? = null
    private var lifecycleOwner: LifecycleOwner? = null
    private var previewView: PreviewView? = null
    private var assistanceEnabled = false
    private var cameraPermissionGranted = false
    private var timerRunning = false
    private var pageVisible = false
    private var appForeground = true
    private var focusMode: FocusMode? = null
    private var processor = FocusStateProcessor(observationConfig)
    private val behaviorAnalyzer = BehaviorAnalyzer(
        createBehaviorEngine?.invoke(application) ?: OnnxBehaviorRecognitionEngine(application),
    )
    private val behaviorSignalProcessor = BehaviorSignalProcessor()
    private val focusSupervisor = FocusSupervisor()
    private var latestResult = initialResult()
    private var releaseJob: kotlinx.coroutines.Job? = null
    private var serviceInitialized = false

    private var behaviorCollectorJob: Job? = null
    private var statusCollectorJob: Job? = null
    private var resultCollectorJob: Job? = null

    private val _status = MutableStateFlow<ExpressionServiceStatus>(ExpressionServiceStatus.Off)
    val status: StateFlow<ExpressionServiceStatus> = _status.asStateFlow()
    private val _result = MutableStateFlow(latestResult)
    val result: StateFlow<ExpressionResult> = _result.asStateFlow()
    private val _focusState = MutableStateFlow(FocusState.UNAVAILABLE)
    val focusState: StateFlow<FocusState> = _focusState.asStateFlow()

    private val _behaviorPrediction = MutableStateFlow<BehaviorPrediction?>(null)
    val behaviorPrediction: StateFlow<BehaviorPrediction?> = _behaviorPrediction.asStateFlow()

    private val _gentleReminder = MutableStateFlow<String?>(null)
    val gentleReminder: StateFlow<String?> = _gentleReminder.asStateFlow()
    val modeLabel: String get() = (service as? ObservableExpressionRecognitionService)?.modeLabel ?: if (useMock) "Mock 表情模型" else "本机 LiteRT"

    init {
        cameraPipeline.errorListener = CameraErrorListener { message ->
            _status.value = ExpressionServiceStatus.Error(message)
        }
    }

    fun attachLifecycle(owner: LifecycleOwner) {
        lifecycleOwner = owner
        cameraPipeline.attachLifecycle(owner)
    }

    fun detachLifecycle() {
        cameraPipeline.detachLifecycle()
        lifecycleOwner = null
    }

    fun attachPreview(view: PreviewView) {
        previewView = view
        cameraPipeline.attachPreview(view)
    }

    fun detachPreview() {
        cameraPipeline.detachPreview()
        previewView = null
    }

    fun attachPreview(owner: LifecycleOwner, view: PreviewView) {
        lifecycleOwner = owner
        previewView = view
        cameraPipeline.bindCamera(owner, view)
    }

    suspend fun setUseMock(enabled: Boolean) {
        releaseJob?.cancel()
        mutex.withLock {
            if (useMock == enabled) return@withLock
            cancelCollectors()
            service?.dispose()
            service = null
            serviceInitialized = false
            useMock = enabled
            latestResult = initialResult()
            _result.value = latestResult
            _status.value = ExpressionServiceStatus.Off
            _focusState.value = FocusState.UNAVAILABLE
            syncLocked()
        }
    }

    suspend fun updateEligibility(
        enabled: Boolean = assistanceEnabled,
        permissionGranted: Boolean = cameraPermissionGranted,
        running: Boolean = timerRunning,
        visible: Boolean = pageVisible,
        foreground: Boolean = appForeground,
        mode: FocusMode? = focusMode,
    ) {
        releaseJob?.cancel()
        mutex.withLock {
            assistanceEnabled = enabled
            cameraPermissionGranted = permissionGranted
            timerRunning = running
            pageVisible = visible
            appForeground = foreground
            focusMode = mode
            syncLocked()
        }
    }

    suspend fun beginFocusSession() {
        releaseJob?.cancel()
        mutex.withLock {
            processor = FocusStateProcessor(observationConfig)
            behaviorSignalProcessor.reset()
            focusSupervisor.reset()
            _gentleReminder.value = null
        }
    }

    suspend fun finishFocusSession(actualFocusMinutes: Int): FocusSessionSummary {
        releaseJob?.cancel()
        return mutex.withLock {
            val summary = processor.finish(
                now = System.currentTimeMillis(),
                actualFocusMinutes = actualFocusMinutes,
                modelVersion = latestResult.modelVersion,
            )
            _gentleReminder.value = null
            summary
        }
    }

    fun releaseAsync() {
        releaseJob?.cancel()
        releaseJob = scope.launch { release() }
    }

    suspend fun release() = mutex.withLock {
        cancelCollectors()
        cameraPipeline.unbindCamera()
        cameraPipeline.dispose()
        service?.let { cameraPipeline.removeAnalyzer(it) }
        cameraPipeline.removeAnalyzer(behaviorAnalyzer)
        behaviorAnalyzer.dispose()
        service?.dispose()
        service = null
        serviceInitialized = false
        _status.value = ExpressionServiceStatus.Off
        _focusState.value = FocusState.UNAVAILABLE
    }

    private fun cancelCollectors() {
        behaviorCollectorJob?.cancel()
        behaviorCollectorJob = null
        statusCollectorJob?.cancel()
        statusCollectorJob = null
        resultCollectorJob?.cancel()
        resultCollectorJob = null
    }

    private suspend fun syncLocked() {
        val eligible = assistanceEnabled && cameraPermissionGranted && timerRunning && pageVisible && appForeground
        val shouldRun = eligible && focusMode == FocusMode.FOCUS

        if (!shouldRun) {
            cameraPipeline.pause()
            service?.pause()
            val fallbackStatus: ExpressionServiceStatus = when {
                !assistanceEnabled -> ExpressionServiceStatus.Off
                !cameraPermissionGranted -> ExpressionServiceStatus.Error("需要摄像头权限")
                !timerRunning -> ExpressionServiceStatus.Ready
                !pageVisible || !appForeground -> ExpressionServiceStatus.Paused
                focusMode != FocusMode.FOCUS -> ExpressionServiceStatus.Paused
                else -> ExpressionServiceStatus.Off
            }
            if (_status.value !is ExpressionServiceStatus.Error) {
                _status.value = fallbackStatus
            }
            _focusState.value = FocusState.UNAVAILABLE
            return
        }

        val target = service ?: createService(useMock).also { created ->
            service = created
            cameraPipeline.addAnalyzer(created)
            behaviorAnalyzer.ensureInitialized()
            cameraPipeline.addAnalyzer(behaviorAnalyzer)

            cancelCollectors()

            behaviorCollectorJob = scope.launch {
                behaviorAnalyzer.predictions.collectLatest { prediction ->
                    _behaviorPrediction.value = prediction
                    val events = behaviorSignalProcessor.process(prediction)
                    val behaviorFocusState = focusSupervisor.processEvents(events, prediction.timestampMs)

                    if (behaviorFocusState != FocusState.FOCUSED || prediction.modelState != "MODEL_NOT_AVAILABLE") {
                        _focusState.value = behaviorFocusState
                    }
                }
            }

            if (created is ObservableExpressionRecognitionService) {
                statusCollectorJob = scope.launch {
                    created.status.collectLatest { _status.value = it }
                }
            }

            resultCollectorJob = scope.launch {
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

                    if (_behaviorPrediction.value?.modelState == "MODEL_NOT_AVAILABLE" ||
                        _focusState.value == FocusState.FOCUSED ||
                        _focusState.value == FocusState.UNAVAILABLE
                    ) {
                        _focusState.value = output.state
                    }

                    if (output.events.any { it is com.example.campusai.data.focus.FocusEvent.BreakSuggested }) {
                        _gentleReminder.value = "这是辅助观察结果，建议休息片刻，再继续学习。"
                    }
                }
            }
        }
        if (!serviceInitialized) {
            target.initialize()
            serviceInitialized = true
        }
        cameraPipeline.start()
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

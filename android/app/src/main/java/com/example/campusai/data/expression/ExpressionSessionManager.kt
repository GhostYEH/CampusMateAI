package com.example.campusai.data.expression

import androidx.camera.view.PreviewView
import androidx.lifecycle.LifecycleOwner
import android.app.Application
import com.example.campusai.data.behavior.BehaviorAnalyzer
import com.example.campusai.data.behavior.BehaviorDisplayState
import com.example.campusai.data.behavior.BehaviorInputDebugExporter
import com.example.campusai.data.behavior.BehaviorObservationHistory
import com.example.campusai.data.behavior.BehaviorObservationSnapshot
import com.example.campusai.data.behavior.LearningContinuityState
import com.example.campusai.data.behavior.LearningContinuityStateMachine
import com.example.campusai.data.behavior.BehaviorPrediction
import com.example.campusai.data.behavior.BehaviorSignalProcessor
import com.example.campusai.data.behavior.FocusSupervisor
import com.example.campusai.data.behavior.OnnxBehaviorRecognitionEngine
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
    private val application: Application,
    private val createService: (Boolean) -> ExpressionRecognitionService,
    initialUseMock: Boolean,
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Default),
    private val observationConfig: FocusObservationConfig = FocusObservationConfig(),
) {
    private val mutex = Mutex()
    private val cameraPipeline = com.example.campusai.data.camera.FocusCameraPipeline(application)
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
    private val behaviorAnalyzer = BehaviorAnalyzer(OnnxBehaviorRecognitionEngine(application))
    private val behaviorSignalProcessor = BehaviorSignalProcessor()
    private val behaviorObservationHistory = BehaviorObservationHistory()
    private val learningContinuityStateMachine = LearningContinuityStateMachine()
    private val focusSupervisor = FocusSupervisor()
    private var latestResult = initialResult()
    private var releaseJob: kotlinx.coroutines.Job? = null

    private val _status = MutableStateFlow<ExpressionServiceStatus>(ExpressionServiceStatus.Off)
    val status: StateFlow<ExpressionServiceStatus> = _status.asStateFlow()
    private val _result = MutableStateFlow(latestResult)
    val result: StateFlow<ExpressionResult> = _result.asStateFlow()
    private val _focusState = MutableStateFlow(FocusState.UNAVAILABLE)
    val focusState: StateFlow<FocusState> = _focusState.asStateFlow()
    
    private val _behaviorPrediction = MutableStateFlow<BehaviorPrediction?>(null)
    val behaviorPrediction: StateFlow<BehaviorPrediction?> = _behaviorPrediction.asStateFlow()
    private val _behaviorDisplayState = MutableStateFlow<BehaviorDisplayState>(BehaviorDisplayState.Observing)
    val behaviorDisplayState: StateFlow<BehaviorDisplayState> = _behaviorDisplayState.asStateFlow()
    private val _behaviorObservation = MutableStateFlow(BehaviorObservationSnapshot())
    val behaviorObservation: StateFlow<BehaviorObservationSnapshot> = _behaviorObservation.asStateFlow()
    private val _learningContinuityState = MutableStateFlow(LearningContinuityState.OBSERVING)
    val learningContinuityState: StateFlow<LearningContinuityState> = _learningContinuityState.asStateFlow()
    private var behaviorObservationActive = false

    private val _gentleReminder = MutableStateFlow<String?>(null)
    val gentleReminder: StateFlow<String?> = _gentleReminder.asStateFlow()
    val modeLabel: String get() = (service as? ObservableExpressionRecognitionService)?.modeLabel ?: if (useMock) "Mock 表情模型" else "本机 LiteRT"

    suspend fun setUseMock(enabled: Boolean) {
        releaseJob?.cancel()
        mutex.withLock {
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
    }

    suspend fun updateEligibility(
        enabled: Boolean = assistanceEnabled,
        permissionGranted: Boolean = cameraPermissionGranted,
        running: Boolean = timerRunning,
        visible: Boolean = pageVisible,
        foreground: Boolean = appForeground,
    ) {
        releaseJob?.cancel()
        mutex.withLock {
            assistanceEnabled = enabled
            cameraPermissionGranted = permissionGranted
            timerRunning = running
            pageVisible = visible
            appForeground = foreground
            syncLocked()
        }
    }

    fun attachPreview(owner: LifecycleOwner, view: PreviewView) {
        previewOwner = owner
        previewView = view
        cameraPipeline.bindCamera(owner, view)
    }

    suspend fun detachPreview() {
        releaseJob?.cancel()
        mutex.withLock {
            cameraPipeline.unbindCamera()
            previewOwner = null
            previewView = null
        }
    }

    /**
     * Fire-and-forget teardown for the UI: stops the camera and marks the page
     * ineligible, but keeps the loaded model warm for the next visit. Runs on the
     * manager's own scope so it survives the composable being disposed.
     */
    fun detachPreviewAsync() {
        scope.launch {
            updateEligibility(visible = false, running = false)
            detachPreview()
        }
    }

    suspend fun beginFocusSession() {
        releaseJob?.cancel()
        mutex.withLock {
            processor = FocusStateProcessor(observationConfig)
            behaviorSignalProcessor.reset()
            learningContinuityStateMachine.reset()
            _learningContinuityState.value = LearningContinuityState.OBSERVING
            behaviorObservationHistory.reset(System.currentTimeMillis())
            _behaviorObservation.value = behaviorObservationHistory.snapshot()
            _behaviorDisplayState.value = BehaviorDisplayState.Observing
            behaviorObservationActive = false
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
            // Also return behavior stats, could be added to FocusSessionSummary in the future
            val behaviorStats = focusSupervisor.stats
            summary
        }
    }

    fun releaseAsync() {
        releaseJob?.cancel()
        releaseJob = scope.launch { release() }
    }

    suspend fun release() = mutex.withLock {
        cameraPipeline.unbindCamera()
        cameraPipeline.dispose()
        service?.let { cameraPipeline.removeAnalyzer(it) }
        cameraPipeline.removeAnalyzer(behaviorAnalyzer)
        behaviorAnalyzer.dispose()
        service?.dispose()
        service = null
        _status.value = ExpressionServiceStatus.Off
        _focusState.value = FocusState.UNAVAILABLE
    }

    private suspend fun syncLocked() {
        val shouldRun = assistanceEnabled && cameraPermissionGranted && timerRunning && pageVisible && appForeground
        android.util.Log.i(
            "FocusEligibility",
            "enabled=$assistanceEnabled, " +
                    "permission=$cameraPermissionGranted, " +
                    "timer=$timerRunning, " +
                    "visible=$pageVisible, " +
                    "foreground=$appForeground, " +
                    "shouldRun=$shouldRun"
        )
        if (!shouldRun) {
            cameraPipeline.unbindCamera()
            cameraPipeline.pause()
            service?.pause()
            behaviorSignalProcessor.reset()
            _behaviorDisplayState.value = BehaviorDisplayState.Observing
            behaviorObservationActive = false
            _focusState.value = if (assistanceEnabled) FocusState.UNAVAILABLE else FocusState.UNAVAILABLE
            return
        }
        if (!behaviorObservationActive) {
            behaviorSignalProcessor.reset()
            behaviorSignalProcessor.beginBehaviorObservation(System.currentTimeMillis())
            _behaviorDisplayState.value = BehaviorDisplayState.Observing
            behaviorObservationActive = true
        }
        val target = service ?: createService(useMock).also { created ->
            service = created
            cameraPipeline.addAnalyzer(created)
            behaviorAnalyzer.ensureInitialized()
            cameraPipeline.addAnalyzer(behaviorAnalyzer)
            
            scope.launch {
                behaviorAnalyzer.predictions.collectLatest { prediction ->
                    _behaviorPrediction.value = prediction
                    val displayState = behaviorSignalProcessor.processDisplayState(prediction)
                    _behaviorDisplayState.value = displayState
                    val continuity = learningContinuityStateMachine.process(displayState, prediction.timestampMs)
                    _learningContinuityState.value = continuity.state
                    behaviorObservationHistory.record(continuity.state, prediction.timestampMs)
                    _behaviorObservation.value = behaviorObservationHistory.snapshot()
                    BehaviorInputDebugExporter.recordPrediction(application, prediction, displayState)
                    val events = behaviorSignalProcessor.process(prediction)
                    val behaviorFocusState = focusSupervisor.processEvents(events, prediction.timestampMs)
                    
                    // We only update if we got a state that needs attention or if we have a stable prediction
                    if (behaviorFocusState != FocusState.FOCUSED || prediction.modelState != "MODEL_NOT_AVAILABLE") {
                        _focusState.value = behaviorFocusState
                    }
                }
            }

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
                    
                    // Only let expression override if behavior hasn't signaled something more critical
                    if (_behaviorPrediction.value?.modelState == "MODEL_NOT_AVAILABLE" || 
                        _focusState.value == FocusState.FOCUSED || 
                        _focusState.value == FocusState.UNAVAILABLE) {
                        _focusState.value = output.state
                    }
                    
                    if (output.events.any { it is com.example.campusai.data.focus.FocusEvent.BreakSuggested }) {
                        _gentleReminder.value = "这是辅助观察结果，建议休息片刻，再继续学习。"
                    }
                }
            }
        }
        target.initialize()
        previewOwner?.let { owner -> previewView?.let { view -> cameraPipeline.bindCamera(owner, view) } }
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

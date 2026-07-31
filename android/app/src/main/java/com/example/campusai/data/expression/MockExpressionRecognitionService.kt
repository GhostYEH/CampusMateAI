package com.example.campusai.data.expression

import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.ExpressionResult
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class MockExpressionRecognitionService : ObservableExpressionRecognitionService {
    private var scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var job: Job? = null
    private val _status = MutableStateFlow<ExpressionServiceStatus>(ExpressionServiceStatus.Off)
    override val status: StateFlow<ExpressionServiceStatus> = _status.asStateFlow()
    private val _results = MutableStateFlow(
        ExpressionResult(
            ExpressionLabel.UNKNOWN,
            0.0,
            emptyMap(),
            System.currentTimeMillis(),
            false,
            MODEL_VERSION,
        ),
    )
    override val modeLabel = "Mock 表情模型"

    override fun results(): Flow<ExpressionResult> = _results

    override suspend fun initialize() {
        ensureScope()
        _status.value = ExpressionServiceStatus.Initializing
        delay(180)
        _status.value = ExpressionServiceStatus.Ready
    }

    override suspend fun start() {
        if (_status.value == ExpressionServiceStatus.Off) initialize()
        _status.value = ExpressionServiceStatus.Running
        job?.cancel()
        job = scope.launch {
            var frames = 0
            while (true) {
                delay(240)
                frames += 1
                _results.value = ExpressionResult(
                    label = ExpressionLabel.NEUTRAL,
                    confidence = 0.78,
                    probabilities = mapOf(
                        ExpressionLabel.NEUTRAL to 0.78,
                        ExpressionLabel.HAPPY to 0.12,
                        ExpressionLabel.SAD to 0.10,
                    ),
                    timestamp = System.currentTimeMillis(),
                    isStable = frames >= 4,
                    modelVersion = MODEL_VERSION,
                )
            }
        }
    }

    override suspend fun pause() {
        job?.cancel()
        job = null
        _status.value = ExpressionServiceStatus.Paused
    }

    override suspend fun stop() {
        job?.cancel()
        job = null
        _status.value = ExpressionServiceStatus.Ready
    }

    override suspend fun dispose() {
        job?.cancel()
        scope.cancel()
        _status.value = ExpressionServiceStatus.Off
    }

    private fun ensureScope() {
        if (!scope.coroutineContext[Job]!!.isActive) {
            scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        }
    }

    companion object {
        const val MODEL_VERSION = "mock-expression-v1"
    }
}

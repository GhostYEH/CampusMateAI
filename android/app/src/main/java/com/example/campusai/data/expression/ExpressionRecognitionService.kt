package com.example.campusai.data.expression

import androidx.camera.view.PreviewView
import androidx.lifecycle.LifecycleOwner
import com.example.campusai.data.model.ExpressionResult
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow

interface ExpressionRecognitionService {
    fun results(): Flow<ExpressionResult>
    suspend fun initialize()
    suspend fun start()
    suspend fun pause()
    suspend fun stop()
    suspend fun dispose()
}

sealed interface ExpressionServiceStatus {
    data object Off : ExpressionServiceStatus
    data object Initializing : ExpressionServiceStatus
    data object Ready : ExpressionServiceStatus
    data object Running : ExpressionServiceStatus
    data object Paused : ExpressionServiceStatus
    data object NoFace : ExpressionServiceStatus
    data object LowConfidence : ExpressionServiceStatus
    data class Error(val message: String) : ExpressionServiceStatus
}

interface ObservableExpressionRecognitionService : ExpressionRecognitionService {
    val status: StateFlow<ExpressionServiceStatus>
    val modeLabel: String
}

interface CameraExpressionRecognitionService : ObservableExpressionRecognitionService {
    fun bindCamera(lifecycleOwner: LifecycleOwner, previewView: PreviewView)
    fun unbindCamera()
}

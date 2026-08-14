package com.example.campusai

import android.app.Application
import com.example.campusai.data.behavior.NoOpBehaviorRecognitionEngine
import com.example.campusai.data.camera.CameraFrame
import com.example.campusai.data.expression.ExpressionRecognitionService
import com.example.campusai.data.expression.ExpressionSessionManager
import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.ExpressionResult
import com.example.campusai.data.model.FocusMode
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Test
import org.mockito.Mockito

class ExpressionSessionManagerTest {
    @Test fun pauseOnTimerStopAndDisposeOnRelease() = runBlocking {
        val fake = FakeService()
        val application = Mockito.mock(Application::class.java)
        val manager = ExpressionSessionManager(
            application = application,
            createService = { fake },
            initialUseMock = false,
            createBehaviorEngine = { NoOpBehaviorRecognitionEngine() },
        )
        manager.updateEligibility(
            enabled = true,
            permissionGranted = true,
            running = true,
            visible = true,
            foreground = true,
            mode = FocusMode.FOCUS,
        )
        assertEquals(1, fake.starts)
        manager.updateEligibility(running = false)
        assertEquals(1, fake.pauses)
        manager.release()
        assertEquals(1, fake.disposals)
    }

    @Test fun shortBreakPausesAnalysis() = runBlocking {
        val fake = FakeService()
        val application = Mockito.mock(Application::class.java)
        val manager = ExpressionSessionManager(
            application = application,
            createService = { fake },
            initialUseMock = false,
            createBehaviorEngine = { NoOpBehaviorRecognitionEngine() },
        )
        manager.updateEligibility(
            enabled = true,
            permissionGranted = true,
            running = true,
            visible = true,
            foreground = true,
            mode = FocusMode.FOCUS,
        )
        assertEquals(1, fake.starts)
        manager.updateEligibility(mode = FocusMode.SHORT_BREAK)
        assertEquals(1, fake.pauses)
        manager.release()
    }

    @Test fun longBreakPausesAnalysis() = runBlocking {
        val fake = FakeService()
        val application = Mockito.mock(Application::class.java)
        val manager = ExpressionSessionManager(
            application = application,
            createService = { fake },
            initialUseMock = false,
            createBehaviorEngine = { NoOpBehaviorRecognitionEngine() },
        )
        manager.updateEligibility(
            enabled = true,
            permissionGranted = true,
            running = true,
            visible = true,
            foreground = true,
            mode = FocusMode.FOCUS,
        )
        assertEquals(1, fake.starts)
        manager.updateEligibility(mode = FocusMode.LONG_BREAK)
        assertEquals(1, fake.pauses)
        manager.release()
    }

    private class FakeService : ExpressionRecognitionService {
        private val stream = MutableStateFlow(ExpressionResult(ExpressionLabel.NEUTRAL, .9, emptyMap(), 1, true, "fake", facePresent = true))
        var starts = 0
        var pauses = 0
        var disposals = 0
        override fun analyze(frame: CameraFrame) {}
        override fun results(): Flow<ExpressionResult> = stream
        override suspend fun initialize() = Unit
        override suspend fun start() { starts++ }
        override suspend fun pause() { pauses++ }
        override suspend fun stop() = Unit
        override suspend fun dispose() { disposals++ }
    }
}

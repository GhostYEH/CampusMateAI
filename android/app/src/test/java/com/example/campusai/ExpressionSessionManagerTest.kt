package com.example.campusai

import android.app.Application
import com.example.campusai.data.behavior.NoOpBehaviorRecognitionEngine
import com.example.campusai.data.behavior.PersonDetectionSnapshot
import com.example.campusai.data.behavior.LearningContinuityState
import com.example.campusai.data.behavior.PresenceSnapshot
import com.example.campusai.data.camera.CameraFrame
import com.example.campusai.data.expression.ExpressionRecognitionService
import com.example.campusai.data.expression.ExpressionSessionManager
import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.ExpressionResult
import com.example.campusai.data.model.FocusMode
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.Mockito

class ExpressionSessionManagerTest {
    @Test fun counselorStartsWithoutFocusTimer() = runBlocking {
        val fake = FakeService()
        val application = Mockito.mock(Application::class.java)
        val manager = ExpressionSessionManager(
            application = application,
            createService = { fake },
            initialUseMock = false,
            createBehaviorEngine = { NoOpBehaviorRecognitionEngine() },
        )

        manager.updateCounselorEligibility(
            enabled = true,
            permissionGranted = true,
            visible = true,
            foreground = true,
        )

        assertEquals(1, fake.starts)
        manager.updateCounselorEligibility(visible = false)
        assertEquals(1, fake.pauses)
        manager.release()
    }

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

    @Test fun stoppingObservationClearsTransientRecognitionState() = runBlocking {
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
        fake.emit(ExpressionResult(ExpressionLabel.HAPPY, .9, emptyMap(), 2, true, "fake", facePresent = true))
        repeat(50) {
            if (manager.result.value.label == ExpressionLabel.HAPPY) return@repeat
            delay(10)
        }
        assertTrue(manager.observationActive.value)
        assertEquals(ExpressionLabel.HAPPY, manager.result.value.label)

        manager.updateEligibility(running = false)

        assertFalse(manager.observationActive.value)
        assertEquals(ExpressionLabel.UNKNOWN, manager.result.value.label)
        assertEquals(PresenceSnapshot(), manager.presence.value)
        assertEquals(PersonDetectionSnapshot(), manager.personDetection.value)
        assertEquals(null, manager.behaviorPrediction.value)
        assertEquals(LearningContinuityState.OBSERVING, manager.learningContinuityState.value)
        assertEquals(null, manager.gentleReminder.value)
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
        fun emit(result: ExpressionResult) { stream.value = result }
    }
}

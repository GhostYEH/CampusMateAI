package com.example.campusai

import android.app.Application
import com.example.campusai.data.camera.CameraFrame
import com.example.campusai.data.expression.ExpressionRecognitionService
import com.example.campusai.data.expression.ExpressionServiceStatus
import com.example.campusai.data.expression.ExpressionSessionManager
import com.example.campusai.data.focus.FocusState
import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.ExpressionResult
import com.example.campusai.data.model.FocusMode
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test
import org.mockito.Mockito
import java.util.concurrent.atomic.AtomicInteger

class ExpressionSessionManagerTest {

    // ── Basic lifecycle ──

    @Test fun pauseOnTimerStopAndDisposeOnRelease() = runBlocking {
        val fake = FakeService()
        val application = Mockito.mock(Application::class.java)
        val manager = ExpressionSessionManager(
            application = application,
            createService = { fake },
            initialUseMock = false,
        )
        manager.updateEligibility(
            enabled = true, permissionGranted = true, running = true,
            visible = true, foreground = true, mode = FocusMode.FOCUS,
        )
        assertEquals(1, fake.starts)
        manager.updateEligibility(running = false)
        assertEquals(1, fake.pauses)
        manager.release()
        assertEquals(1, fake.disposals)
    }

    // ── Eligibility gates ──

    @Test fun disabledDoesNotStartService() = runBlocking {
        val fake = FakeService()
        val application = Mockito.mock(Application::class.java)
        val manager = ExpressionSessionManager(
            application = application, createService = { fake }, initialUseMock = false,
        )
        manager.updateEligibility(
            enabled = false, permissionGranted = true, running = true,
            visible = true, foreground = true, mode = FocusMode.FOCUS,
        )
        assertEquals(0, fake.starts)
        assertEquals(ExpressionServiceStatus.Off::class, manager.status.value::class)
        manager.release()
    }

    @Test fun noPermissionDoesNotStartService() = runBlocking {
        val fake = FakeService()
        val application = Mockito.mock(Application::class.java)
        val manager = ExpressionSessionManager(
            application = application, createService = { fake }, initialUseMock = false,
        )
        manager.updateEligibility(
            enabled = true, permissionGranted = false, running = true,
            visible = true, foreground = true, mode = FocusMode.FOCUS,
        )
        assertEquals(0, fake.starts)
        assertTrue(manager.status.value is ExpressionServiceStatus.Error)
        manager.release()
    }

    @Test fun timerInactiveDoesNotStartService() = runBlocking {
        val fake = FakeService()
        val application = Mockito.mock(Application::class.java)
        val manager = ExpressionSessionManager(
            application = application, createService = { fake }, initialUseMock = false,
        )
        manager.updateEligibility(
            enabled = true, permissionGranted = true, running = false,
            visible = true, foreground = true, mode = FocusMode.FOCUS,
        )
        assertEquals(0, fake.starts)
        manager.release()
    }

    @Test fun pageInvisibleDoesNotRun() = runBlocking {
        val fake = FakeService()
        val application = Mockito.mock(Application::class.java)
        val manager = ExpressionSessionManager(
            application = application, createService = { fake }, initialUseMock = false,
        )
        manager.updateEligibility(
            enabled = true, permissionGranted = true, running = true,
            visible = false, foreground = true, mode = FocusMode.FOCUS,
        )
        assertEquals(0, fake.starts)
        manager.release()
    }

    @Test fun appBackgroundDoesNotRun() = runBlocking {
        val fake = FakeService()
        val application = Mockito.mock(Application::class.java)
        val manager = ExpressionSessionManager(
            application = application, createService = { fake }, initialUseMock = false,
        )
        manager.updateEligibility(
            enabled = true, permissionGranted = true, running = true,
            visible = true, foreground = false, mode = FocusMode.FOCUS,
        )
        assertEquals(0, fake.starts)
        manager.release()
    }

    // ── Focus mode gating ──

    @Test fun shortBreakDoesNotRunAnalysis() = runBlocking {
        val fake = FakeService()
        val application = Mockito.mock(Application::class.java)
        val manager = ExpressionSessionManager(
            application = application, createService = { fake }, initialUseMock = false,
        )
        manager.updateEligibility(
            enabled = true, permissionGranted = true, running = true,
            visible = true, foreground = true, mode = FocusMode.SHORT_BREAK,
        )
        assertEquals(0, fake.starts)
        manager.release()
    }

    @Test fun longBreakDoesNotRunAnalysis() = runBlocking {
        val fake = FakeService()
        val application = Mockito.mock(Application::class.java)
        val manager = ExpressionSessionManager(
            application = application, createService = { fake }, initialUseMock = false,
        )
        manager.updateEligibility(
            enabled = true, permissionGranted = true, running = true,
            visible = true, foreground = true, mode = FocusMode.LONG_BREAK,
        )
        assertEquals(0, fake.starts)
        manager.release()
    }

    @Test fun onlyFocusModeStartsAnalysis() = runBlocking {
        val fake = FakeService()
        val application = Mockito.mock(Application::class.java)
        val manager = ExpressionSessionManager(
            application = application, createService = { fake }, initialUseMock = false,
        )
        manager.updateEligibility(
            enabled = true, permissionGranted = true, running = true,
            visible = true, foreground = true, mode = FocusMode.FOCUS,
        )
        assertEquals(1, fake.starts)
        manager.release()
    }

    // ── Eligible → ineligible → eligible recovery ──

    @Test fun eligiblePausedEligibleRecovers() = runBlocking {
        val fake = FakeService()
        val application = Mockito.mock(Application::class.java)
        val manager = ExpressionSessionManager(
            application = application, createService = { fake }, initialUseMock = false,
        )
        // Start eligible
        manager.updateEligibility(true, true, true, true, true, FocusMode.FOCUS)
        assertEquals(1, fake.starts)
        assertEquals(1, fake.initializes)

        // Become ineligible (page invisible)
        manager.updateEligibility(true, true, true, false, true, FocusMode.FOCUS)
        assertEquals(1, fake.pauses)

        // Become eligible again
        manager.updateEligibility(true, true, true, true, true, FocusMode.FOCUS)
        assertEquals(2, fake.starts) // resumed
        assertEquals(1, fake.initializes) // not re-initialized (service same)

        manager.release()
        assertEquals(1, fake.disposals)
    }

    // ── Duplicate collector prevention ──

    @Test fun repeatedEligibilityDoesNotDuplicateCollectors() = runBlocking {
        val fake = FakeService()
        val application = Mockito.mock(Application::class.java)
        val manager = ExpressionSessionManager(
            application = application, createService = { fake }, initialUseMock = false,
        )
        // First eligibility
        manager.updateEligibility(true, true, true, true, true, FocusMode.FOCUS)
        assertEquals(1, fake.starts)

        // Repeated with same parameters
        for (i in 1..5) {
            manager.updateEligibility(true, true, true, true, true, FocusMode.FOCUS)
        }
        // Still only 1 service created — no duplicate collectors
        assertEquals(1, fake.initializes)

        manager.release()
    }

    // ── beginFocusSession resets state ──

    @Test fun beginFocusSessionResetsProcessor() = runBlocking {
        val fake = FakeService()
        val application = Mockito.mock(Application::class.java)
        val manager = ExpressionSessionManager(
            application = application, createService = { fake }, initialUseMock = false,
        )
        manager.updateEligibility(true, true, true, true, true, FocusMode.FOCUS)
        // beginFocusSession should not throw
        manager.beginFocusSession()
        assertEquals(FocusState.UNAVAILABLE, manager.focusState.value)
        manager.release()
    }

    // ── Status mapping to focus state ──

    @Test fun ineligibleShowsUnavailable() = runBlocking {
        val fake = FakeService()
        val application = Mockito.mock(Application::class.java)
        val manager = ExpressionSessionManager(
            application = application, createService = { fake }, initialUseMock = false,
        )
        manager.updateEligibility(
            enabled = false, permissionGranted = true, running = true,
            visible = true, foreground = true, mode = FocusMode.FOCUS,
        )
        assertEquals(FocusState.UNAVAILABLE, manager.focusState.value)
        manager.release()
    }

    // ── Fake service ──

    private class FakeService : ExpressionRecognitionService {
        private val stream = MutableStateFlow(
            ExpressionResult(
                ExpressionLabel.NEUTRAL, .9, emptyMap(), 1, true, "fake",
                facePresent = true,
            ),
        )
        var starts = 0
        var pauses = 0
        var disposals = 0
        var initializes = 0
        override fun analyze(frame: CameraFrame) {}
        override fun results(): Flow<ExpressionResult> = stream
        override suspend fun initialize() { initializes++ }
        override suspend fun start() { starts++ }
        override suspend fun pause() { pauses++ }
        override suspend fun stop() = Unit
        override suspend fun dispose() { disposals++ }
    }
}

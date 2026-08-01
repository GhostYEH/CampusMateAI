package com.example.campusai

import com.example.campusai.data.expression.ExpressionRecognitionService
import com.example.campusai.data.expression.ExpressionSessionManager
import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.ExpressionResult
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Test

class ExpressionSessionManagerTest {
    @Test fun pauseOnTimerStopAndDisposeOnRelease() = runBlocking {
        val fake = FakeService()
        val manager = ExpressionSessionManager(createService = { fake }, initialUseMock = false)
        manager.updateEligibility(enabled = true, permissionGranted = true, running = true, visible = true, foreground = true)
        assertEquals(1, fake.starts)
        manager.updateEligibility(running = false)
        assertEquals(1, fake.pauses)
        manager.release()
        assertEquals(1, fake.disposals)
    }

    private class FakeService : ExpressionRecognitionService {
        private val stream = MutableStateFlow(ExpressionResult(ExpressionLabel.NEUTRAL, .9, emptyMap(), 1, true, "fake", facePresent = true))
        var starts = 0
        var pauses = 0
        var disposals = 0
        override fun results(): Flow<ExpressionResult> = stream
        override suspend fun initialize() = Unit
        override suspend fun start() { starts++ }
        override suspend fun pause() { pauses++ }
        override suspend fun stop() = Unit
        override suspend fun dispose() { disposals++ }
    }
}

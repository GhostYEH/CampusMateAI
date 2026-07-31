package com.example.campusai

import com.example.campusai.data.expression.ExpressionServiceStatus
import com.example.campusai.data.expression.MockExpressionRecognitionService
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Test

class MockExpressionRecognitionServiceTest {
    @Test
    fun lifecycleTransitionsReleaseAndCanInitialize() = runBlocking {
        val service = MockExpressionRecognitionService()
        service.initialize()
        assertEquals(ExpressionServiceStatus.Ready, service.status.value)
        service.start()
        assertEquals(ExpressionServiceStatus.Running, service.status.value)
        service.pause()
        assertEquals(ExpressionServiceStatus.Paused, service.status.value)
        service.stop()
        assertEquals(ExpressionServiceStatus.Ready, service.status.value)
        service.dispose()
        assertEquals(ExpressionServiceStatus.Off, service.status.value)
        service.initialize()
        assertEquals(ExpressionServiceStatus.Ready, service.status.value)
        service.dispose()
    }
}

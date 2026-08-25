package com.example.campusai.ui.screens.counselor

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class CounselorViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    @Before fun setUp() = Dispatchers.setMain(dispatcher)
    @After fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `send publishes every chunk before completion and queues final speech`() = runTest(dispatcher) {
        val finish = CompletableDeferred<Unit>()
        val viewModel = CounselorViewModel(
            streamer = CpmChatStreamer { _, emit ->
                emit("实时")
                finish.await()
                emit("回答")
            },
            clock = { 100L },
        )
        viewModel.updateInput("怎么规划大学生活？")

        viewModel.send()
        runCurrent()

        assertTrue(viewModel.uiState.value.chatActive)
        assertTrue(viewModel.uiState.value.sending)
        assertEquals("实时", viewModel.uiState.value.messages.last().content)

        finish.complete(Unit)
        advanceUntilIdle()

        assertEquals("实时回答", viewModel.uiState.value.messages.last().content)
        assertEquals(CpmMessageStatus.COMPLETED, viewModel.uiState.value.messages.last().status)
        assertEquals("实时回答", viewModel.uiState.value.speechText)
        assertEquals(1, viewModel.uiState.value.speechRequestId)
    }

    @Test
    fun `retry resends the last user prompt after an error`() = runTest(dispatcher) {
        var attempts = 0
        val viewModel = CounselorViewModel(
            streamer = CpmChatStreamer { _, emit ->
                attempts += 1
                if (attempts == 1) throw IllegalStateException("offline")
                emit("重试成功")
            },
            clock = { attempts.toLong() + 1L },
        )
        viewModel.updateInput("原问题")
        viewModel.send()
        advanceUntilIdle()
        assertEquals(CpmMessageStatus.ERROR, viewModel.uiState.value.messages.last().status)

        viewModel.retryLast()
        advanceUntilIdle()

        assertEquals(2, attempts)
        assertEquals("重试成功", viewModel.uiState.value.messages.last().content)
    }
}

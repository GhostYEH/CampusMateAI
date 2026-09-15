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
import org.junit.Assert.assertNull
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
            streamer = CpmChatStreamer { _, _, _, emit ->
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
            streamer = CpmChatStreamer { _, _, _, emit ->
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

    @Test
    fun `plain chat sends null courseId and keeps no course context`() = runTest(dispatcher) {
        var sentCourseId: String? = "not-sent"
        val viewModel = CounselorViewModel(
            streamer = CpmChatStreamer { _, _, courseId, emit ->
                sentCourseId = courseId
                emit("你好")
            },
            clock = { 1L },
        )
        viewModel.updateInput("普通问题")
        viewModel.send()
        advanceUntilIdle()

        assertNull(sentCourseId)
        assertNull(viewModel.uiState.value.courseContext)
    }

    @Test
    fun `course session keeps courseId and forwards it to streaming chat`() = runTest(dispatcher) {
        var sentCourseId: String? = null
        val course = CpmCourseContext(courseId = "course-42", courseName = "数据结构")
        val viewModel = CounselorViewModel(
            streamer = CpmChatStreamer { _, _, courseId, emit ->
                sentCourseId = courseId
                emit("围绕课程回答")
            },
            clock = { 2L },
            initialCourse = course,
        )
        viewModel.updateInput("请讲解链表")
        viewModel.send()
        runCurrent()
        val second = sentCourseId
        viewModel.send("再问一次")
        advanceUntilIdle()

        assertEquals("course-42", viewModel.uiState.value.courseContext?.courseId)
        assertEquals("course-42", second)
        assertEquals("course-42", sentCourseId)
    }

    @Test
    fun `starting a new plain session clears old courseId`() = runTest(dispatcher) {
        val viewModel = CounselorViewModel(
            streamer = CpmChatStreamer { _, _, _, emit -> emit("ok") },
            clock = { 3L },
            initialCourse = CpmCourseContext(courseId = "course-9", courseName = "高数"),
        )
        assertTrue(viewModel.uiState.value.courseContext != null)

        viewModel.startPlainSession()

        assertNull(viewModel.uiState.value.courseContext)
    }
}
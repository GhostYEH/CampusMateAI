package com.example.campusai.data.classroom.nativeplayer

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ClassroomSequenceWaitTest {

    @Test
    fun `signal before deadline returns value`() = runTest {
        val signal = CompletableDeferred<String>()
        var result: ClassroomSequenceWait<String>? = null
        val job = launch {
            result = awaitClassroomSequenceSignal(
                timeoutMs = 5_000L,
                isCurrent = { true },
                awaitPause = {},
                awaitSignal = { signal.await() },
            )
        }
        runCurrent()
        signal.complete("ready")
        advanceUntilIdle()
        job.join()
        assertEquals(ClassroomSequenceWait.Value("ready"), result)
    }

    @Test
    fun `missing signal ends in timeout`() = runTest {
        val result = awaitClassroomSequenceSignal(
            timeoutMs = 3_000L,
            isCurrent = { true },
            awaitPause = {},
            awaitSignal = { CompletableDeferred<String>().await() },
        )
        assertEquals(ClassroomSequenceWait.Timeout, result)
    }

    @Test
    fun `paused time does not consume the wait budget`() = runTest {
        var paused = true
        val signal = CompletableDeferred<String>()
        var result: ClassroomSequenceWait<String>? = null
        val job = launch {
            result = awaitClassroomSequenceSignal(
                timeoutMs = 2_000L,
                isCurrent = { true },
                awaitPause = { while (paused) delay(20L) },
                awaitSignal = { signal.await() },
            )
        }
        advanceTimeBy(10_000L)
        runCurrent()
        assertNull(result)

        paused = false
        runCurrent()
        signal.complete("after pause")
        advanceUntilIdle()
        job.join()
        assertEquals(ClassroomSequenceWait.Value("after pause"), result)
    }

    @Test
    fun `leaving the scene cancels instead of timing out`() = runTest {
        var current = true
        var result: ClassroomSequenceWait<String>? = null
        val job = launch {
            result = awaitClassroomSequenceSignal(
                timeoutMs = 5_000L,
                isCurrent = { current },
                awaitPause = {},
                awaitSignal = { CompletableDeferred<String>().await() },
            )
        }
        runCurrent()
        current = false
        advanceUntilIdle()
        job.join()
        assertEquals(ClassroomSequenceWait.Cancelled, result)
    }

    @Test
    fun `late signal cannot satisfy the next wait`() = runTest {
        val first = CompletableDeferred<String>()
        val firstResult = awaitClassroomSequenceSignal(
            timeoutMs = 2_000L,
            isCurrent = { true },
            awaitPause = {},
            awaitSignal = { first.await() },
        )
        assertEquals(ClassroomSequenceWait.Timeout, firstResult)
        first.complete("late")

        val second = CompletableDeferred<String>()
        var secondResult: ClassroomSequenceWait<String>? = null
        val job = launch {
            secondResult = awaitClassroomSequenceSignal(
                timeoutMs = 2_000L,
                isCurrent = { true },
                awaitPause = {},
                awaitSignal = { second.await() },
            )
        }
        runCurrent()
        second.complete("next")
        advanceUntilIdle()
        job.join()
        assertEquals(ClassroomSequenceWait.Value("next"), secondResult)
    }
}

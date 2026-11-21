package com.example.campusai.data.classroom.nativeplayer

import com.example.campusai.data.remote.ClassroomApiException
import com.example.campusai.data.remote.MagicClassQuizAttemptRequest
import com.example.campusai.data.remote.MagicClassQuizAttemptResponseDto
import com.example.campusai.data.remote.MagicClassQuizAttemptStateDto
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException

/**
 * 用可控延迟的假服务端验证草稿写入顺序、编辑代次、409 回读和重做轮次。
 * 这些用例直接驱动生产协调器，延迟发生在服务端受理之后、响应返回之前。
 */
@OptIn(ExperimentalCoroutinesApi::class)
class ClassroomQuizCoordinatorTest {

    private fun quiz() = NativeQuiz(
        listOf(
            NativeQuestion(
                id = "q1", number = 1, type = "single", question = "1 + 1 = ?",
                options = listOf(NativeQuizOption("A", "A"), NativeQuizOption("B", "B")),
                answerKey = listOf("A"), hasAnswer = true,
            ),
            NativeQuestion(
                id = "q2", number = 2, type = "single", question = "2 + 2 = ?",
                options = listOf(NativeQuizOption("A", "A"), NativeQuizOption("B", "B")),
                answerKey = listOf("B"), hasAnswer = true,
            ),
        ),
    )

    private class FakeServer {
        var attemptId = "attempt-1"
        var answers: Map<String, Any?> = emptyMap()
        var phase = "draft"
        var attempts = 1
        val requests = mutableListOf<MagicClassQuizAttemptRequest>()
        var holdResponse: CompletableDeferred<Unit>? = null
        var failure: Throwable? = null
        var failureAfterApply: Throwable? = null

        private fun state() = MagicClassQuizAttemptStateDto(
            sessionId = "session-1", phase = phase, answers = answers,
        )

        suspend fun save(sceneId: String, request: MagicClassQuizAttemptRequest): Result<MagicClassQuizAttemptResponseDto> {
            requests += request
            failure?.let { error ->
                failure = null
                return Result.failure(error)
            }
            // 服务端先受理并落库，再把响应延迟返回：用于验证客户端迟到响应处理。
            if (request.startNewAttempt) {
                attempts++
                attemptId = "attempt-$attempts"
            }
            answers = request.answers
            phase = request.phase
            val response = MagicClassQuizAttemptResponseDto(
                attemptId,
                MagicClassQuizAttemptStateDto("session-1", phase, answers, request.results),
            )
            holdResponse?.await()
            failureAfterApply?.let { error ->
                failureAfterApply = null
                return Result.failure(error)
            }
            return Result.success(response)
        }

        suspend fun load(sceneId: String): Result<MagicClassQuizAttemptResponseDto> =
            Result.success(MagicClassQuizAttemptResponseDto(attemptId, state()))
    }

    private fun TestScope.coordinator(
        sceneId: String,
        server: FakeServer,
        mutex: Mutex = Mutex(),
        isCurrent: () -> Boolean = { true },
        onSettled: (Int, Int) -> Unit = { _, _ -> },
        onState: (NativeQuizUiState) -> Unit = {},
    ) = ClassroomQuizCoordinator(
        sceneId = sceneId,
        quiz = quiz(),
        writeMutex = mutex,
        isAccountCurrent = isCurrent,
        loadAttempt = server::load,
        saveAttempt = server::save,
        scope = this,
        onState = onState,
        onSettled = onSettled,
    )

    @Test
    fun `stale echo does not overwrite newer local answers`() = runTest {
        val server = FakeServer()
        var state: NativeQuizUiState? = null
        val gate = CompletableDeferred<Unit>()
        server.holdResponse = gate
        val writer = coordinator("scene-a", server) { state = it }
        writer.load()
        advanceUntilIdle()

        writer.setAnswer("q1", NativeAnswer(selected = setOf("A")))
        advanceTimeBy(701)
        advanceUntilIdle()
        assertEquals(1, server.requests.size)
        assertEquals("A", server.answers["q1"])

        // 第一个草稿的响应还没回来时，用户改成了 B。
        writer.setAnswer("q1", NativeAnswer(selected = setOf("B")))
        advanceTimeBy(701)
        advanceUntilIdle()
        assertEquals("第一份草稿仍在途，第二份应排队", 1, server.requests.size)

        gate.complete(Unit)
        advanceUntilIdle()
        assertEquals("旧响应不能覆盖新答案", setOf("B"), state?.answers?.get("q1")?.selected)
        assertEquals("服务端最终草稿应为最新答案", "B", server.answers["q1"])
        assertEquals(2, server.requests.size)
        assertEquals("B", server.requests[1].answers["q1"])
    }

    @Test
    fun `edit on A then B then back to A keeps newest draft on server`() = runTest {
        val server = FakeServer()
        val sharedMutex = Mutex()
        val gate = CompletableDeferred<Unit>()
        server.holdResponse = gate
        var stateA2: NativeQuizUiState? = null

        val firstA = coordinator("scene-a", server, sharedMutex) { }
        firstA.load()
        advanceUntilIdle()
        firstA.setAnswer("q1", NativeAnswer(selected = setOf("A")))
        advanceTimeBy(300)

        // 离开 A：取走草稿并关闭旧协调器；落盘任务先排进共享写锁。
        val flush = firstA.takeDraftFlush()
        firstA.close()
        assertNotNull(flush)
        launch(start = CoroutineStart.UNDISPATCHED) { flush?.invoke() }

        // 回到 A：新协调器读到的是服务端旧状态，但用户随后又改成 B。
        val secondA = coordinator("scene-a", server, sharedMutex) { stateA2 = it }
        secondA.load()
        advanceUntilIdle()
        secondA.setAnswer("q1", NativeAnswer(selected = setOf("B")))
        advanceTimeBy(701)
        advanceUntilIdle()
        assertEquals("新场景的保存必须排在旧页草稿之后", 1, server.requests.size)

        gate.complete(Unit)
        advanceUntilIdle()
        assertEquals("服务端最终草稿应为回 A 后的新答案", "B", server.answers["q1"])
        assertEquals(setOf("B"), stateA2?.answers?.get("q1")?.selected)
        assertEquals(2, server.requests.size)
        assertFalse("旧页的迟到响应不能再发布状态", stateA2?.answers?.get("q1")?.selected == setOf("A"))
    }

    @Test
    fun `submit waits for in-flight draft and lands after it`() = runTest {
        val server = FakeServer()
        val gate = CompletableDeferred<Unit>()
        server.holdResponse = gate
        var state: NativeQuizUiState? = null
        var settled: Pair<Int, Int>? = null
        val writer = coordinator("scene-a", server, onState = { state = it }, onSettled = { c, t -> settled = c to t })
        writer.load()
        advanceUntilIdle()

        writer.setAnswer("q1", NativeAnswer(selected = setOf("A")))
        writer.setAnswer("q2", NativeAnswer(selected = setOf("B")))
        advanceTimeBy(701)
        advanceUntilIdle()
        assertEquals(1, server.requests.size)

        writer.submit()
        advanceUntilIdle()
        assertEquals("提交应等待在途草稿", 1, server.requests.size)

        gate.complete(Unit)
        advanceUntilIdle()
        assertEquals(2, server.requests.size)
        assertEquals("draft", server.requests[0].phase)
        assertEquals("reviewed", server.requests[1].phase)
        assertEquals("reviewed", server.phase)
        assertEquals("reviewed", state?.phase)
        assertEquals(2 to 2, settled)
    }

    @Test
    fun `lost draft response keeps local answers and next save persists latest`() = runTest {
        val server = FakeServer()
        server.failureAfterApply = IOException("connection reset")
        var state: NativeQuizUiState? = null
        val writer = coordinator("scene-a", server) { state = it }
        writer.load()
        advanceUntilIdle()

        writer.setAnswer("q1", NativeAnswer(selected = setOf("A")))
        advanceTimeBy(701)
        advanceUntilIdle()
        assertEquals("服务端已写入但客户端丢失响应", "A", server.answers["q1"])
        assertEquals("本地答案必须保留", setOf("A"), state?.answers?.get("q1")?.selected)
        assertNotNull(state?.error)

        writer.setAnswer("q1", NativeAnswer(selected = setOf("B")))
        advanceTimeBy(701)
        advanceUntilIdle()
        assertEquals("重试后服务端应为最新答案", "B", server.answers["q1"])
        assertEquals(setOf("B"), state?.answers?.get("q1")?.selected)
    }

    @Test
    fun `conflict reloads server attempt instead of treating 409 as success`() = runTest {
        val server = FakeServer()
        var state: NativeQuizUiState? = null
        var loaded = 0
        val writer = ClassroomQuizCoordinator(
            sceneId = "scene-a",
            quiz = quiz(),
            writeMutex = Mutex(),
            isAccountCurrent = { true },
            loadAttempt = { loaded++; server.load(it) },
            saveAttempt = server::save,
            scope = this,
            onState = { state = it },
            onSettled = { _, _ -> },
        )
        writer.load()
        advanceUntilIdle()
        val baseline = loaded
        assertEquals("draft", state?.phase)

        writer.setAnswer("q1", NativeAnswer(selected = setOf("B")))
        // 服务端在保存前已经进入另一份作答；本次写入返回 409。
        server.phase = "reviewed"
        server.answers = mapOf("q1" to "A", "q2" to "B")
        server.failure = ClassroomApiException(409, "QUIZ_ATTEMPT_CONFLICT", "冲突")
        advanceTimeBy(701)
        advanceUntilIdle()
        assertEquals("409 后应回读服务端当前作答", baseline + 1, loaded)
        assertEquals("reviewed", state?.phase)
        assertEquals(setOf("A"), state?.answers?.get("q1")?.selected)
    }

    @Test
    fun `retry allocates a new attempt even before the response arrives`() = runTest {
        val server = FakeServer()
        server.phase = "reviewed"
        server.answers = mapOf("q1" to "A", "q2" to "B")
        val gate = CompletableDeferred<Unit>()
        var state: NativeQuizUiState? = null
        val writer = coordinator("scene-a", server, onState = { state = it })
        writer.load()
        advanceUntilIdle()
        assertEquals("attempt-1", state?.attemptId)

        server.holdResponse = gate
        writer.retry()
        advanceUntilIdle()
        assertEquals("重做先申请新根 attempt", 1, server.requests.size)
        assertTrue(server.requests.first().startNewAttempt)
        assertFalse("新一轮不能再显示上一轮结果", state?.showReport == true)

        // 新 attemptID 尚未返回时用户已开始作答。
        writer.setAnswer("q1", NativeAnswer(selected = setOf("A")))
        advanceTimeBy(701)
        advanceUntilIdle()
        assertEquals("作答保存应排在新 attempt 申请之后", 1, server.requests.size)

        gate.complete(Unit)
        advanceUntilIdle()
        assertEquals(2, server.requests.size)
        assertEquals("第二轮草稿必须写到新 attempt", "attempt-2", server.requests[1].attemptId)
        assertEquals("attempt-2", state?.attemptId)
        assertEquals("A", server.answers["q1"])
        assertNull(state?.error)
    }

    @Test
    fun `account switch drops late responses`() = runTest {
        val server = FakeServer()
        var accountCurrent = true
        var state: NativeQuizUiState? = null
        val gate = CompletableDeferred<Unit>()
        server.holdResponse = gate
        val writer = coordinator("scene-a", server, isCurrent = { accountCurrent }) { state = it }
        writer.load()
        advanceUntilIdle()

        writer.setAnswer("q1", NativeAnswer(selected = setOf("A")))
        advanceTimeBy(701)
        advanceUntilIdle()
        accountCurrent = false
        val before = state
        gate.complete(Unit)
        advanceUntilIdle()

        assertEquals("换号后迟到响应不能发布", before, state)
        assertEquals("A", server.answers["q1"])
    }
}

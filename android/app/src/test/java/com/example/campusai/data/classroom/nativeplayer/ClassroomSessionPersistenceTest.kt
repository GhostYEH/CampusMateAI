package com.example.campusai.data.classroom.nativeplayer

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import com.example.campusai.data.local.InMemoryKeyValueStorage
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class ClassroomSessionPersistenceTest {

    @Before
    fun resetGate() {
        ClassroomLocalWriteGate.reset()
    }

    @Test
    fun `position failure still attempts rewards and draft`() = runTest {
        val calls = mutableListOf<String>()
        val positionKey = "classroom:position"
        val rewardsKey = "classroom:rewards"
        val draftKey = "classroom:draft"
        val writes = listOf(
            ClassroomStateWrite(positionKey, "position", ClassroomLocalWriteGate.grant(positionKey)) {
                calls += "position"
                throw IOException("disk full")
            },
            ClassroomStateWrite(rewardsKey, "rewards", ClassroomLocalWriteGate.grant(rewardsKey)) {
                calls += "rewards"
            },
            ClassroomStateWrite(draftKey, "draft", ClassroomLocalWriteGate.grant(draftKey)) {
                calls += "draft"
            },
        )
        val flusher = ClassroomSessionFlusher(
            budgetMs = 2_000L,
            itemBudgetMs = 1_000L,
            maxAttempts = 1,
            retryDelayMs = 0L,
        )

        val results = flusher.run(writes).associateBy { it.label }

        assertEquals(ClassroomWriteStatus.IO_ERROR, results.getValue("position").status)
        assertEquals(ClassroomWriteStatus.SAVED, results.getValue("rewards").status)
        assertEquals(ClassroomWriteStatus.SAVED, results.getValue("draft").status)
        assertEquals(listOf("position", "rewards", "draft"), calls)
    }

    @Test
    fun `recoverable io failure is retried within the budget`() = runTest {
        var attempts = 0
        val key = "classroom:rewards"
        val write = ClassroomStateWrite(key, "rewards", ClassroomLocalWriteGate.grant(key)) {
            attempts += 1
            if (attempts < 3) throw IOException("transient")
        }
        val flusher = ClassroomSessionFlusher(
            budgetMs = 2_000L,
            itemBudgetMs = 1_000L,
            maxAttempts = 3,
            retryDelayMs = 20L,
        )

        val result = flusher.run(listOf(write)).single()

        assertEquals(ClassroomWriteStatus.SAVED, result.status)
        assertEquals(3, result.attempts)
    }

    @Test
    fun `non io failure is not retried`() = runTest {
        var attempts = 0
        val key = "classroom:position"
        val write = ClassroomStateWrite(key, "position", ClassroomLocalWriteGate.grant(key)) {
            attempts += 1
            throw IllegalStateException("unexpected payload")
        }
        val flusher = ClassroomSessionFlusher(
            budgetMs = 2_000L,
            itemBudgetMs = 1_000L,
            maxAttempts = 3,
            retryDelayMs = 20L,
        )

        val result = flusher.run(listOf(write)).single()

        assertEquals(ClassroomWriteStatus.FAILED, result.status)
        assertEquals(1, result.attempts)
        assertEquals(1, attempts)
    }

    @Test
    fun `slow item times out without blocking other writes`() = runTest {
        val slowKey = "classroom:position"
        val fastKey = "classroom:rewards"
        val fastSaved = mutableListOf<String>()
        val writes = listOf(
            ClassroomStateWrite(slowKey, "position", ClassroomLocalWriteGate.grant(slowKey)) {
                delay(5_000L)
            },
            ClassroomStateWrite(fastKey, "rewards", ClassroomLocalWriteGate.grant(fastKey)) {
                fastSaved += "fast"
            },
        )
        val flusher = ClassroomSessionFlusher(
            budgetMs = 400L,
            itemBudgetMs = 200L,
            maxAttempts = 1,
            retryDelayMs = 0L,
        )

        val results = flusher.run(writes).associateBy { it.label }

        assertEquals(ClassroomWriteStatus.TIMED_OUT, results.getValue("position").status)
        assertEquals(ClassroomWriteStatus.SAVED, results.getValue("rewards").status)
        assertEquals(listOf("fast"), fastSaved)
    }

    @Test
    fun `overall budget marks remaining writes as timed out`() = runTest {
        val keys = listOf("classroom:position", "classroom:rewards")
        val writes = keys.map { key ->
            ClassroomStateWrite(key, key.substringAfter(':'), ClassroomLocalWriteGate.grant(key)) {
                delay(10_000L)
            }
        }
        val flusher = ClassroomSessionFlusher(
            budgetMs = 300L,
            itemBudgetMs = 10_000L,
            maxAttempts = 1,
            retryDelayMs = 0L,
        )

        val results = flusher.run(writes)

        assertTrue(results.all { it.status == ClassroomWriteStatus.TIMED_OUT })
    }

    @Test
    fun `cancelling the flush keeps cancellation semantics`() = runTest {
        val key = "classroom:position"
        var saved = false
        val write = ClassroomStateWrite(key, "position", ClassroomLocalWriteGate.grant(key)) {
            delay(1_000L)
            saved = true
        }
        val flusher = ClassroomSessionFlusher(
            budgetMs = 5_000L,
            itemBudgetMs = 5_000L,
            maxAttempts = 1,
            retryDelayMs = 0L,
        )

        val job = launch { flusher.run(listOf(write)) }
        advanceTimeBy(100L)
        runCurrent()
        job.cancel()
        job.join()

        assertTrue(job.isCancelled)
        assertFalse(saved)
    }

    @Test
    fun `stale write cannot overwrite a newer commit that landed mid-flight`() = runTest {
        val key = "classroom:rewards"
        val storage = InMemoryKeyValueStorage()
        val oldGrant = ClassroomLocalWriteGate.grant(key)
        val oldStarted = CompletableDeferred<Unit>()
        val releaseOld = CompletableDeferred<Unit>()
        val flusher = ClassroomSessionFlusher(
            budgetMs = 10_000L,
            itemBudgetMs = 10_000L,
            maxAttempts = 1,
            retryDelayMs = 0L,
        )

        // 旧写入先通过调度检查并停在真正提交之前。
        val oldWrite = ClassroomStateWrite(key, "rewards", oldGrant) {
            oldStarted.complete(Unit)
            releaseOld.await()
            storage.saveRawIf(key, "old", shouldWrite = {
                ClassroomLocalWriteGate.isCurrent(key, oldGrant)
            })
        }
        val oldJob = launch { flusher.run(listOf(oldWrite)) }
        oldStarted.await()

        // 新快照完成落盘后，旧写入才恢复。
        val newGrant = ClassroomLocalWriteGate.grant(key)
        storage.saveRawIf(key, "new", shouldWrite = {
            ClassroomLocalWriteGate.isCurrent(key, newGrant)
        })
        releaseOld.complete(Unit)
        oldJob.join()

        assertEquals("new", storage.readRaw(key))
    }

    @Test
    fun `new session waits for an exit flush before reading the same classroom`() = runTest {
        val key = "classroom:rewards"
        ClassroomLocalWriteGate.beginPending(key)
        var read = false
        val reader = launch {
            ClassroomLocalWriteGate.awaitIdle(key)
            read = true
        }
        runCurrent()
        assertFalse("退出落盘完成前不能读取旧账本", read)

        ClassroomLocalWriteGate.finishPending(key)
        reader.join()
        assertTrue(read)
    }

    @Test
    fun `await idle keeps waiting when a new write follows the first one`() = runTest {
        val key = "classroom:rewards"
        ClassroomLocalWriteGate.beginPending(key)
        var read = false
        val reader = launch {
            ClassroomLocalWriteGate.awaitIdle(key)
            read = true
        }
        runCurrent()
        assertFalse(read)

        ClassroomLocalWriteGate.finishPending(key)
        ClassroomLocalWriteGate.beginPending(key)
        runCurrent()
        assertFalse("第一笔完成后紧接着有新写入，仍不能读取", read)

        ClassroomLocalWriteGate.finishPending(key)
        reader.join()
        assertTrue(read)
    }

    @Test
    fun `late write from an old session yields to a newer grant`() = runTest {
        val key = "classroom:rewards"
        val oldGrant = ClassroomLocalWriteGate.grant(key)
        val newGrant = ClassroomLocalWriteGate.grant(key)
        val saved = mutableListOf<String>()
        val flusher = ClassroomSessionFlusher(
            budgetMs = 1_000L,
            itemBudgetMs = 500L,
            maxAttempts = 1,
            retryDelayMs = 0L,
        )

        val newest = flusher.run(
            listOf(ClassroomStateWrite(key, "rewards", newGrant) { saved += "new" }),
        ).single()
        val stale = flusher.run(
            listOf(ClassroomStateWrite(key, "rewards", oldGrant) { saved += "old" }),
        ).single()

        assertEquals(ClassroomWriteStatus.SAVED, newest.status)
        assertEquals(ClassroomWriteStatus.STALE, stale.status)
        assertEquals(listOf("new"), saved)
    }

    @Test
    fun `local reads distinguish missing value and failure`() = runTest {
        assertTrue(readClassroomLocal<String> { null } is ClassroomLocalRead.Missing)
        assertEquals(
            ClassroomLocalRead.Value("scene-1"),
            readClassroomLocal { "scene-1" },
        )
        assertTrue(
            readClassroomLocal<String> { throw IOException("storage unavailable") } is ClassroomLocalRead.Failed,
        )
    }

    @Test
    fun `local read keeps coroutine cancellation`() = runTest {
        var cancelled = false
        try {
            readClassroomLocal<Any> { throw CancellationException("cancelled") }
        } catch (_: CancellationException) {
            cancelled = true
        }
        assertTrue(cancelled)
    }
}

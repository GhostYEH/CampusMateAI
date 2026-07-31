package com.example.campusai

import com.example.campusai.data.local.InMemoryKeyValueStorage
import com.example.campusai.data.model.FocusMode
import com.example.campusai.data.model.FocusRecord
import com.example.campusai.data.model.FocusSnapshot
import com.example.campusai.data.model.FocusTimerState
import com.example.campusai.data.repository.LocalFocusRepository
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

class LocalFocusRepositoryTest {

    private fun newRepo(storage: InMemoryKeyValueStorage = InMemoryKeyValueStorage()) =
        LocalFocusRepository(storage = storage)

    @Test
    fun `完成专注后更新记录与统计`() = runBlocking {
        val repo = newRepo()
        repo.setGoal(60) // 等待初始化完成

        repo.addRecord(FocusMode.FOCUS, 25, finished = true)
        repo.addRecord(FocusMode.FOCUS, 25, finished = true)
        repo.addRecord(FocusMode.SHORT_BREAK, 5, finished = true)

        val stats = repo.stats.value
        assertEquals(50, stats.todayMinutes) // 休息不计入专注时长
        assertEquals(2, stats.todayCount)
        assertEquals(1, stats.streakDays)
        assertEquals(3, repo.records.value.size)
    }

    @Test
    fun `连续天数跨天统计`() = runBlocking {
        val storage = InMemoryKeyValueStorage()
        val today = LocalDate.now()
        val records = listOf(
            FocusRecord(3, today.toString(), FocusMode.FOCUS.name, 25, 25, true, "22:00"),
            FocusRecord(2, today.minusDays(1).toString(), FocusMode.FOCUS.name, 25, 25, true, "21:00"),
            FocusRecord(1, today.minusDays(2).toString(), FocusMode.FOCUS.name, 25, 25, true, "20:00"),
        )
        val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
        storage.saveRaw("focus_snapshot", moshi.adapter(FocusSnapshot::class.java).toJson(FocusSnapshot(records)))

        val repo = newRepo(storage)
        repo.setGoal(60) // 触发加载完成
        assertEquals(3, repo.stats.value.streakDays)
    }

    @Test
    fun `计时状态持久化与恢复`() = runBlocking {
        val storage = InMemoryKeyValueStorage()
        val repo = newRepo(storage)
        val state = FocusTimerState(
            mode = FocusMode.FOCUS.name,
            remainingSeconds = 800,
            running = false,
            savedAtEpochMillis = System.currentTimeMillis(),
        )
        repo.saveTimer(state)

        val restored = newRepo(storage)
        restored.setGoal(60)
        assertEquals(800, restored.timer.value?.remainingSeconds)
        assertEquals(false, restored.timer.value?.running)
    }

    @Test
    fun `运行中的计时按墙钟流逝`() {
        val savedAt = System.currentTimeMillis() - 60_000
        val state = FocusTimerState(FocusMode.FOCUS.name, 300, running = true, savedAtEpochMillis = savedAt)
        val remaining = state.currentRemaining(System.currentTimeMillis())
        assertTrue(remaining in 230..240)
    }

    @Test
    fun `自习目标限制在合理范围`() = runBlocking {
        val repo = newRepo()
        repo.setGoal(5)
        assertEquals(15, repo.stats.value.goalMinutes)
        repo.setGoal(9999)
        assertEquals(480, repo.stats.value.goalMinutes)
    }

    @Test
    fun `清除计时状态`() = runBlocking {
        val repo = newRepo()
        repo.saveTimer(FocusTimerState(FocusMode.FOCUS.name, 100, false, System.currentTimeMillis()))
        assertNotNull(repo.timer.value)
        repo.saveTimer(null)
        assertNull(repo.timer.value)
    }
}

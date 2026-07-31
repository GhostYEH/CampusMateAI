package com.example.campusai.data.repository

import com.example.campusai.data.local.KeyValueStorage
import com.example.campusai.data.model.FocusMode
import com.example.campusai.data.model.FocusRecord
import com.example.campusai.data.model.FocusSnapshot
import com.example.campusai.data.model.FocusStats
import com.example.campusai.data.model.FocusTimerState
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/**
 * 专注自习数据入口：番茄钟状态、专注记录与自习目标全部本地持久化，
 * 页面退出或应用重启后可恢复。
 */
interface FocusRepository {
    val records: StateFlow<List<FocusRecord>>
    val timer: StateFlow<FocusTimerState?>
    val stats: StateFlow<FocusStats>
    val loading: StateFlow<Boolean>

    suspend fun saveTimer(state: FocusTimerState?)
    suspend fun setGoal(minutes: Int)
    suspend fun addRecord(mode: FocusMode, actualMinutes: Int, finished: Boolean)
}

class LocalFocusRepository(
    private val storage: KeyValueStorage,
    private val now: () -> Long = System::currentTimeMillis,
    scope: CoroutineScope? = null,
) : FocusRepository {

    private val repoScope = scope ?: CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val mutex = Mutex()
    private val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
    private val adapter = moshi.adapter(FocusSnapshot::class.java)

    private val _records = MutableStateFlow<List<FocusRecord>>(emptyList())
    override val records: StateFlow<List<FocusRecord>> = _records.asStateFlow()

    private val _timer = MutableStateFlow<FocusTimerState?>(null)
    override val timer: StateFlow<FocusTimerState?> = _timer.asStateFlow()

    private val _stats = MutableStateFlow(FocusStats(0, 0, 0, 60))
    override val stats: StateFlow<FocusStats> = _stats.asStateFlow()

    private val _loading = MutableStateFlow(true)
    override val loading: StateFlow<Boolean> = _loading.asStateFlow()

    private var goalMinutes = 60

    private val initJob = repoScope.launch {
        try {
            val snapshot = storage.readRaw(STORAGE_KEY)?.let { adapter.fromJson(it) }
            if (snapshot != null) {
                _records.value = snapshot.records
                _timer.value = snapshot.timer
                goalMinutes = snapshot.goalMinutes
            }
        } catch (_: Exception) {
            // 损坏数据自动降级为初始状态
        } finally {
            recomputeStats()
            _loading.value = false
        }
    }

    override suspend fun saveTimer(state: FocusTimerState?) {
        initJob.join()
        mutex.withLock {
            _timer.value = state
            persist()
        }
    }

    override suspend fun setGoal(minutes: Int) {
        initJob.join()
        mutex.withLock {
            goalMinutes = minutes.coerceIn(15, 480)
            recomputeStats()
            persist()
        }
    }

    override suspend fun addRecord(mode: FocusMode, actualMinutes: Int, finished: Boolean) {
        initJob.join()
        mutex.withLock {
            val endedAt = now()
            val record = FocusRecord(
                id = endedAt,
                date = LocalDate.now().toString(),
                mode = mode.name,
                plannedMinutes = mode.minutes,
                actualMinutes = actualMinutes.coerceAtLeast(0),
                finished = finished,
                endedAt = Instant.ofEpochMilli(endedAt).atZone(ZoneId.systemDefault())
                    .format(DateTimeFormatter.ofPattern("HH:mm")),
            )
            _records.value = listOf(record) + _records.value.take(99)
            recomputeStats()
            persist()
        }
    }

    private fun recomputeStats() {
        val today = LocalDate.now().toString()
        val focusRecords = _records.value.filter { it.mode == FocusMode.FOCUS.name }
        val todayRecords = focusRecords.filter { it.date == today }
        val dates = focusRecords.map { it.date }.toSet()
        var streak = 0
        var cursor = LocalDate.now()
        // 今天还没记录时，从昨天开始也算连续
        if (today !in dates) cursor = cursor.minusDays(1)
        while (cursor.toString() in dates) {
            streak++
            cursor = cursor.minusDays(1)
        }
        _stats.value = FocusStats(
            todayMinutes = todayRecords.sumOf { it.actualMinutes },
            todayCount = todayRecords.count { it.finished },
            streakDays = streak,
            goalMinutes = goalMinutes,
        )
    }

    private suspend fun persist() {
        storage.saveRaw(
            STORAGE_KEY,
            adapter.toJson(FocusSnapshot(_records.value, _timer.value, goalMinutes)),
        )
    }

    companion object {
        private const val STORAGE_KEY = "focus_snapshot"
    }
}

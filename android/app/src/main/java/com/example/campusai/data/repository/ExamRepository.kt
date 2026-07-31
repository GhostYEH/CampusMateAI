package com.example.campusai.data.repository

import com.example.campusai.data.local.KeyValueStorage
import com.example.campusai.data.model.Exam
import com.squareup.moshi.Moshi
import com.squareup.moshi.Types
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
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/**
 * 考试安排数据入口。当前后端没有考试接口，本地实现负责持久化；
 * 后续接入教务系统时只需替换为 Remote 实现。
 */
interface ExamRepository {
    val exams: StateFlow<List<Exam>>
    val loading: StateFlow<Boolean>
    val error: StateFlow<String?>

    suspend fun refresh()
    suspend fun upsert(exam: Exam): Long
    suspend fun delete(id: Long)
    suspend fun setReminder(id: Long, enabled: Boolean)
    fun getById(id: Long): Exam?
}

class LocalExamRepository(
    private val storage: KeyValueStorage,
    private val courseNames: () -> List<String>,
    private val now: () -> Long = System::currentTimeMillis,
    scope: CoroutineScope? = null,
) : ExamRepository {

    private val repoScope = scope ?: CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val mutex = Mutex()
    private val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
    private val listAdapter = moshi.adapter<List<Exam>>(
        Types.newParameterizedType(List::class.java, Exam::class.java),
    )

    private val _exams = MutableStateFlow<List<Exam>>(emptyList())
    override val exams: StateFlow<List<Exam>> = _exams.asStateFlow()

    private val _loading = MutableStateFlow(true)
    override val loading: StateFlow<Boolean> = _loading.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    override val error: StateFlow<String?> = _error.asStateFlow()

    private val initJob = repoScope.launch { load() }

    private suspend fun load() {
        _loading.value = true
        _error.value = null
        try {
            val raw = storage.readRaw(STORAGE_KEY)
            val parsed = raw?.let { listAdapter.fromJson(it) }
            val data = parsed ?: seedExams().also { storage.saveRaw(STORAGE_KEY, listAdapter.toJson(it)) }
            _exams.value = data.sortedBy { it.startDateTime() }
        } catch (_: Exception) {
            _error.value = "考试数据读取失败，请重试"
        } finally {
            _loading.value = false
        }
    }

    override suspend fun refresh() {
        initJob.join()
        load()
    }

    override suspend fun upsert(exam: Exam): Long {
        initJob.join()
        return mutex.withLock {
            val list = _exams.value.toMutableList()
            // A fixed clock is used by tests and can also occur when a user
            // creates multiple records quickly; never reuse a seeded id.
            val id = if (exam.id > 0) exam.id else {
                val candidate = now()
                if (list.any { it.id == candidate }) (list.maxOfOrNull { it.id } ?: candidate) + 1 else candidate
            }
            val idx = list.indexOfFirst { it.id == id }
            val saved = exam.copy(id = id)
            if (idx >= 0) list[idx] = saved else list.add(saved)
            _exams.value = list.sortedBy { it.startDateTime() }
            persist()
            id
        }
    }

    override suspend fun delete(id: Long) {
        initJob.join()
        mutex.withLock {
            _exams.value = _exams.value.filterNot { it.id == id }
            persist()
        }
    }

    override suspend fun setReminder(id: Long, enabled: Boolean) {
        initJob.join()
        mutex.withLock {
            _exams.value = _exams.value.map { if (it.id == id) it.copy(reminderEnabled = enabled) else it }
            persist()
        }
    }

    override fun getById(id: Long): Exam? = _exams.value.find { it.id == id }

    private suspend fun persist() {
        storage.saveRaw(STORAGE_KEY, listAdapter.toJson(_exams.value))
    }

    /** 首次启动时基于现有课程生成贴近考试周的演示数据。 */
    private fun seedExams(): List<Exam> {
        val courses = courseNames().ifEmpty {
            listOf("数据结构", "高等数学（下）", "计算机网络", "操作系统原理")
        }
        val zone = ZoneId.systemDefault()
        val base = Instant.ofEpochMilli(now()).atZone(zone).toLocalDate()
        val fmt = DateTimeFormatter.ISO_LOCAL_DATE
        val types = listOf("期末考试", "期末考试", "期中考试", "随堂测验")
        val rooms = listOf("博学楼 1-401", "教学楼 2-305", "明德楼 3-208", "实验楼 B-310")
        val slots = listOf("09:00" to "11:00", "14:00" to "16:00", "10:00" to "11:30", "19:00" to "20:30")
        val offsets = listOf(3L, 7L, 12L, -2L)
        return courses.take(4).mapIndexed { index, name ->
            val (start, end) = slots[index % slots.size]
            Exam(
                id = now() + index,
                courseName = name,
                date = base.plusDays(offsets[index % offsets.size]).format(fmt),
                startTime = start,
                endTime = end,
                location = rooms[index % rooms.size],
                seatNumber = "%02d".format(6 + index * 7),
                type = types[index % types.size],
                reminderEnabled = true,
            )
        }
    }

    companion object {
        private const val STORAGE_KEY = "exams"
    }
}

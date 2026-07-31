package com.example.campusai.data.repository

import com.example.campusai.data.local.KeyValueStorage
import com.example.campusai.data.model.LeaveForm
import com.example.campusai.data.model.RepairForm
import com.example.campusai.data.model.RequestStatus
import com.example.campusai.data.model.ServiceKind
import com.example.campusai.data.model.ServiceRequest
import com.example.campusai.data.model.TimelineEvent
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
 * 办事大厅申请数据入口。当前为本地实现（提交后即时进入"审核中"），
 * 后续接入学工 / 后勤系统时替换为 Remote 实现。
 */
interface ServiceRepository {
    val requests: StateFlow<List<ServiceRequest>>
    val loading: StateFlow<Boolean>
    val error: StateFlow<String?>

    suspend fun refresh()
    suspend fun submitLeave(form: LeaveForm): Result<Long>
    suspend fun submitRepair(form: RepairForm): Result<Long>
    suspend fun submitGeneric(kind: ServiceKind, title: String, fields: Map<String, String>): Result<Long>
    fun getById(id: Long): ServiceRequest?
}

class LocalServiceRepository(
    private val storage: KeyValueStorage,
    private val now: () -> Long = System::currentTimeMillis,
    scope: CoroutineScope? = null,
) : ServiceRepository {

    private val repoScope = scope ?: CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val mutex = Mutex()
    private val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
    private val listAdapter = moshi.adapter<List<ServiceRequest>>(
        Types.newParameterizedType(List::class.java, ServiceRequest::class.java),
    )

    private val _requests = MutableStateFlow<List<ServiceRequest>>(emptyList())
    override val requests: StateFlow<List<ServiceRequest>> = _requests.asStateFlow()

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
            _requests.value = parsed ?: seedRequests().also {
                storage.saveRaw(STORAGE_KEY, listAdapter.toJson(it))
            }
        } catch (_: Exception) {
            _error.value = "申请数据读取失败，请重试"
        } finally {
            _loading.value = false
        }
    }

    override suspend fun refresh() {
        initJob.join()
        load()
    }

    override suspend fun submitLeave(form: LeaveForm): Result<Long> {
        form.validate()?.let { return Result.failure(IllegalArgumentException(it)) }
        val fields = linkedMapOf(
            "请假类型" to form.type,
            "开始时间" to form.startAt.replace('T', ' '),
            "结束时间" to form.endAt.replace('T', ' '),
            "请假原因" to form.reason.trim(),
            "联系方式" to form.phone.trim(),
        )
        return submit(
            kind = ServiceKind.LEAVE,
            title = "${form.type}申请",
            fields = fields,
            attachments = listOfNotNull(form.attachmentUri),
        )
    }

    override suspend fun submitRepair(form: RepairForm): Result<Long> {
        form.validate()?.let { return Result.failure(IllegalArgumentException(it)) }
        val fields = linkedMapOf(
            "宿舍楼" to form.building,
            "房间号" to form.room.trim(),
            "报修类型" to form.type,
            "问题描述" to form.description.trim(),
            "紧急程度" to form.urgency,
            "联系电话" to form.phone.trim(),
        )
        return submit(
            kind = ServiceKind.REPAIR,
            title = "${form.building} ${form.room.trim()} 报修",
            fields = fields,
            attachments = listOfNotNull(form.imageUri),
        )
    }

    override suspend fun submitGeneric(
        kind: ServiceKind,
        title: String,
        fields: Map<String, String>,
    ): Result<Long> {
        if (title.isBlank()) return Result.failure(IllegalArgumentException("请填写申请标题"))
        return submit(kind, title.trim(), fields, emptyList())
    }

    private suspend fun submit(
        kind: ServiceKind,
        title: String,
        fields: Map<String, String>,
        attachments: List<String>,
    ): Result<Long> {
        initJob.join()
        return mutex.withLock {
            val id = now()
            val created = formatDateTime(id)
            val request = ServiceRequest(
                id = id,
                kind = kind,
                title = title,
                status = RequestStatus.PENDING,
                createdAt = created,
                fields = fields,
                attachmentUris = attachments,
                timeline = listOf(
                    TimelineEvent(created, "提交成功", "申请已提交，等待审核"),
                    TimelineEvent(created, "已受理", "已进入审核队列，预计 1-2 个工作日内处理"),
                ),
            )
            _requests.value = listOf(request) + _requests.value
            persist()
            Result.success(id)
        }
    }

    override fun getById(id: Long): ServiceRequest? = _requests.value.find { it.id == id }

    private suspend fun persist() {
        storage.saveRaw(STORAGE_KEY, listAdapter.toJson(_requests.value))
    }

    private fun formatDateTime(millis: Long): String =
        Instant.ofEpochMilli(millis).atZone(ZoneId.systemDefault())
            .format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm"))

    private fun seedRequests(): List<ServiceRequest> {
        val base = now()
        val approved = ServiceRequest(
            id = base - 3 * 86_400_000L,
            kind = ServiceKind.LEAVE,
            title = "病假申请",
            status = RequestStatus.APPROVED,
            createdAt = formatDateTime(base - 3 * 86_400_000L),
            fields = linkedMapOf(
                "请假类型" to "病假",
                "开始时间" to "2026-07-28 08:00",
                "结束时间" to "2026-07-29 18:00",
                "请假原因" to "感冒发烧到校医院就诊，医嘱建议休息两天，附上病历单。",
                "联系方式" to "13800002026",
            ),
            timeline = listOf(
                TimelineEvent(formatDateTime(base - 3 * 86_400_000L), "提交成功", "申请已提交，等待审核"),
                TimelineEvent(formatDateTime(base - 3 * 86_400_000L + 3_600_000L), "已受理", "辅导员已接收申请"),
                TimelineEvent(formatDateTime(base - 2 * 86_400_000L), "审核通过", "同意请假，请注意休息，返校后及时销假"),
            ),
        )
        val rejected = ServiceRequest(
            id = base - 5 * 86_400_000L,
            kind = ServiceKind.VENUE,
            title = "教室借用申请",
            status = RequestStatus.REJECTED,
            createdAt = formatDateTime(base - 5 * 86_400_000L),
            fields = linkedMapOf(
                "借用场地" to "博学楼 203",
                "使用时间" to "周六 14:00-17:00",
                "用途说明" to "社团招新宣讲",
            ),
            timeline = listOf(
                TimelineEvent(formatDateTime(base - 5 * 86_400_000L), "提交成功", "申请已提交，等待审核"),
                TimelineEvent(formatDateTime(base - 4 * 86_400_000L), "已驳回", "该时段教室已有考试安排，请调整时间后重新提交"),
            ),
        )
        val completed = ServiceRequest(
            id = base - 9 * 86_400_000L,
            kind = ServiceKind.REPAIR,
            title = "竹园 3 栋 412 报修",
            status = RequestStatus.COMPLETED,
            createdAt = formatDateTime(base - 9 * 86_400_000L),
            fields = linkedMapOf(
                "宿舍楼" to "竹园 3 栋",
                "房间号" to "412",
                "报修类型" to "水电维修",
                "问题描述" to "宿舍洗手池水龙头持续滴水，关闭后仍有渗漏，影响休息。",
                "紧急程度" to "一般",
                "联系电话" to "13800002026",
            ),
            timeline = listOf(
                TimelineEvent(formatDateTime(base - 9 * 86_400_000L), "提交成功", "报修单已提交"),
                TimelineEvent(formatDateTime(base - 8 * 86_400_000L), "已派单", "维修师傅王工已接单，联系电话 6278-3321"),
                TimelineEvent(formatDateTime(base - 7 * 86_400_000L), "处理完成", "水龙头已更换密封圈，如有问题请再次报修"),
            ),
        )
        return listOf(approved, rejected, completed)
    }

    companion object {
        private const val STORAGE_KEY = "service_requests"
    }
}

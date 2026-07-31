package com.example.campusai.data.repository

import com.example.campusai.data.local.KeyValueStorage
import com.example.campusai.data.model.LostFoundForm
import com.example.campusai.data.model.LostFoundItem
import com.example.campusai.data.model.LostFoundKind
import com.example.campusai.data.model.LostFoundStatus
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

/**
 * 失物招领数据入口。当前为本地实现（含演示数据）；
 * 图片仅保存本地 Uri，上传实现隔离在本仓库内，后续接入后端时替换。
 */
interface LostFoundRepository {
    val items: StateFlow<List<LostFoundItem>>
    val loading: StateFlow<Boolean>
    val error: StateFlow<String?>

    suspend fun refresh()
    suspend fun publish(form: LostFoundForm, publisher: String): Result<Long>
    suspend fun close(id: Long)
    suspend fun delete(id: Long)
    fun getById(id: Long): LostFoundItem?
}

class LocalLostFoundRepository(
    private val storage: KeyValueStorage,
    private val now: () -> Long = System::currentTimeMillis,
    scope: CoroutineScope? = null,
) : LostFoundRepository {

    private val repoScope = scope ?: CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val mutex = Mutex()
    private val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
    private val listAdapter = moshi.adapter<List<LostFoundItem>>(
        Types.newParameterizedType(List::class.java, LostFoundItem::class.java),
    )

    private val _items = MutableStateFlow<List<LostFoundItem>>(emptyList())
    override val items: StateFlow<List<LostFoundItem>> = _items.asStateFlow()

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
            _items.value = parsed ?: seedItems().also {
                storage.saveRaw(STORAGE_KEY, listAdapter.toJson(it))
            }
        } catch (_: Exception) {
            _error.value = "数据读取失败，请重试"
        } finally {
            _loading.value = false
        }
    }

    override suspend fun refresh() {
        initJob.join()
        load()
    }

    override suspend fun publish(form: LostFoundForm, publisher: String): Result<Long> {
        form.validate()?.let { return Result.failure(IllegalArgumentException(it)) }
        initJob.join()
        return mutex.withLock {
            val id = now()
            val item = LostFoundItem(
                id = id,
                kind = form.kind,
                title = form.title.trim(),
                category = form.category,
                description = form.description.trim(),
                time = form.time,
                location = form.location.trim(),
                contact = form.contact.trim(),
                anonymous = form.anonymous,
                imageUri = form.imageUri,
                status = LostFoundStatus.OPEN,
                publisher = publisher,
                mine = true,
                createdAt = id,
            )
            _items.value = listOf(item) + _items.value
            persist()
            Result.success(id)
        }
    }

    override suspend fun close(id: Long) {
        initJob.join()
        mutex.withLock {
            _items.value = _items.value.map {
                if (it.id == id) it.copy(status = LostFoundStatus.CLOSED) else it
            }
            persist()
        }
    }

    override suspend fun delete(id: Long) {
        initJob.join()
        mutex.withLock {
            _items.value = _items.value.filterNot { it.id == id }
            persist()
        }
    }

    override fun getById(id: Long): LostFoundItem? = _items.value.find { it.id == id }

    private suspend fun persist() {
        storage.saveRaw(STORAGE_KEY, listAdapter.toJson(_items.value))
    }

    private fun seedItems(): List<LostFoundItem> {
        val base = now()
        return listOf(
            LostFoundItem(
                id = base - 3_600_000L,
                kind = LostFoundKind.LOST,
                title = "黑色小米充电宝",
                category = "电子产品",
                description = "20000mAh 黑色小米充电宝，侧面贴着一张宇航员贴纸，昨晚落在图书馆三楼自习区。",
                time = "昨天 21:30 左右",
                location = "图书馆三楼",
                contact = "13800002026",
                anonymous = false,
                imageUri = null,
                status = LostFoundStatus.OPEN,
                publisher = "林知夏",
                mine = true,
                createdAt = base - 3_600_000L,
            ),
            LostFoundItem(
                id = base - 7_200_000L,
                kind = LostFoundKind.FOUND,
                title = "捡到一串钥匙",
                category = "生活用品",
                description = "在第二食堂一楼捡到钥匙一串，共 4 把，挂有蓝色校园卡套，已交到食堂服务台。",
                time = "今天 12:10",
                location = "第二食堂",
                contact = "请到服务台认领",
                anonymous = true,
                imageUri = null,
                status = LostFoundStatus.OPEN,
                publisher = "热心同学",
                mine = false,
                createdAt = base - 7_200_000L,
            ),
            LostFoundItem(
                id = base - 30_000_000L,
                kind = LostFoundKind.LOST,
                title = "《深度学习》教材",
                category = "书籍资料",
                description = "Ian Goodfellow 著《深度学习》中文版，扉页写有名字，夹了一张银杏叶书签。",
                time = "前天 16:00 左右",
                location = "教学楼 2-305",
                contact = "lin.zhixia@campus.edu.cn",
                anonymous = false,
                imageUri = null,
                status = LostFoundStatus.OPEN,
                publisher = "林知夏",
                mine = true,
                createdAt = base - 30_000_000L,
            ),
            LostFoundItem(
                id = base - 50_000_000L,
                kind = LostFoundKind.FOUND,
                title = "银色 AirPods 充电盒",
                category = "电子产品",
                description = "操场看台座位上捡到银色 AirPods 充电盒一个（无耳机），盒盖有轻微划痕。",
                time = "昨天 18:40",
                location = "东操场看台",
                contact = "13900001111",
                anonymous = false,
                imageUri = null,
                status = LostFoundStatus.CLOSED,
                publisher = "陈同学",
                mine = false,
                createdAt = base - 50_000_000L,
            ),
        )
    }

    companion object {
        private const val STORAGE_KEY = "lost_found_items"

        /** 纯函数筛选，供页面与单元测试共用。 */
        fun filter(
            items: List<LostFoundItem>,
            kind: LostFoundKind,
            keyword: String,
            category: String,
            location: String,
            newestFirst: Boolean,
        ): List<LostFoundItem> {
            val key = keyword.trim()
            return items
                .asSequence()
                .filter { it.kind == kind }
                .filter { category.isBlank() || category == "全部" || it.category == category }
                .filter { location.isBlank() || location == "全部" || it.location.contains(location) }
                .filter {
                    key.isEmpty() ||
                        it.title.contains(key) ||
                        it.description.contains(key) ||
                        it.location.contains(key)
                }
                .sortedBy { if (newestFirst) -it.createdAt else it.createdAt }
                .toList()
        }
    }
}

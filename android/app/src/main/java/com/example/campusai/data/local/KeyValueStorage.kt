package com.example.campusai.data.local

import kotlinx.coroutines.flow.Flow

/**
 * 轻量键值存储抽象：各模块本地 Repository 通过它读写 JSON 快照，
 * 避免直接依赖 DataStore，便于单元测试与后续替换为后端接口。
 */
interface KeyValueStorage {
    fun observeRaw(key: String): Flow<String?>
    suspend fun readRaw(key: String): String?
    suspend fun saveRaw(key: String, value: String)

    /**
     * 把最终代次校验和写入放在同一个存储事务里。
     * 默认实现用于内存存储；真实 DataStore 必须覆盖为原子事务。
     */
    suspend fun saveRawIf(key: String, value: String, shouldWrite: () -> Boolean) {
        if (shouldWrite()) saveRaw(key, value)
    }
}

/** 进程内实现，供单元测试使用。 */
class InMemoryKeyValueStorage : KeyValueStorage {
    private val map = mutableMapOf<String, String>()
    private val flows = mutableMapOf<String, kotlinx.coroutines.flow.MutableStateFlow<String?>>()

    override fun observeRaw(key: String): Flow<String?> =
        flows.getOrPut(key) { kotlinx.coroutines.flow.MutableStateFlow(map[key]) }

    override suspend fun readRaw(key: String): String? = map[key]

    override suspend fun saveRaw(key: String, value: String) {
        map[key] = value
        flows[key]?.value = value
    }

    override suspend fun saveRawIf(key: String, value: String, shouldWrite: () -> Boolean) {
        // 内存实现无挂起点，校验与赋值在同一段代码内完成。
        if (!shouldWrite()) return
        map[key] = value
        flows[key]?.value = value
    }
}

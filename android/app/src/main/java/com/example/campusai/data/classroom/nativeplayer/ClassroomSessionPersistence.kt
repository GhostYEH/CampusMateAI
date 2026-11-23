package com.example.campusai.data.classroom.nativeplayer

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.withTimeoutOrNull
import java.io.IOException
import java.util.Collections

/**
 * 本地课堂进度的读取结果。
 *
 * 必须把「确实没有数据」与「读不出来」分开：前者按首次到访处理，
 * 后者不能当成空账本，更不能在随后结算时覆盖原有记录。
 */
sealed interface ClassroomLocalRead<out T> {
    data class Value<T>(val value: T) : ClassroomLocalRead<T>
    data object Missing : ClassroomLocalRead<Nothing>
    data class Failed(val error: Throwable?) : ClassroomLocalRead<Nothing>
}

val ClassroomLocalRead<*>.failed: Boolean get() = this is ClassroomLocalRead.Failed

/**
 * 读取本地课堂状态，只把 IO/存储异常转为 [ClassroomLocalRead.Failed]。
 * 协程取消继续向上抛出，避免把退出课堂当成一次普通的读取失败。
 */
suspend fun <T : Any> readClassroomLocal(reader: suspend () -> T?): ClassroomLocalRead<T> =
    try {
        val value = reader()
        if (value == null) ClassroomLocalRead.Missing else ClassroomLocalRead.Value(value)
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (error: Exception) {
        ClassroomLocalRead.Failed(error)
    }

/**
 * 进程内的课堂本地写入仲裁。
 *
 * 每次写入在调度时领取一个单调递增的票据；只有仍是最新票据的写入才允许提交。
 * 快速关闭并重开课堂时，旧会话的迟到快照会因此让位于新会话已经排入的更新，
 * 但新会话尚未写入任何内容时，旧会话的退出落盘仍然有效。
 */
object ClassroomLocalWriteGate {
    private val latestGrants = mutableMapOf<String, Long>()
    private var nextGrant = 0L

    @Synchronized
    fun grant(key: String): Long {
        nextGrant += 1
        latestGrants[key] = nextGrant
        return nextGrant
    }

    @Synchronized
    fun isCurrent(key: String, grant: Long): Boolean = latestGrants[key] == grant

    @Synchronized
    fun reset() {
        latestGrants.clear()
        nextGrant = 0L
    }
}

enum class ClassroomWriteStatus { SAVED, STALE, FAILED, TIMED_OUT }

data class ClassroomStateWrite(
    val key: String,
    val label: String,
    val grant: Long,
    val save: suspend () -> Unit,
)

data class ClassroomWriteResult(
    val key: String,
    val label: String,
    val status: ClassroomWriteStatus,
    val attempts: Int,
)

/**
 * 课堂退出/日常落盘的小型执行器。
 *
 * - 单项之间互相隔离：位置写入失败不会跳过奖励或草稿；
 * - 只为可恢复的 [IOException] 做有界重试，重试受同一个总预算约束；
 * - 每项有独立时间片，整体超过预算时剩余项标记 TIMED_OUT；
 * - 协程取消原样上抛，超时只影响本次落盘，不会被当成保存成功。
 */
class ClassroomSessionFlusher(
    private val budgetMs: Long = DEFAULT_BUDGET_MS,
    private val itemBudgetMs: Long = DEFAULT_ITEM_BUDGET_MS,
    private val maxAttempts: Int = DEFAULT_MAX_ATTEMPTS,
    private val retryDelayMs: Long = DEFAULT_RETRY_DELAY_MS,
    private val onResult: (ClassroomWriteResult) -> Unit = {},
) {

    /** 在独立作用域落盘，退出页面或 ViewModel 清理后仍能完成。 */
    fun flush(writes: List<ClassroomStateWrite>): Job? {
        if (writes.isEmpty()) return null
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        return scope.launch {
            try {
                run(writes)
            } finally {
                scope.cancel()
            }
        }
    }

    /** 供调用方等待结果（测试与需要确认落盘的场景使用）。 */
    suspend fun run(writes: List<ClassroomStateWrite>): List<ClassroomWriteResult> {
        if (writes.isEmpty()) return emptyList()
        val results = Collections.synchronizedMap(mutableMapOf<String, ClassroomWriteResult>())
        val completed = withTimeoutOrNull(budgetMs) {
            supervisorScope {
                writes.map { write ->
                    async {
                        runWrite(write).also { results[write.key] = it }
                    }
                }.awaitAll()
            }
        }
        val finalResults = completed ?: writes.map { write ->
            results[write.key] ?: ClassroomWriteResult(
                key = write.key,
                label = write.label,
                status = ClassroomWriteStatus.TIMED_OUT,
                attempts = 0,
            )
        }
        finalResults.forEach(onResult)
        return finalResults
    }

    private suspend fun runWrite(write: ClassroomStateWrite): ClassroomWriteResult {
        var attempts = 0
        while (true) {
            if (!ClassroomLocalWriteGate.isCurrent(write.key, write.grant)) {
                return result(write, ClassroomWriteStatus.STALE, attempts)
            }
            attempts += 1
            try {
                val saved = withTimeoutOrNull(itemBudgetMs) {
                    write.save()
                    true
                }
                if (saved == true) return result(write, ClassroomWriteStatus.SAVED, attempts)
                return result(write, ClassroomWriteStatus.TIMED_OUT, attempts)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Throwable) {
                if (attempts >= maxAttempts || error !is IOException) {
                    return result(write, ClassroomWriteStatus.FAILED, attempts)
                }
                delay(retryDelayMs)
            }
        }
    }

    private fun result(
        write: ClassroomStateWrite,
        status: ClassroomWriteStatus,
        attempts: Int,
    ) = ClassroomWriteResult(write.key, write.label, status, attempts)

    companion object {
        const val DEFAULT_BUDGET_MS = 6_000L
        const val DEFAULT_ITEM_BUDGET_MS = 2_500L
        const val DEFAULT_MAX_ATTEMPTS = 3
        const val DEFAULT_RETRY_DELAY_MS = 150L
    }
}

package com.example.campusai.data.classroom.nativeplayer

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
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
 * 结果按「记录键 + 票据代次」保存，旧会话的迟到回包不会覆盖新代次的确认结果。
 * 快速关闭并重开课堂时，旧会话的退出落盘会先被等待；若最新写入失败，VM 可凭
 * 仍属于当前代次的快照做有界恢复，再重新读取确认后的位置与账本。
 */
object ClassroomLocalWriteGate {
    private val latestGrants = mutableMapOf<String, Long>()
    private val pending = mutableMapOf<String, Int>()
    private val idleSignals = mutableMapOf<String, CompletableDeferred<Unit>>()
    private val lastResults = mutableMapOf<String, ClassroomWriteResult>()
    private val latestSnapshots = mutableMapOf<String, ClassroomLocalSnapshot>()

    /** 正在恢复的「记录键 -> 快照代次」；同一份快照只能由一个任务认领。 */
    private val recovering = mutableMapOf<String, Long>()
    private var nextGrant = 0L

    @Synchronized
    fun grant(key: String): Long {
        nextGrant += 1
        latestGrants[key] = nextGrant
        // 新代次一旦开始，旧恢复就不能再代表当前状态。清理旧标记，
        // 让后续打开看到新代次的实际结果而不是永久停留在待确认。
        recovering.remove(key)
        return nextGrant
    }

    @Synchronized
    fun isCurrent(key: String, grant: Long): Boolean = latestGrants[key] == grant

    /** 只接受当前写入代次的结果；旧代次的迟到回包不覆盖新代次。 */
    @Synchronized
    fun recordResult(result: ClassroomWriteResult) {
        if (latestGrants[result.key] != result.grant) return
        lastResults[result.key] = result
    }

    /** 兼容只关心键与状态的调用；没有票据时补一个当前代次。 */
    @Synchronized
    fun recordResult(key: String, status: ClassroomWriteStatus) {
        val grant = latestGrants[key] ?: grant(key)
        recordResult(ClassroomWriteResult(key, "", status, 0, grant))
    }

    /** 测试和恢复流程可直接提交带代次的结果；过期代次被静默忽略。 */
    @Synchronized
    fun recordResult(key: String, grant: Long, status: ClassroomWriteStatus) {
        recordResult(ClassroomWriteResult(key, "", status, 0, grant))
    }

    @Synchronized
    fun rememberSnapshot(key: String, grant: Long, payload: String) {
        if (latestGrants[key] == grant) {
            latestSnapshots[key] = ClassroomLocalSnapshot(key, grant, payload)
        }
    }

    @Synchronized
    fun latestSnapshot(key: String): ClassroomLocalSnapshot? = latestSnapshotInternal(key)

    /**
     * 在同一原子操作内核对快照的记录键、当前代次和恢复占用，然后认领本次恢复。
     *
     * 只有快照仍是该键的当前代次、且没有其它任务正在恢复同一份快照时才成功。
     * 认领不会推进代次：恢复写入仍使用快照自己的票据，任何新写入都会让它失效；
     * 这样旧内容不可能因为「重新领票」被提升到新代次。
     */
    @Synchronized
    fun claimRecovery(snapshots: List<ClassroomLocalSnapshot>): ClassroomRecoveryClaim {
        if (snapshots.isEmpty()) return ClassroomRecoveryClaim.MISSING
        for (snapshot in snapshots) {
            if (snapshot.key.isBlank()) return ClassroomRecoveryClaim.MISSING
            val current = latestGrants[snapshot.key] ?: return ClassroomRecoveryClaim.MISSING
            if (current != snapshot.grant) return ClassroomRecoveryClaim.SUPERSEDED
            if (latestSnapshots[snapshot.key] != snapshot) return ClassroomRecoveryClaim.SUPERSEDED
            if (recovering[snapshot.key] != null) return ClassroomRecoveryClaim.BUSY
        }
        snapshots.forEach { recovering[it.key] = it.grant }
        return ClassroomRecoveryClaim.CLAIMED
    }

    /** 只释放本次任务认领的代次；旧任务不能清掉新代次正在进行的恢复。 */
    @Synchronized
    fun releaseRecovery(snapshots: List<ClassroomLocalSnapshot>) {
        snapshots.forEach { snapshot ->
            if (recovering[snapshot.key] == snapshot.grant) recovering.remove(snapshot.key)
        }
    }

    @Synchronized
    fun needsRecovery(key: String): Boolean {
        val grant = latestGrants[key] ?: return false
        val result = lastResults[key]
        return result == null || result.grant != grant || result.status != ClassroomWriteStatus.SAVED
    }

    private fun latestSnapshotInternal(key: String): ClassroomLocalSnapshot? {
        val snapshot = latestSnapshots[key] ?: return null
        return snapshot.takeIf { it.key == key && latestGrants[key] == it.grant }
    }

    private fun isRecoveryInProgress(key: String): Boolean {
        val grant = recovering[key] ?: return false
        return latestGrants[key] == grant
    }

    /**
     * 读取屏障的四种结果：
     * - [SUCCESS]：没有上一轮写入，或当前代次明确保存成功；
     * - [FAILED]：上一轮已完成但失败、超时或被更新写入取代；
     * - [UNKNOWN]：等待结束前仍有写入未完成；
     * - [PENDING]：另一任务正在恢复同一份快照，结果尚未回读确认。
     */
    @Synchronized
    fun restoreState(positionKey: String, rewardsKey: String, idle: Boolean): ClassroomLocalRestore {
        if (isRecoveryInProgress(positionKey) || isRecoveryInProgress(rewardsKey)) {
            return ClassroomLocalRestore.PENDING
        }
        if (!idle) return ClassroomLocalRestore.UNKNOWN
        return if (isSuccessful(positionKey) && isSuccessful(rewardsKey)) {
            ClassroomLocalRestore.SUCCESS
        } else {
            ClassroomLocalRestore.FAILED
        }
    }

    private fun isSuccessful(key: String): Boolean {
        val grant = latestGrants[key] ?: return true
        val result = lastResults[key] ?: return false
        return result.grant == grant && result.status == ClassroomWriteStatus.SAVED
    }

    /** 退出落盘已排队但尚未结束时，新会话读取同一课堂前应等待，避免以旧账本起步。 */
    @Synchronized
    fun beginPending(key: String) {
        val count = pending[key] ?: 0
        pending[key] = count + 1
        if (count == 0) idleSignals[key] = CompletableDeferred()
    }

    @Synchronized
    fun finishPending(key: String) {
        val count = (pending[key] ?: 0) - 1
        if (count <= 0) {
            pending.remove(key)
            idleSignals.remove(key)?.complete(Unit)
        } else {
            pending[key] = count
        }
    }

    suspend fun awaitIdle(key: String) {
        while (true) {
            val signal = synchronized(this) {
                if ((pending[key] ?: 0) > 0) idleSignals[key] else null
            }
            if (signal == null) return
            signal.await()
        }
    }

    /** 当前没有排队或进行中的写入/恢复任务时返回 true。 */
    @Synchronized
    fun isIdle(vararg keys: String): Boolean = keys.all { (pending[it] ?: 0) == 0 }

    @Synchronized
    fun reset() {
        latestGrants.clear()
        pending.clear()
        idleSignals.values.forEach { it.complete(Unit) }
        idleSignals.clear()
        lastResults.clear()
        latestSnapshots.clear()
        recovering.clear()
        nextGrant = 0L
    }
}

enum class ClassroomLocalRestore { SUCCESS, FAILED, UNKNOWN, PENDING }

/** 某次恢复的原子认领结果；只有 [CLAIMED] 允许继续写入和回读。 */
enum class ClassroomRecoveryClaim { CLAIMED, BUSY, SUPERSEDED, MISSING }

/** 某个记录键最近一次仍可信的待落盘快照；键和代次都必须匹配当前记录。 */
data class ClassroomLocalSnapshot(val key: String, val grant: Long, val payload: String)

enum class ClassroomWriteStatus {
    SAVED,
    STALE,
    ACCOUNT_CHANGED,
    CONFLICT,
    IO_ERROR,
    FAILED,
    TIMED_OUT,
}

/** 退出补存时发现作答代次已前进，当前快照不再是最终版本。 */
class ClassroomWriteStaleException(message: String = "课堂状态已被更新的写入取代") : Exception(message)

/** 退出补存拿到写锁后账号已经切换，不能把原账号的草稿发出去。 */
class ClassroomWriteAccountChangedException(message: String = "课堂账号已经切换") : Exception(message)

/** 服务端已有不可回退的提交记录，草稿回退被 409 拒绝。 */
class ClassroomWriteConflictException(message: String = "课堂记录已被服务端确认") : Exception(message)

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
    val grant: Long = 0L,
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
        // 同步登记待写状态，保证紧接着重开的会话读取前能看到这次退出落盘。
        writes.forEach { ClassroomLocalWriteGate.beginPending(it.key) }
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        val job = scope.launch {
            try {
                run(writes, trackPending = false)
            } finally {
                scope.cancel()
            }
        }
        // 完成回调对「尚未启动就被取消」同样生效，避免待写标记永久悬挂。
        job.invokeOnCompletion {
            writes.forEach { ClassroomLocalWriteGate.finishPending(it.key) }
        }
        return job
    }

    /** 供调用方等待结果（测试与需要确认落盘的场景使用）。 */
    suspend fun run(
        writes: List<ClassroomStateWrite>,
        trackPending: Boolean = true,
        recordResults: Boolean = true,
    ): List<ClassroomWriteResult> {
        if (writes.isEmpty()) return emptyList()
        if (trackPending) writes.forEach { ClassroomLocalWriteGate.beginPending(it.key) }
        try {
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
                    grant = write.grant,
                )
            }
            finalResults.forEach {
                // 恢复流程必须先回读确认，不能在这里提前发布 SAVED。
                if (recordResults) ClassroomLocalWriteGate.recordResult(it)
                onResult(it)
            }
            return finalResults
        } finally {
            if (trackPending) writes.forEach { ClassroomLocalWriteGate.finishPending(it.key) }
        }
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
                if (saved == true) {
                    // DataStore 事务内的代次守卫可能已经跳过了本次赋值；即使事务
                    // 正常返回，也只有代次仍有效才能算 SAVED，跳过的写入明确记为 STALE。
                    return result(
                        write,
                        if (ClassroomLocalWriteGate.isCurrent(write.key, write.grant)) {
                            ClassroomWriteStatus.SAVED
                        } else {
                            ClassroomWriteStatus.STALE
                        },
                        attempts,
                    )
                }
                return result(write, ClassroomWriteStatus.TIMED_OUT, attempts)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (stale: ClassroomWriteStaleException) {
                return result(write, ClassroomWriteStatus.STALE, attempts)
            } catch (accountChanged: ClassroomWriteAccountChangedException) {
                return result(write, ClassroomWriteStatus.ACCOUNT_CHANGED, attempts)
            } catch (conflict: ClassroomWriteConflictException) {
                return result(write, ClassroomWriteStatus.CONFLICT, attempts)
            } catch (error: Throwable) {
                val retryable = error is IOException
                if (!retryable || attempts >= maxAttempts) {
                    return result(
                        write,
                        if (retryable) ClassroomWriteStatus.IO_ERROR else ClassroomWriteStatus.FAILED,
                        attempts,
                    )
                }
                delay(retryDelayMs)
            }
        }
    }

    private fun result(
        write: ClassroomStateWrite,
        status: ClassroomWriteStatus,
        attempts: Int,
    ) = ClassroomWriteResult(write.key, write.label, status, attempts, write.grant)

    companion object {
        const val DEFAULT_BUDGET_MS = 6_000L
        const val DEFAULT_ITEM_BUDGET_MS = 2_500L
        const val DEFAULT_MAX_ATTEMPTS = 3
        const val DEFAULT_RETRY_DELAY_MS = 150L
    }
}

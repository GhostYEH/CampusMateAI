package com.example.campusai.data.classroom.nativeplayer

import kotlinx.coroutines.withTimeoutOrNull

/** 阻塞动作的等待结果。超时和取消是两种独立状态，调用方不能把两者都当成失败。 */
internal sealed interface ClassroomSequenceWait<out T> {
    data class Value<T>(val value: T) : ClassroomSequenceWait<T>
    data object Timeout : ClassroomSequenceWait<Nothing>
    data object Cancelled : ClassroomSequenceWait<Nothing>
}

/**
 * 在暂停期间不计时的前提下等待一个动作信号。
 *
 * 每次只等待一小段，便于在用户暂停、换页或账号切换时尽快退出；[awaitPause] 在
 * 暂停时挂起，因此暂停时间不会消耗 [timeoutMs]。等待超时后回调即使到达，也只
 * 会完成旧的 [awaitSignal] 结果，不会影响下一次等待。
 */
internal suspend fun <T : Any> awaitClassroomSequenceSignal(
    timeoutMs: Long,
    isCurrent: () -> Boolean,
    awaitPause: suspend () -> Unit,
    awaitSignal: suspend () -> T,
    sliceMs: Long = 1_000L,
): ClassroomSequenceWait<T> {
    var remaining = timeoutMs.coerceAtLeast(1L)
    while (remaining > 0L) {
        awaitPause()
        if (!isCurrent()) return ClassroomSequenceWait.Cancelled
        val slice = minOf(remaining, sliceMs.coerceAtLeast(1L))
        val value = withTimeoutOrNull(slice) { awaitSignal() }
        if (value != null) return ClassroomSequenceWait.Value(value)
        remaining -= slice
    }
    return ClassroomSequenceWait.Timeout
}

package com.example.campusai.data.classroom.nativeplayer

/**
 * 媒体请求代次。
 *
 * 账号、课堂或页面切换后，旧请求即使晚到也不能写回新课堂，更不能复用新账号的缓存。
 * 纯 JVM 实现，便于在单元测试里复现「迟到响应」。
 */
class ClassroomMediaSession(
    private val accountScope: String,
    private val ref: NativeClassroomRef,
) {
    private var generation = 0

    @Synchronized
    fun beginRequest(): Int = ++generation

    @Synchronized
    fun invalidate() {
        generation++
    }

    @Synchronized
    fun isCurrent(requestGeneration: Int, accountScope: String, ref: NativeClassroomRef): Boolean =
        requestGeneration == generation &&
            accountScope == this.accountScope &&
            ref.stableKey == this.ref.stableKey
}

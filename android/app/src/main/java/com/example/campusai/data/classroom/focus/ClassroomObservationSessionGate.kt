package com.example.campusai.data.classroom.focus

/**
 * 观察会话代次。控制器用它拒绝关闭/重开/快速切课后的旧异步回调。
 * 只做单调计数，不接触 Android，可在普通 JVM 测试中覆盖。
 */
class ClassroomObservationSessionGate {
    private var currentId = 0L

    @Synchronized
    fun open(): Long {
        currentId += 1
        return currentId
    }

    @Synchronized
    fun close() {
        currentId += 1
    }

    @Synchronized
    fun isCurrent(sessionId: Long): Boolean = sessionId == currentId
}

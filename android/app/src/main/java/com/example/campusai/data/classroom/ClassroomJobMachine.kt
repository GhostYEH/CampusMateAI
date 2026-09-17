package com.example.campusai.data.classroom

/**
 * CPM 互动课堂生成的异步状态机（与 Web `classroomJobMachine.js` 同一套语义）。
 *
 * 真实时序：
 *   POST /agent-jobs → 立刻返回 QUEUED、pending_approval_id = null
 *   Worker 稍后执行   → GET /agent-jobs/{id} 才变成 AWAITING_APPROVAL + pending_approval_id
 *   学生批准          → **只**调用审批接口；后端把原 Run 重新排队并继续执行
 *   继续订阅同一个 Job → 终态后读取 session_id / deep_link
 *
 * 两条硬约束：
 * 1. 绝不创建"携带旧 approval_id 的第二个 Job"（跨请求复用审批的漏洞入口）；
 * 2. 不用"已提交"冒充"已生成完成"。
 */
enum class JobPhase {
    IDLE,
    CREATING_JOB,
    QUEUED,
    AWAITING_APPROVAL,
    APPROVING,
    RUNNING,
    SUCCEEDED,
    FAILED,
    REJECTED,
    EXPIRED,
}

data class ClassroomJobState(
    val phase: JobPhase = JobPhase.IDLE,
    val jobId: String? = null,
    val runId: String? = null,
    val approvalId: String? = null,
    val sessionId: String? = null,
    val deepLink: String? = null,
    val status: String? = null,
    val error: String = "",
    /** 是否已经发起过创建请求（恢复时用它避免重复创建）。 */
    val created: Boolean = false,
) {
    val canConfirm: Boolean
        get() = !created && (phase == JobPhase.IDLE || phase == JobPhase.FAILED)

    val canApprove: Boolean
        get() = phase == JobPhase.AWAITING_APPROVAL && !approvalId.isNullOrBlank()

    val needsPolling: Boolean
        get() = phase == JobPhase.QUEUED || phase == JobPhase.RUNNING || phase == JobPhase.AWAITING_APPROVAL

    /** 已成功但后端还没回填深链 —— 继续等，不要说"已完成"。 */
    val awaitingOutcome: Boolean
        get() = phase == JobPhase.SUCCEEDED && deepLink.isNullOrBlank()

    val isTerminal: Boolean
        get() = phase == JobPhase.SUCCEEDED || phase == JobPhase.FAILED ||
            phase == JobPhase.REJECTED || phase == JobPhase.EXPIRED
}

/** 后端 job 快照（只保留状态机需要的字段）。 */
data class JobSnapshot(
    val jobId: String? = null,
    val runId: String? = null,
    val status: String? = null,
    val pendingApprovalId: String? = null,
    val sessionId: String? = null,
    val deepLink: String? = null,
)

object ClassroomJobMachine {

    fun phaseOf(snapshot: JobSnapshot?): JobPhase {
        val snap = snapshot ?: return JobPhase.QUEUED
        if (!snap.pendingApprovalId.isNullOrBlank()) return JobPhase.AWAITING_APPROVAL
        return when (snap.status?.trim()?.uppercase()) {
            "SUCCEEDED", "PARTIAL" -> JobPhase.SUCCEEDED
            "CANCELLED" -> JobPhase.REJECTED
            "FAILED" -> JobPhase.FAILED
            "RUNNING" -> JobPhase.RUNNING
            "AWAITING_APPROVAL" -> JobPhase.AWAITING_APPROVAL
            else -> JobPhase.QUEUED
        }
    }

    fun confirmRequested(state: ClassroomJobState): ClassroomJobState =
        if (!state.canConfirm) state
        else state.copy(phase = JobPhase.CREATING_JOB, created = true, error = "")

    fun jobCreated(state: ClassroomJobState, snapshot: JobSnapshot): ClassroomJobState = state.copy(
        jobId = snapshot.jobId ?: state.jobId,
        runId = snapshot.runId ?: state.runId,
        approvalId = snapshot.pendingApprovalId,
        status = snapshot.status ?: state.status,
        phase = phaseOf(snapshot),
        sessionId = snapshot.sessionId ?: state.sessionId,
        deepLink = snapshot.deepLink ?: state.deepLink,
        error = "",
    )

    fun createFailed(state: ClassroomJobState, message: String): ClassroomJobState =
        // 失败要允许重试：清掉 created，否则按钮会被永久禁用
        state.copy(phase = JobPhase.FAILED, created = false, error = message)

    fun pollResult(state: ClassroomJobState, snapshot: JobSnapshot): ClassroomJobState {
        val phase = phaseOf(snapshot)
        // 轮询只允许阶段前进；后端在续跑期间会短暂返回旧快照，不能把
        // 已批准的 RUNNING 回退成"等审批"。
        val regressed = state.phase == JobPhase.RUNNING && phase == JobPhase.AWAITING_APPROVAL
        return state.copy(
            jobId = snapshot.jobId ?: state.jobId,
            runId = snapshot.runId ?: state.runId,
            approvalId = if (regressed) state.approvalId else snapshot.pendingApprovalId,
            status = snapshot.status ?: state.status,
            phase = if (regressed) state.phase else phase,
            sessionId = snapshot.sessionId ?: state.sessionId,
            deepLink = snapshot.deepLink ?: state.deepLink,
        )
    }

    /** 网络抖动只记录原因，不改变已确定的阶段。 */
    fun pollFailed(state: ClassroomJobState, message: String): ClassroomJobState =
        state.copy(error = message)

    fun approveRequested(state: ClassroomJobState): ClassroomJobState =
        if (!state.canApprove) state
        else state.copy(phase = JobPhase.APPROVING, error = "")

    fun approveDone(state: ClassroomJobState, snapshot: JobSnapshot): ClassroomJobState {
        val phase = phaseOf(snapshot)
        return state.copy(
            phase = if (phase == JobPhase.AWAITING_APPROVAL) JobPhase.QUEUED else phase,
            approvalId = null,
            jobId = snapshot.jobId ?: state.jobId,
            status = snapshot.status ?: state.status,
            error = "",
        )
    }

    fun approveRejected(state: ClassroomJobState, message: String = "已拒绝，本次不会生成课堂") =
        state.copy(phase = JobPhase.REJECTED, approvalId = null, error = message)

    fun approveFailed(state: ClassroomJobState, message: String, expired: Boolean = false) =
        state.copy(
            phase = if (expired) JobPhase.EXPIRED else JobPhase.AWAITING_APPROVAL,
            error = message,
        )

    /** 恢复：沿用同一个 jobId，绝不重新创建。 */
    fun restored(jobId: String, phaseName: String? = null): ClassroomJobState =
        ClassroomJobState(
            phase = phaseOfName(phaseName ?: JobPhase.QUEUED.name),
            jobId = jobId,
            created = true,
        )

    /**
     * 持久化的阶段名 → JobPhase。
     *
     * 未知值一律回落到 QUEUED（"还在进行中"）：宁可多轮询一次，也不能把
     * 未知阶段当成终态而漏掉真正的结果，更不能当成 IDLE 而重复创建任务。
     */
    fun phaseOfName(name: String?): JobPhase =
        JobPhase.entries.firstOrNull { it.name == name } ?: JobPhase.QUEUED

    /** 该阶段是否终态（与 `ClassroomJobState.isTerminal` 同一口径）。 */
    fun isTerminalPhase(phase: JobPhase): Boolean =
        phase == JobPhase.SUCCEEDED || phase == JobPhase.FAILED ||
            phase == JobPhase.REJECTED || phase == JobPhase.EXPIRED
}

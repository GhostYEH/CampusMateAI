package com.example.campusai.data.repository

import com.example.campusai.data.remote.ApiService
import com.example.campusai.data.remote.agent.AgentApprovalDto
import com.example.campusai.data.remote.agent.AgentArtifactDto
import com.example.campusai.data.remote.agent.AgentCapabilitiesDto
import com.example.campusai.data.remote.agent.AgentErrorEnvelope
import com.example.campusai.data.remote.agent.AgentErrorParser
import com.example.campusai.data.remote.agent.AgentEventDto
import com.example.campusai.data.remote.agent.AgentIdempotency
import com.example.campusai.data.remote.agent.AgentJobDto
import com.example.campusai.data.remote.agent.AgentRunDto
import com.example.campusai.data.remote.agent.StudentGoalCreateRequest
import com.example.campusai.data.remote.agent.StudentGoalDto
import com.example.campusai.data.remote.agent.LearningPlanSummaryDto
import com.example.campusai.data.remote.agent.AgentSseClient
import com.example.campusai.data.remote.agent.ApprovalDecisionRequest
import kotlinx.coroutines.flow.Flow
import retrofit2.Response

/**
 * Agent Runtime 通用 Repository：capabilities、jobs、runs、approvals、artifacts。
 */
class AgentRuntimeRepository(
    private val api: ApiService,
    private val sseClient: AgentSseClient,
    private val userIdProvider: () -> String,
) {
    suspend fun capabilities(): Result<AgentCapabilitiesDto> = runCatching {
        val response = api.agentCapabilities()
        check(response.isSuccessful) { "加载能力清单失败(${response.code()})" }
        response.body() ?: AgentCapabilitiesDto()
    }

    suspend fun createJob(jobKind: String, payload: Map<String, Any?> = emptyMap()): Result<AgentJobDto> = runCatching {
        val key = AgentIdempotency.payloadKey(userIdProvider(), "create_job", jobKind to payload)
        val response = api.agentCreateJob(mapOf("job_kind" to jobKind, "input_ref" to payload), key)
        check(response.isSuccessful) { "创建任务失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("任务响应为空")
    }

    suspend fun getJob(jobId: String): Result<AgentJobDto> = runCatching {
        val response = api.agentGetJob(jobId)
        check(response.isSuccessful) { "加载任务失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("任务响应为空")
    }

    suspend fun listJobs(): Result<List<AgentJobDto>> = runCatching {
        val response = api.agentListJobs()
        check(response.isSuccessful) { "加载目标执行记录失败(${response.code()})" }
        response.body() ?: emptyList()
    }

    suspend fun listLearningGoals(): Result<List<StudentGoalDto>> = runCatching {
        val response = api.listStudentGoals()
        check(response.isSuccessful) { "加载学习目标失败(${response.code()})" }
        response.body()?.items ?: emptyList()
    }

    suspend fun createLearningGoal(name: String, category: String = "academic"): Result<StudentGoalDto> = runCatching {
        val response = api.createStudentGoal(
            StudentGoalCreateRequest(name = name, category = category,
                idempotencyKey = AgentIdempotency.stableKey(userIdProvider(), "goal", name)),
        )
        check(response.isSuccessful) { "创建学习目标失败(${response.code()})" }
        response.body()?.goal ?: throw IllegalStateException("目标响应为空")
    }

    suspend fun createLearningGoalJob(goalId: String, availableMinutes: Int): Result<AgentJobDto> = createJob(
        "learning_goal", mapOf("goal_id" to goalId, "available_minutes" to availableMinutes),
    )

    suspend fun getRun(runId: String): Result<AgentRunDto> = runCatching {
        val response = api.agentGetRun(runId)
        check(response.isSuccessful) { "加载运行失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("运行响应为空")
    }

    suspend fun cancelRun(runId: String): Result<AgentRunDto> = runCatching {
        val key = AgentIdempotency.stableKey(userIdProvider(), "cancel_run", runId)
        val response = api.agentCancelRun(runId, emptyMap(), key)
        check(response.isSuccessful) { "取消运行失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("运行响应为空")
    }

    suspend fun pauseRun(runId: String, reason: String? = null): Result<AgentRunDto> = runCatching {
        val key = AgentIdempotency.stableKey(userIdProvider(), "pause_run", runId)
        val response = api.agentPauseRun(runId, reason?.let { mapOf("reason" to it) } ?: emptyMap(), key)
        check(response.isSuccessful) { "暂停运行失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("运行响应为空")
    }

    suspend fun resumeRun(runId: String): Result<AgentRunDto> = runCatching {
        val key = AgentIdempotency.stableKey(userIdProvider(), "resume_run", runId)
        val response = api.agentResumeRun(runId, emptyMap(), key)
        check(response.isSuccessful) { "恢复运行失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("运行响应为空")
    }

    suspend fun retryRun(runId: String): Result<AgentRunDto> = runCatching {
        val key = AgentIdempotency.stableKey(userIdProvider(), "retry_run", runId)
        val response = api.agentRetryRun(runId, emptyMap(), key)
        check(response.isSuccessful) { "重试运行失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("运行响应为空")
    }

    suspend fun planSummary(planId: String): Result<LearningPlanSummaryDto> = runCatching {
        val response = api.getLearningPlanSummary(planId)
        check(response.isSuccessful) { "加载计划总结失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("计划总结为空")
    }

    suspend fun confirmPlan(planId: String): Result<LearningPlanSummaryDto> = runCatching {
        val response = api.decideLearningPlan(planId, mapOf("decision" to "ACCEPT"))
        check(response.isSuccessful) { "确认计划失败(${response.code()})" }
        planSummary(planId).getOrThrow()
    }

    suspend fun executePlan(planId: String): Result<LearningPlanSummaryDto> = runCatching {
        val response = api.executeLearningPlan(planId)
        check(response.isSuccessful) { "创建个人待办失败(${response.code()})" }
        planSummary(planId).getOrThrow()
    }

    suspend fun replan(planId: String): Result<LearningPlanSummaryDto> = runCatching {
        val key = AgentIdempotency.stableKey(userIdProvider(), "replan", planId)
        val response = api.replanLearningPlan(planId, key)
        check(response.isSuccessful) { "重新规划失败(${response.code()})" }
        val newPlanId = (response.body()?.get("plan_id") as? String) ?: planId
        planSummary(newPlanId).getOrThrow()
    }

    suspend fun listEvents(runId: String): Result<List<AgentEventDto>> = runCatching {
        val response = api.agentListRunEvents(runId)
        check(response.isSuccessful) { "加载事件失败(${response.code()})" }
        response.body() ?: emptyList()
    }

    fun streamRunEvents(runId: String, lastEventId: String? = null): Flow<AgentSseClient.SseEvent> {
        return sseClient.streamRunEvents(runId, lastEventId)
    }

    suspend fun decideApproval(approvalId: String, decision: String, reason: String? = null): Result<AgentApprovalDto> = runCatching {
        val key = AgentIdempotency.stableKey(userIdProvider(), "decide_approval", approvalId, decision)
        val response = api.agentDecideApproval(approvalId, ApprovalDecisionRequest(decision.uppercase(), reason), key)
        check(response.isSuccessful) { "审批失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("审批响应为空")
    }

    suspend fun getArtifact(artifactId: String): Result<AgentArtifactDto> = runCatching {
        val response = api.agentGetArtifact(artifactId)
        check(response.isSuccessful) { "加载产物失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("产物响应为空")
    }

    fun extractError(response: Response<*>): AgentErrorEnvelope? = AgentErrorParser.parse(response)
}

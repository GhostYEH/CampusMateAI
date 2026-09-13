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

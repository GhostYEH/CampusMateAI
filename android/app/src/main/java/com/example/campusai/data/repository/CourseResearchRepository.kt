package com.example.campusai.data.repository

import com.example.campusai.data.remote.ApiService
import com.example.campusai.data.remote.agent.AgentArtifactDto
import com.example.campusai.data.remote.agent.AgentErrorEnvelope
import com.example.campusai.data.remote.agent.AgentErrorParser
import com.example.campusai.data.remote.agent.AgentEventDto
import com.example.campusai.data.remote.agent.AgentIdempotency
import com.example.campusai.data.remote.agent.AgentSseClient
import com.example.campusai.data.remote.agent.CourseResearchCitationDto
import com.example.campusai.data.remote.agent.CourseResearchRoleProgressDto
import com.example.campusai.data.remote.agent.CourseResearchRunCreateRequest
import com.example.campusai.data.remote.agent.CourseResearchRunDto
import kotlinx.coroutines.flow.Flow
import retrofit2.Response

/**
 * 课程研究 Repository。
 *
 * 表单（question, mode, academic_policy, source_policy）、展示逻辑角色进度、
 * 引用验证状态、PARTIAL 状态和 artifact。
 * 学术策略由后端裁决为最严格值；客户端输入不能强制 ALLOWED。
 */
class CourseResearchRepository(
    private val api: ApiService,
    private val sseClient: AgentSseClient,
    private val userIdProvider: () -> String,
) {
    suspend fun createRun(request: CourseResearchRunCreateRequest): Result<CourseResearchRunDto> = runCatching {
        val key = AgentIdempotency.payloadKey(userIdProvider(), "cr_create_run", request)
        val response = api.agentCreateCourseResearchRun(request, key)
        check(response.isSuccessful) { "创建研究请求失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("研究请求响应为空")
    }

    suspend fun listRuns(): Result<List<CourseResearchRunDto>> = runCatching {
        val response = api.agentListCourseResearchRuns()
        check(response.isSuccessful) { "加载研究记录失败(${response.code()})" }
        response.body()?.items ?: emptyList()
    }

    suspend fun getRun(runId: String): Result<CourseResearchRunDto> = runCatching {
        val response = api.agentGetCourseResearchRun(runId)
        check(response.isSuccessful) { "加载研究记录失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("研究记录响应为空")
    }

    suspend fun cancelRun(runId: String): Result<Unit> = runCatching {
        val key = AgentIdempotency.stableKey(userIdProvider(), "cr_cancel", runId)
        val response = api.agentCancelCourseResearchRun(runId, key)
        check(response.isSuccessful) { "取消研究失败(${response.code()})" }
    }

    suspend fun listArtifacts(runId: String): Result<List<AgentArtifactDto>> = runCatching {
        val response = api.agentListCourseResearchArtifacts(runId)
        check(response.isSuccessful) { "加载研究产物失败(${response.code()})" }
        response.body()?.items ?: emptyList()
    }

    suspend fun listRoleProgress(runId: String): Result<List<CourseResearchRoleProgressDto>> = runCatching {
        val response = api.agentListCourseResearchRoleProgress(runId)
        check(response.isSuccessful) { "加载角色进度失败(${response.code()})" }
        response.body()?.items ?: emptyList()
    }

    suspend fun listCitations(runId: String): Result<List<CourseResearchCitationDto>> = runCatching {
        val response = api.agentListCourseResearchCitations(runId)
        check(response.isSuccessful) { "加载引用失败(${response.code()})" }
        response.body()?.items ?: emptyList()
    }

    fun streamRunEvents(runId: String, lastEventId: String? = null): Flow<AgentSseClient.SseEvent> {
        return sseClient.streamRunEvents(runId, lastEventId)
    }

    fun extractError(response: Response<*>): AgentErrorEnvelope? = AgentErrorParser.parse(response)
}
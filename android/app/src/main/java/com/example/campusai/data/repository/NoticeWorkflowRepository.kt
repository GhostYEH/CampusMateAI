package com.example.campusai.data.repository

import com.example.campusai.data.remote.ApiService
import com.example.campusai.data.remote.agent.AgentErrorEnvelope
import com.example.campusai.data.remote.agent.AgentErrorParser
import com.example.campusai.data.remote.agent.AgentIdempotency
import com.example.campusai.data.remote.agent.ApprovalDecisionRequest
import com.example.campusai.data.remote.agent.NoticeActionStatus
import com.example.campusai.data.remote.agent.NoticeManualCreateRequest
import com.example.campusai.data.remote.agent.NoticeManualResponseDto
import com.example.campusai.data.remote.agent.NoticeWorkflowActionDto
import com.example.campusai.data.remote.agent.NoticeWorkflowCreateRequest
import com.example.campusai.data.remote.agent.NoticeWorkflowDto
import com.example.campusai.data.remote.agent.NotificationSourceDto
import com.example.campusai.data.remote.agent.NotificationSourcePatchRequest
import kotlinx.coroutines.flow.Flow
import retrofit2.Response

/**
 * 通知事务 Repository。
 *
 * 粘贴通知先调用 /notices/manual 获取 server notice_id，再创建 workflow。
 * 展示 action 风险、依据、confidence、批准/拒绝和执行状态。
 * MANUAL_ONLY 动作不自动执行；客户端只展示引导。
 */
class NoticeWorkflowRepository(
    private val api: ApiService,
    private val userIdProvider: () -> String,
) {
    suspend fun listSources(): Result<List<NotificationSourceDto>> = runCatching {
        val response = api.agentListNotificationSources()
        check(response.isSuccessful) { "加载通知来源失败(${response.code()})" }
        response.body() ?: emptyList()
    }

    suspend fun patchSource(sourceId: String, request: NotificationSourcePatchRequest): Result<NotificationSourceDto> = runCatching {
        val response = api.agentPatchNotificationSource(sourceId, request)
        check(response.isSuccessful) { "更新通知来源失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("通知来源响应为空")
    }

    /**
     * 粘贴通知：先获取 server notice_id，再创建 workflow。
     * 两步都使用稳定 Idempotency-Key，避免重组或重试重复创建。
     */
    suspend fun createWorkflowFromText(content: String, sourceName: String, publishedAt: String? = null): Result<NoticeWorkflowDto> = runCatching {
        val userId = userIdProvider()
        val manualKey = AgentIdempotency.stableKey(userId, "nw_manual_notice", content, sourceName)
        val manualResponse = api.agentCreateManualNotice(
            NoticeManualCreateRequest(
                title = content.lineSequence().firstOrNull()?.take(128).orEmpty().ifBlank { "校园通知" },
                content = content,
                sourceName = sourceName,
            ),
            manualKey,
        )
        check(manualResponse.isSuccessful) { "创建通知失败(${manualResponse.code()})" }
        val noticeId = manualResponse.body()?.noticeId?.takeIf { it.isNotBlank() }
            ?: throw IllegalStateException("未获得通知 ID")
        val workflowKey = AgentIdempotency.stableKey(userId, "nw_create_workflow", noticeId)
        val workflowResponse = api.agentCreateNoticeWorkflow(
            noticeId,
            NoticeWorkflowCreateRequest(),
            workflowKey,
        )
        check(workflowResponse.isSuccessful) { "创建工作流失败(${workflowResponse.code()})" }
        workflowResponse.body() ?: throw IllegalStateException("工作流响应为空")
    }

    suspend fun getWorkflow(workflowId: String): Result<NoticeWorkflowDto> = runCatching {
        val response = api.agentGetNoticeWorkflow(workflowId)
        check(response.isSuccessful) { "加载工作流失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("工作流响应为空")
    }

    suspend fun reanalyze(workflowId: String): Result<NoticeWorkflowDto> = runCatching {
        val key = AgentIdempotency.stableKey(userIdProvider(), "nw_reanalyze", workflowId)
        val response = api.agentReanalyzeNoticeWorkflow(workflowId, emptyMap(), key)
        check(response.isSuccessful) { "重新分析失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("工作流响应为空")
    }

    suspend fun decideAction(actionId: String, decision: String, reason: String? = null): Result<NoticeWorkflowActionDto> = runCatching {
        val key = AgentIdempotency.stableKey(userIdProvider(), "nw_decide", actionId, decision)
        val response = api.agentDecideNoticeWorkflowAction(actionId, ApprovalDecisionRequest(decision, reason), key)
        check(response.isSuccessful) { "审批动作失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("动作响应为空")
    }

    suspend fun executeAction(actionId: String): Result<NoticeWorkflowActionDto> = runCatching {
        val key = AgentIdempotency.stableKey(userIdProvider(), "nw_execute", actionId)
        val response = api.agentExecuteNoticeWorkflowAction(actionId, emptyMap(), key)
        check(response.isSuccessful) { "执行动作失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("动作响应为空")
    }

    fun extractError(response: Response<*>): AgentErrorEnvelope? = AgentErrorParser.parse(response)
}

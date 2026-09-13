package com.example.campusai.data.repository

import com.example.campusai.data.remote.ApiService
import com.example.campusai.data.remote.agent.AgentErrorEnvelope
import com.example.campusai.data.remote.agent.AgentErrorParser
import com.example.campusai.data.remote.agent.AgentEventDto
import com.example.campusai.data.remote.agent.AgentIdempotency
import com.example.campusai.data.remote.agent.AgentSseClient
import com.example.campusai.data.remote.agent.FinalReviewAdjustmentProposalDto
import com.example.campusai.data.remote.agent.FinalReviewCampaignCreateRequest
import com.example.campusai.data.remote.agent.FinalReviewCampaignDto
import com.example.campusai.data.remote.agent.FinalReviewDailyAgendaDto
import com.example.campusai.data.remote.agent.FinalReviewEvidenceRequest
import com.example.campusai.data.remote.agent.FinalReviewActivateRequest
import com.example.campusai.data.remote.agent.FinalReviewCompleteItemRequest
import com.example.campusai.data.remote.agent.FinalReviewPlanGenerateDto
import com.example.campusai.data.remote.agent.ApprovalDecisionRequest
import com.example.campusai.data.remote.agent.FinalReviewPlanVersionDto
import kotlinx.coroutines.flow.Flow
import retrofit2.Response

/**
 * 期末复习 Repository。
 *
 * 客户端只消费后端协议：创建 campaign、展示 plan version、今日 agenda、
 * 提交 evidence、查看 adjustment proposal、批准/拒绝、查看历史版本。
 * 不在客户端复制领域决策（计划生成、调整分析由后端完成）。
 */
class FinalReviewRepository(
    private val api: ApiService,
    private val sseClient: AgentSseClient,
    private val userIdProvider: () -> String,
) {
    suspend fun listCampaigns(): Result<List<FinalReviewCampaignDto>> = runCatching {
        val response = api.agentListFinalReviewCampaigns()
        check(response.isSuccessful) { "加载复习活动失败(${response.code()})" }
        response.body() ?: emptyList()
    }

    suspend fun createCampaign(request: FinalReviewCampaignCreateRequest): Result<FinalReviewCampaignDto> = runCatching {
        val key = AgentIdempotency.payloadKey(userIdProvider(), "fr_create_campaign", request)
        val response = api.agentCreateFinalReviewCampaign(request, key)
        check(response.isSuccessful) { "创建复习活动失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("创建复习活动响应为空")
    }

    suspend fun getCampaign(campaignId: String): Result<FinalReviewCampaignDto> = runCatching {
        val response = api.agentGetFinalReviewCampaign(campaignId)
        check(response.isSuccessful) { "加载复习活动失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("复习活动响应为空")
    }

    suspend fun generatePlan(campaignId: String): Result<FinalReviewPlanGenerateDto> = runCatching {
        val key = AgentIdempotency.stableKey(userIdProvider(), "fr_generate_plan", campaignId)
        val response = api.agentGenerateFinalReviewPlan(campaignId, emptyMap(), key)
        check(response.isSuccessful) { "生成计划失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("生成计划响应为空")
    }

    suspend fun listPlanVersions(campaignId: String): Result<List<FinalReviewPlanVersionDto>> = runCatching {
        val response = api.agentListFinalReviewPlanVersions(campaignId)
        check(response.isSuccessful) { "加载计划版本失败(${response.code()})" }
        response.body() ?: emptyList()
    }

    suspend fun getPlanVersion(campaignId: String, version: Int): Result<FinalReviewPlanVersionDto> = runCatching {
        val response = api.agentGetFinalReviewPlanVersion(campaignId, version)
        check(response.isSuccessful) { "加载计划版本失败(${response.code()})" }
        response.body() ?: throw IllegalStateException("计划版本响应为空")
    }

    suspend fun activatePlan(campaignId: String, version: Int): Result<Unit> = runCatching {
        val key = AgentIdempotency.stableKey(userIdProvider(), "fr_activate", campaignId, version.toString())
        val response = api.agentActivateFinalReviewPlan(campaignId, FinalReviewActivateRequest(version), key)
        check(response.isSuccessful) { "激活计划失败(${response.code()})" }
    }

    suspend fun approvePlan(approvalId: String): Result<Unit> = runCatching {
        val key = AgentIdempotency.stableKey(userIdProvider(), "fr_approve_plan", approvalId)
        val response = api.agentDecideApproval(
            approvalId,
            ApprovalDecisionRequest("APPROVED", "用户确认激活期末复习计划"),
            key,
        )
        check(response.isSuccessful) { "批准计划失败(${response.code()})" }
    }

    suspend fun getTodayAgenda(campaignId: String): Result<FinalReviewDailyAgendaDto> = runCatching {
        val response = api.agentGetFinalReviewTodayAgenda(campaignId)
        check(response.isSuccessful) { "加载今日议程失败(${response.code()})" }
        response.body() ?: FinalReviewDailyAgendaDto()
    }

    suspend fun completeDailyItem(itemId: String, evidence: FinalReviewEvidenceRequest): Result<Unit> = runCatching {
        val key = AgentIdempotency.stableKey(userIdProvider(), "fr_complete_item", itemId)
        val response = api.agentCompleteFinalReviewDailyItem(
            itemId,
            FinalReviewCompleteItemRequest(feedback = evidence.selfReport),
            key,
        )
        check(response.isSuccessful) { "提交完成失败(${response.code()})" }
    }

    suspend fun analyzeAdjustments(campaignId: String): Result<Unit> = runCatching {
        val key = AgentIdempotency.stableKey(userIdProvider(), "fr_analyze", campaignId)
        val response = api.agentAnalyzeFinalReviewAdjustments(campaignId, emptyMap(), key)
        check(response.isSuccessful) { "分析调整失败(${response.code()})" }
    }

    suspend fun listAdjustmentProposals(campaignId: String): Result<List<FinalReviewAdjustmentProposalDto>> = runCatching {
        val response = api.agentListFinalReviewAdjustmentProposals(campaignId)
        check(response.isSuccessful) { "加载调整提案失败(${response.code()})" }
        response.body() ?: emptyList()
    }

    suspend fun decideAdjustment(proposalId: String, decision: String, reason: String? = null): Result<Unit> = runCatching {
        val key = AgentIdempotency.stableKey(userIdProvider(), "fr_decide", proposalId, decision)
        val response = api.agentDecideFinalReviewAdjustment(
            proposalId,
            com.example.campusai.data.remote.agent.ApprovalDecisionRequest(decision, reason),
            key,
        )
        check(response.isSuccessful) { "审批调整失败(${response.code()})" }
    }

    fun streamCampaignEvents(campaignId: String, lastEventId: String? = null): Flow<AgentSseClient.SseEvent> {
        return sseClient.streamRunEvents(campaignId, lastEventId)
    }

    fun extractError(response: Response<*>): AgentErrorEnvelope? = AgentErrorParser.parse(response)
}

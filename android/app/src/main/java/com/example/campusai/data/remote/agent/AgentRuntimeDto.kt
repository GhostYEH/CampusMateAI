package com.example.campusai.data.remote.agent

import com.squareup.moshi.Json

/**
 * Agent Runtime v1 DTO 层。
 *
 * 服务端 ID 一律 String；未知枚举映射 UNKNOWN/保守值，不崩溃。
 * 客户端只消费后端协议，不复制领域决策。
 */

internal inline fun <reified T : Enum<T>> safeEnum(raw: String?, known: Array<T>, unknown: T): T {
    if (raw == null) return unknown
    return known.firstOrNull { it.name == raw } ?: unknown
}

// ── Runtime 枚举 ──

enum class AgentJobKind { final_review, course_research, notice_workflow, UNKNOWN }
enum class AgentRunStatus { QUEUED, RUNNING, AWAITING_APPROVAL, SUCCEEDED, PARTIAL, FAILED, CANCELLED, UNKNOWN }
enum class AgentRunPhase {
    CONTEXT_BUILDING, WAITING_FOR_MODEL, VALIDATING_OUTPUT,
    WAITING_FOR_TOOL, WAITING_FOR_APPROVAL, PERSISTING_RESULT,
    RECOVERY_CHECKING, IDLE, UNKNOWN,
}
enum class AgentRiskLevel { AUTO_SAFE, CONFIRM_REQUIRED, MANUAL_ONLY, UNKNOWN }
enum class AgentEventType {
    RUN_QUEUED, RUN_STARTED, CONTEXT_READY, MODEL_STARTED, MODEL_COMPLETED,
    MODEL_FALLBACK, TOOL_STARTED, TOOL_COMPLETED, TOOL_FAILED,
    APPROVAL_REQUIRED, APPROVAL_RESOLVED, ARTIFACT_CREATED,
    RUN_PARTIAL, RUN_COMPLETED, RUN_FAILED, RUN_CANCELLED, UNKNOWN,
}
enum class AgentApprovalStatus { PENDING, APPROVED, REJECTED, EXPIRED, UNKNOWN }
enum class AgentArtifactType {
    FINAL_REVIEW_PLAN, DAILY_AGENDA, NOTICE_CHECKLIST,
    COURSE_RESEARCH_REPORT, CITATION_BUNDLE, UNKNOWN,
}
enum class AgentErrorCode {
    AGENT_INVALID_STATE, AGENT_PERMISSION_DENIED, AGENT_TOOL_REJECTED,
    AGENT_APPROVAL_REQUIRED, AGENT_PROVIDER_UNAVAILABLE, AGENT_CONTEXT_EXPIRED,
    AGENT_IDEMPOTENCY_CONFLICT, AGENT_RUN_NOT_FOUND, AGENT_RUN_CANCELLED,
    AGENT_OUTPUT_SCHEMA_INVALID, AGENT_SOURCE_POLICY_VIOLATION,
    AGENT_ACADEMIC_POLICY_RESTRICTED, UNKNOWN,
}

// ── Runtime DTO ──

data class AgentJobDto(
    @Json(name = "job_id") val jobId: String = "",
    @Json(name = "user_id") val userId: String = "",
    @Json(name = "job_kind") val jobKind: String = "",
    val status: String = "",
    @Json(name = "created_at") val createdAt: String = "",
    @Json(name = "updated_at") val updatedAt: String = "",
    @Json(name = "latest_run_id") val latestRunId: String? = null,
) {
    fun kind(): AgentJobKind = safeEnum(jobKind, AgentJobKind.entries.toTypedArray(), AgentJobKind.UNKNOWN)
    fun runStatus(): AgentRunStatus = safeEnum(status, AgentRunStatus.entries.toTypedArray(), AgentRunStatus.UNKNOWN)
}

data class AgentProgressDto(
    val current: Int = 0,
    val total: Int = 0,
    val percent: Int = 0,
)

data class AgentRunDto(
    @Json(name = "run_id") val runId: String = "",
    @Json(name = "job_id") val jobId: String = "",
    @Json(name = "user_id") val userId: String = "",
    val status: String = "",
    val phase: String = "",
    @Json(name = "risk_level") val riskLevel: String? = null,
    @Json(name = "started_at") val startedAt: String? = null,
    @Json(name = "finished_at") val finishedAt: String? = null,
    @Json(name = "created_at") val createdAt: String = "",
    @Json(name = "updated_at") val updatedAt: String = "",
    val error: String? = null,
    @Json(name = "artifact_ids") val artifactIds: List<String> = emptyList(),
) {
    fun runStatus(): AgentRunStatus = safeEnum(status, AgentRunStatus.entries.toTypedArray(), AgentRunStatus.UNKNOWN)
    fun runPhase(): AgentRunPhase = safeEnum(phase, AgentRunPhase.entries.toTypedArray(), AgentRunPhase.UNKNOWN)
    fun risk(): AgentRiskLevel = safeEnum(riskLevel, AgentRiskLevel.entries.toTypedArray(), AgentRiskLevel.UNKNOWN)
}

data class AgentEventDto(
    val id: String = "",
    val type: String = "",
    @Json(name = "run_id") val runId: String = "",
    val sequence: Long = 0,
    val status: String = "",
    val phase: String = "",
    val role: String? = null,
    val summary: String = "",
    val progress: AgentProgressDto? = null,
    @Json(name = "artifact_id") val artifactId: String? = null,
    @Json(name = "approval_id") val approvalId: String? = null,
    @Json(name = "created_at") val createdAt: String = "",
) {
    fun eventType(): AgentEventType = safeEnum(type, AgentEventType.entries.toTypedArray(), AgentEventType.UNKNOWN)
    fun runStatus(): AgentRunStatus = safeEnum(status, AgentRunStatus.entries.toTypedArray(), AgentRunStatus.UNKNOWN)
    fun runPhase(): AgentRunPhase = safeEnum(phase, AgentRunPhase.entries.toTypedArray(), AgentRunPhase.UNKNOWN)
}

data class AgentApprovalDto(
    @Json(name = "approval_id") val approvalId: String = "",
    @Json(name = "run_id") val runId: String = "",
    val status: String = "",
    @Json(name = "risk_level") val riskLevel: String? = null,
    @Json(name = "action_summary") val actionSummary: String = "",
    @Json(name = "expires_at") val expiresAt: String? = null,
    @Json(name = "resolved_at") val resolvedAt: String? = null,
    @Json(name = "decision_reason") val decisionReason: String? = null,
) {
    fun approvalStatus(): AgentApprovalStatus = safeEnum(status, AgentApprovalStatus.entries.toTypedArray(), AgentApprovalStatus.UNKNOWN)
    fun risk(): AgentRiskLevel = safeEnum(riskLevel, AgentRiskLevel.entries.toTypedArray(), AgentRiskLevel.UNKNOWN)
}

data class AgentArtifactDto(
    @Json(name = "artifact_id") val artifactId: String = "",
    @Json(name = "run_id") val runId: String = "",
    @Json(name = "user_id") val userId: String = "",
    @Json(name = "artifact_type") val artifactType: String = "",
    val version: Int = 1,
    @Json(name = "mime_type") val mimeType: String? = null,
    @Json(name = "size_bytes") val sizeBytes: Long = 0,
    @Json(name = "content_hash") val contentHash: String? = null,
    @Json(name = "download_url") val downloadUrl: String? = null,
    @Json(name = "created_at") val createdAt: String = "",
) {
    fun type(): AgentArtifactType = safeEnum(artifactType, AgentArtifactType.entries.toTypedArray(), AgentArtifactType.UNKNOWN)
}

data class AgentErrorEnvelope(
    val code: String = "",
    val message: String = "",
    @Json(name = "request_id") val requestId: String? = null,
    val details: Map<String, Any?>? = null,
) {
    fun errorCode(): AgentErrorCode = safeEnum(code, AgentErrorCode.entries.toTypedArray(), AgentErrorCode.UNKNOWN)
    companion object {
        val APPROVAL_REQUIRED = AgentErrorCode.AGENT_APPROVAL_REQUIRED.name
        val ACADEMIC_POLICY_RESTRICTED = AgentErrorCode.AGENT_ACADEMIC_POLICY_RESTRICTED.name
        val IDEMPOTENCY_CONFLICT = AgentErrorCode.AGENT_IDEMPOTENCY_CONFLICT.name
    }
}

data class AgentCapabilitiesDto(
    val capabilities: List<String> = emptyList(),
    val version: String = "",
)

// ── Final Review DTO ──

data class FinalReviewCampaignDto(
    @Json(name = "campaign_id") val campaignId: String = "",
    @Json(name = "user_id") val userId: String = "",
    @Json(name = "course_ids") val courseIds: List<String> = emptyList(),
    @Json(name = "exam_ids") val examIds: List<String> = emptyList(),
    @Json(name = "daily_capacity_minutes") val dailyCapacityMinutes: Int = 120,
    val status: String = "",
    @Json(name = "active_version") val currentPlanVersion: Int? = null,
    @Json(name = "created_at") val createdAt: String = "",
    @Json(name = "updated_at") val updatedAt: String = "",
)

data class FinalReviewPlanVersionDto(
    val version: Int = 1,
    @Json(name = "campaign_id") val campaignId: String = "",
    val status: String = "",
    @Json(name = "created_at") val createdAt: String = "",
    @Json(name = "activated_at") val activatedAt: String? = null,
    val summary: String = "",
    @Json(name = "total_items") val totalItems: Int = 0,
)

data class FinalReviewPlanGenerateDto(
    @Json(name = "run_id") val runId: String = "",
    val version: Int = 0,
    @Json(name = "risk_level") val riskLevel: String = "",
    @Json(name = "requires_approval") val requiresApproval: Boolean = false,
    @Json(name = "approval_id") val approvalId: String? = null,
)

data class FinalReviewActivateRequest(val version: Int)

data class FinalReviewCompleteItemRequest(
    val difficulty: String? = null,
    val feedback: String? = null,
)

data class FinalReviewDailyItemDto(
    @Json(name = "item_id") val itemId: String = "",
    val date: String = "",
    val title: String = "",
    val description: String = "",
    @Json(name = "estimated_minutes") val estimatedMinutes: Int = 0,
    val status: String = "",
    @Json(name = "course_name") val courseName: String? = null,
    @Json(name = "plan_version") val planVersion: Int = 1,
)

data class FinalReviewDailyAgendaDto(
    @Json(name = "agenda_date") val date: String = "",
    val items: List<FinalReviewDailyItemDto> = emptyList(),
    @Json(name = "total_minutes") val totalMinutes: Int = 0,
)

data class FinalReviewAdjustmentProposalDto(
    @Json(name = "proposal_id") val proposalId: String = "",
    @Json(name = "campaign_id") val campaignId: String = "",
    val summary: String = "",
    @Json(name = "risk_level") val riskLevel: String = "",
    val status: String = "",
    val rationale: String = "",
    @Json(name = "created_at") val createdAt: String = "",
) {
    fun risk(): AgentRiskLevel = safeEnum(riskLevel, AgentRiskLevel.entries.toTypedArray(), AgentRiskLevel.UNKNOWN)
}

data class FinalReviewDailyCheckinRequest(
    val date: String,
    @Json(name = "completed_item_ids") val completedItemIds: List<String> = emptyList(),
    @Json(name = "self_report") val selfReport: String? = null,
    @Json(name = "difficulty") val difficulty: String? = null,
)

data class FinalReviewEvidenceRequest(
    @Json(name = "item_id") val itemId: String,
    @Json(name = "session_id") val sessionId: String? = null,
    @Json(name = "self_report") val selfReport: String? = null,
    @Json(name = "completed") val completed: Boolean = true,
)

data class FinalReviewCampaignCreateRequest(
    @Json(name = "course_ids") val courseIds: List<String>,
    @Json(name = "exam_ids") val examIds: List<String>,
    @Json(name = "daily_capacity_minutes") val dailyCapacityMinutes: Int = 120,
    @Json(name = "preferred_periods") val preferredPeriods: List<String> = emptyList(),
    @Json(name = "rest_days") val restDays: List<String> = emptyList(),
    val intensity: String = "medium",
)

// ── Course Research DTO ──

enum class AcademicPolicy { ALLOWED, LIMITED, EXAM_RESTRICTED, AI_PROHIBITED, UNKNOWN }
enum class AssistanceMode { HINT, EXPLAIN, REVIEW, FULL_SOLUTION, UNKNOWN }
enum class CitationStatus { VERIFIED, UNVERIFIED, CONFLICT, UNAVAILABLE, UNKNOWN }

data class SourcePolicyDto(
    @Json(name = "course_material_priority") val courseMaterialPriority: Boolean = true,
    @Json(name = "allow_web") val allowWeb: Boolean = true,
    @Json(name = "allow_user_upload") val allowUserUpload: Boolean = true,
)

data class CourseResearchRunDto(
    @Json(name = "run_id") val runId: String = "",
    @Json(name = "job_id") val jobId: String = "",
    val question: String = "",
    val mode: String = "",
    @Json(name = "academic_policy") val academicPolicy: String = "",
    @Json(name = "source_policy") val sourcePolicy: SourcePolicyDto? = null,
    val status: String = "",
    val phase: String = "",
    @Json(name = "risk_level") val riskLevel: String? = null,
    @Json(name = "created_at") val createdAt: String = "",
    @Json(name = "updated_at") val updatedAt: String = "",
    @Json(name = "artifact_ids") val artifactIds: List<String> = emptyList(),
) {
    fun runStatus(): AgentRunStatus = safeEnum(status, AgentRunStatus.entries.toTypedArray(), AgentRunStatus.UNKNOWN)
    fun policy(): AcademicPolicy = safeEnum(academicPolicy, AcademicPolicy.entries.toTypedArray(), AcademicPolicy.UNKNOWN)
    fun assistance(): AssistanceMode = safeEnum(mode, AssistanceMode.entries.toTypedArray(), AssistanceMode.UNKNOWN)
    fun risk(): AgentRiskLevel = safeEnum(riskLevel, AgentRiskLevel.entries.toTypedArray(), AgentRiskLevel.UNKNOWN)
}

data class CourseResearchRoleProgressDto(
    val role: String = "",
    val status: String = "",
    val summary: String = "",
    val progress: AgentProgressDto? = null,
)

data class CourseResearchCitationDto(
    @Json(name = "citation_id") val citationId: String = "",
    val source: String = "",
    val url: String? = null,
    val status: String = "",
    @Json(name = "verified_at") val verifiedAt: String? = null,
    val note: String? = null,
) {
    fun citationStatus(): CitationStatus = safeEnum(status, CitationStatus.entries.toTypedArray(), CitationStatus.UNKNOWN)
}

data class CourseResearchRunCreateRequest(
    val question: String,
    @Json(name = "assistance_mode") val mode: String = "EXPLAIN",
    @Json(name = "academic_policy") val academicPolicy: String = "LIMITED",
    @Json(name = "source_policy") val sourcePolicy: SourcePolicyDto = SourcePolicyDto(),
    @Json(name = "course_id") val courseId: String? = null,
)

// ── Notice Workflow DTO ──

enum class NoticeWorkflowStatus { CREATED, ANALYZING, WAITING_CONFIRMATION, PROCESSING, COMPLETED, EXPIRED, FAILED, UNKNOWN }
enum class NoticeActionStatus { PROPOSED, APPROVED, REJECTED, EXECUTING, DONE, FAILED, EXPIRED, UNKNOWN }

data class NotificationSourceDto(
    @Json(name = "source_id") val sourceId: String = "",
    val code: String = "",
    @Json(name = "display_name") val name: String = "",
    @Json(name = "automation_enabled") val enabled: Boolean = false,
    @Json(name = "permission_scope") val permissionScope: String? = null,
)

data class NotificationSourcePatchRequest(
    @Json(name = "automation_enabled") val enabled: Boolean? = null,
    @Json(name = "display_name") val displayName: String? = null,
)

data class NoticeWorkflowActionDto(
    @Json(name = "action_id") val actionId: String = "",
    @Json(name = "workflow_id") val workflowId: String = "",
    @Json(name = "action_type") val actionType: String = "",
    @Json(name = "risk_level") val riskLevel: String = "",
    val status: String = "",
    val summary: String = "",
    val confidence: Double = 0.0,
    val evidence: String = "",
    @Json(name = "external_url") val externalUrl: String? = null,
    @Json(name = "created_at") val createdAt: String = "",
) {
    fun risk(): AgentRiskLevel = safeEnum(riskLevel, AgentRiskLevel.entries.toTypedArray(), AgentRiskLevel.UNKNOWN)
    fun actionStatus(): NoticeActionStatus = safeEnum(status, NoticeActionStatus.entries.toTypedArray(), NoticeActionStatus.UNKNOWN)
}

data class NoticeWorkflowDto(
    @Json(name = "workflow_id") val workflowId: String = "",
    @Json(name = "notice_id") val noticeId: String = "",
    val status: String = "",
    val summary: String = "",
    val actions: List<NoticeWorkflowActionDto> = emptyList(),
    @Json(name = "created_at") val createdAt: String = "",
    @Json(name = "updated_at") val updatedAt: String = "",
) {
    fun workflowStatus(): NoticeWorkflowStatus = safeEnum(status, NoticeWorkflowStatus.entries.toTypedArray(), NoticeWorkflowStatus.UNKNOWN)
}

data class NoticeManualCreateRequest(
    val title: String,
    val content: String,
    @Json(name = "source_name") val sourceName: String = "manual_input",
)

data class NoticeManualResponseDto(
    @Json(name = "notice_id") val noticeId: String = "",
    val title: String = "",
    val content: String = "",
    val source: String = "",
)

data class NoticeWorkflowCreateRequest(
    @Json(name = "idempotency_key") val idempotencyKey: String? = null,
)

data class ApprovalDecisionRequest(
    val decision: String,
    @Json(name = "reason") val decisionReason: String? = null,
)

data class CourseResearchArtifactBundleDto(
    @Json(name = "run_id") val runId: String = "",
    val artifacts: List<AgentArtifactDto> = emptyList(),
)

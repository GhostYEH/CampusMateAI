package com.example.campusai.data.remote

import com.example.campusai.data.model.ExtractResult
import com.example.campusai.data.remote.agent.AgentArtifactDto
import com.example.campusai.data.remote.agent.AgentApprovalDto
import com.example.campusai.data.remote.agent.AgentCapabilitiesDto
import com.example.campusai.data.remote.agent.AgentEventDto
import com.example.campusai.data.remote.agent.AgentJobDto
import com.example.campusai.data.remote.agent.AgentRunDto
import com.example.campusai.data.remote.agent.StudentGoalCreateRequest
import com.example.campusai.data.remote.agent.StudentGoalCreateResultDto
import com.example.campusai.data.remote.agent.StudentGoalPageDto
import com.example.campusai.data.remote.agent.LearningPlanSummaryDto
import com.example.campusai.data.remote.agent.AdaptiveInterventionOutcomeDto
import com.example.campusai.data.remote.agent.AdaptiveInterventionPageDto
import com.example.campusai.data.remote.agent.DataSourceControlDto
import com.example.campusai.data.remote.agent.DataSourceControlListDto
import com.example.campusai.data.remote.agent.ForecastPageDto
import com.example.campusai.data.remote.agent.LearnerStateSnapshotPageDto
import com.example.campusai.data.remote.agent.ModelTransparencyDto
import com.example.campusai.data.remote.agent.ApprovalDecisionRequest
import com.example.campusai.data.remote.agent.CourseResearchArtifactBundleDto
import com.example.campusai.data.remote.agent.CourseResearchRunCreateRequest
import com.example.campusai.data.remote.agent.CourseResearchRunDto
import com.example.campusai.data.remote.agent.FinalReviewAdjustmentProposalDto
import com.example.campusai.data.remote.agent.FinalReviewActivateRequest
import com.example.campusai.data.remote.agent.FinalReviewCampaignCreateRequest
import com.example.campusai.data.remote.agent.FinalReviewCampaignDto
import com.example.campusai.data.remote.agent.FinalReviewDailyAgendaDto
import com.example.campusai.data.remote.agent.FinalReviewDailyCheckinRequest
import com.example.campusai.data.remote.agent.FinalReviewCompleteItemRequest
import com.example.campusai.data.remote.agent.FinalReviewEvidenceRequest
import com.example.campusai.data.remote.agent.FinalReviewPlanVersionDto
import com.example.campusai.data.remote.agent.FinalReviewPlanGenerateDto
import com.example.campusai.data.remote.agent.NoticeManualCreateRequest
import com.example.campusai.data.remote.agent.NoticeManualResponseDto
import com.example.campusai.data.remote.agent.NoticeWorkflowActionDto
import com.example.campusai.data.remote.agent.NoticeWorkflowCreateRequest
import com.example.campusai.data.remote.agent.NoticeWorkflowDto
import com.example.campusai.data.remote.agent.NotificationSourceDto
import com.example.campusai.data.remote.agent.NotificationSourcePatchRequest
import com.squareup.moshi.Json
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.*

data class LoginRequest(val username: String, val password: String)
data class LoginResponse(val access_token: String, val refresh_token: String)
data class RefreshRequest(val refresh_token: String)
data class ExpressionSignalRequest(
    val label: String,
    val confidence: Double,
    val is_stable: Boolean,
    val timestamp: Long,
    val model_version: String,
)
data class ChatRequest(
    val message: String,
    val session_id: String = "android-session",
    val stream: Boolean = false,
    @Json(name = "course_id") val course_id: String? = null,
    val expression_signal: ExpressionSignalRequest? = null,
)
data class ChatResponse(val answer: String? = null, val message: String? = null)
data class FocusAiAskRequest(val text: String)
data class FocusAiAskResponse(val answer: String)
data class FocusRealtimeVoiceSessionDto(
    val session_id: String,
    val websocket_path: String,
)
data class FocusRealtimeVoiceStopDto(val session_id: String, val stopped: Boolean)
data class ExpressionContributionResponse(
    val sample_id: String,
    val label: String,
    val status: String,
    val message: String,
)
data class NoticeExtractRequest(
    val content: String,
    val published_at: String? = null,
    val source_name: String? = null,
    val allow_multi_task: Boolean = true,
)
data class NoticeExtractTaskDto(
    val title: String = "",
    val task: String = "",
    val actionable: Boolean = false,
    val deadline: String? = null,
    val source_name: String? = null,
    val confidence: Double = 0.0,
)
data class MultiNoticeExtractResponseDto(
    val tasks: List<NoticeExtractTaskDto> = emptyList(),
    val split_reason: String = "",
    val needs_user_confirmation: Boolean = false,
) {
    fun toExtractResult(): com.example.campusai.data.model.ExtractResult {
        val first = tasks.firstOrNull()
        return com.example.campusai.data.model.ExtractResult(
            title = first?.title.orEmpty(),
            source = first?.source_name.orEmpty(),
            deadline = first?.deadline.orEmpty(),
            tasks = tasks.map { it.task.ifBlank { it.title } }.filter { it.isNotBlank() },
            confidence = tasks.maxOfOrNull { it.confidence } ?: 0.0,
        )
    }
}
data class NoticeIngestRequest(
    val content: String,
    val source_name: String,
    val published_at: String
)
data class ChaoxingLoginRequest(
    val username: String,
    val password: String
)

data class ChaoxingSyncStatusResponse(
    val status: String, // "online" or "offline"
    val last_synced_at: String?,
    val source: String? = null,
    val courses: Int = 0,
    val teachers: Int = 0,
    val pending_assignments: Int = 0,
    val notices: Int = 0,
)
data class NoticeBatchMessageRequest(val text: String, val published_at: String?)
data class NoticeBatchItemRequest(
    val client_id: String,
    val client_fingerprint: String,
    val source_name: String,
    val published_at: String?,
    val messages: List<NoticeBatchMessageRequest>,
)
data class NoticeBatchIngestRequest(val items: List<NoticeBatchItemRequest>)
data class NoticeBatchItemResponse(
    val client_id: String,
    val client_fingerprint: String,
    val status: String,
    val semantic_type: String,
    val duplicate: Boolean = false,
    val reason: String? = null,
)
data class NoticeBatchIngestResponse(val items: List<NoticeBatchItemResponse> = emptyList())

data class HealthResponse(val mode: String? = null)
data class KnowledgeStatusResponse(
    val mode: String? = null,
    val document_count: Int? = null,
    val index_ready: Boolean? = null,
)
data class MeResponse(val user: UserResponse? = null)
data class UserResponse(
    val id: String? = null,
    val username: String? = null,
    val role: String? = null,
    val display_name: String? = null,
    val student_number: String? = null,
    val college: String? = null,
    val major: String? = null,
    val grade: String? = null,
    val avatar_url: String? = null,
    val university_id: String? = null,
)

data class UniversityDto(
    val id: String,
    val name: String,
    val short_name: String? = null,
    val province: String? = null,
    val city: String? = null,
    val academic_provider: String = "unsupported",
    val forum_enabled: Boolean = true,
    val is_demo: Boolean = false,
)
data class UniversitySelectionRequest(val university_id: String)
data class UniversitySelectionResponse(val university_id: String?, val university: UniversityDto?)

data class CommunityPostDto(
    val id: String,
    val title: String,
    val content: String,
    val category: String = "campus",
    val author_id: String? = null,
    val author_name: String = "校园同学",
    val is_anonymous: Boolean = false,
    val images: List<String> = emptyList(),
    val extra: Map<String, Any?>? = null,
    val status: String = "published",
    val like_count: Int = 0,
    val comment_count: Int = 0,
    val favorite_count: Int = 0,
    val view_count: Int = 0,
    val liked: Boolean = false,
    val favorited: Boolean = false,
    val is_owner: Boolean = false,
    val created_at: String = "",
    val updated_at: String? = null,
)
data class CommunityPostCreateRequest(
    val title: String,
    val content: String,
    val category: String = "campus",
    val images: List<String> = emptyList(),
    val is_anonymous: Boolean = false,
    val extra: Map<String, Any?>? = null,
)
data class CommunityPostUpdateRequest(
    val title: String? = null,
    val content: String? = null,
    val category: String? = null,
    val images: List<String>? = null,
    val is_anonymous: Boolean? = null,
    val extra: Map<String, Any?>? = null,
)
data class CommentDto(
    val id: String,
    val post_id: String = "",
    val author_id: String? = null,
    val author_name: String = "校园同学",
    val parent_comment_id: String? = null,
    val content: String,
    val is_anonymous: Boolean = false,
    val status: String = "published",
    val created_at: String = "",
)
data class CommentCreateRequest(
    val content: String,
    val parent_comment_id: String? = null,
    val is_anonymous: Boolean = false,
)
data class CategoryMetaDto(
    val key: String,
    val label: String,
    val description: String = "",
    val icon: String = "",
    val color: String = "",
)
data class CommunityReportRequest(
    val target_type: String,
    val target_id: String,
    val reason: String,
    val details: String? = null,
)
data class UploadImageResponse(
    val url: String,
    val filename: String = "",
    val size: Int = 0,
)
data class AcademicStatusDto(
    val status: String,
    val provider: String,
    val last_synced_at: String? = null,
    val external_student_id: String? = null,
)
data class AcademicProviderDto(
    val university_id: String,
    val provider: String,
    val status: String,
    val supports: List<String> = emptyList(),
)
data class AcademicProvidersResponse(val items: List<AcademicProviderDto> = emptyList())
data class AcademicBindRequest(val username: String, val password: String)

// ===== CampusMate EduConnector =====
data class EduDetectResult(
    val university_id: String,
    val provider: String,
    val system_type: String,
    val detected: Boolean,
    val confidence: Double = 0.0,
    val evidence: List<Map<String, Any>> = emptyList(),
    val detection_source: String = "UNKNOWN",
    val reason: String? = null,
)
data class EduSystemConfigDto(
    val id: String,
    val university_id: String,
    val provider: String,
    val system_type: String,
    val academic_system_url: String? = null,
    val academic_system_url_status: String = "not_discovered",
    val sso_url: String? = null,
    val cas_url: String? = null,
    val webvpn_url: String? = null,
    val login_method: String = "unknown",
    val captcha_type: String = "unknown",
    val requires_campus_network: Boolean? = null,
    val supported_features: List<String> = emptyList(),
    val school_code: String? = null,
    val data_source: String = "unknown",
)
data class EduBindingDto(
    val id: String,
    val user_id: String,
    val edu_system_id: String? = null,
    val university_id: String,
    val provider: String,
    val supported_features: List<String> = emptyList(),
    val system_type: String = "undergrad",
    val external_student_id: String? = null,
    val external_student_name: String? = null,
    val connection_status: String = "unbound",
    val session_type: String? = null,
    val last_authenticated_at: String? = null,
    val session_expires_at: String? = null,
    val last_synced_at: String? = null,
    val last_sync_status: String? = null,
    val last_error: String? = null,
)
data class EduBindRequest(val username: String, val password: String, val system_type: String = "undergrad")
data class EduProfile(
    val external_student_id: String? = null,
    val name: String? = null,
    val gender: String? = null,
    val college: String? = null,
    val major: String? = null,
    val grade: String? = null,
    val class_name: String? = null,
    val enrollment_year: String? = null,
    val schooling_length: String? = null,
)
data class EduScheduleItem(
    val course_name: String? = null,
    val course_code: String? = null,
    val teacher: String? = null,
    val location: String? = null,
    val weekday: Int? = null,
    val start_section: Int? = null,
    val end_section: Int? = null,
    val start_time: String? = null,
    val end_time: String? = null,
    val weeks: String? = null,
    val semester: String? = null,
)
data class EduSchedule(val semester: String? = null, val items: List<EduScheduleItem> = emptyList())
data class EduGradeItem(
    val course_name: String? = null,
    val course_code: String? = null,
    val credit: Double? = null,
    val score: String? = null,
    val grade_point: Double? = null,
    val semester: String? = null,
    val category: String? = null,
    val status: String? = null,
)
data class EduGrade(val semester: String? = null, val gpa: Double? = null, val items: List<EduGradeItem> = emptyList())
data class EduExamItem(
    val course_name: String? = null,
    val course_code: String? = null,
    val exam_type: String? = null,
    val location: String? = null,
    val seat: String? = null,
    val starts_at: String? = null,
    val ends_at: String? = null,
    val semester: String? = null,
    val notes: String? = null,
)
data class EduExam(val semester: String? = null, val items: List<EduExamItem> = emptyList())
data class EduSyncResult(
    val sync_type: String,
    val status: String,
    val items_count: Int = 0,
    val error_message: String? = null,
    val profile: EduProfile? = null,
    val schedule: EduSchedule? = null,
    val grade: EduGrade? = null,
    val exam: EduExam? = null,
    val persisted: Boolean = false,
    val inserted: Int = 0,
    val updated: Int = 0,
    val unchanged: Int = 0,
    val removed: Int = 0,
    val failed: Int = 0,
    val sync_batch_id: String? = null,
    val semester: String? = null,
    val stage: String? = null,
    val previous_schedule_preserved: Boolean? = null,
    val requires_user_action: String? = null,
    val protocol_source: String? = null,
)
data class EduSyncRecord(
    val id: String,
    val binding_id: String,
    val sync_type: String,
    val status: String,
    val items_count: Int = 0,
    val error_message: String? = null,
    val started_at: String,
    val finished_at: String? = null,
)

// ===== EduConnection 状态机（client_webview 登录流程） =====
data class EduConnectionDto(
    val id: String,
    val user_id: String = "",
    val edu_system_id: String = "",
    val university_id: String = "",
    val state: String = "idle",
    val provider: String = "unknown",
    val login_execution_mode: String = "unsupported",
    val portal_url: String? = null,
    val allowed_origins: List<String> = emptyList(),
    val external_student_id: String? = null,
    val external_student_name: String? = null,
    val error_code: String? = null,
    val error_message: String? = null,
    val created_at: String = "",
    val updated_at: String = "",
)

data class EduProbeRequest(val portal_url: String)
data class EduProbeResult(
    val portal_url: String,
    val provider: String = "unknown",
    val provider_confidence: Double = 0.0,
    val reachable: Boolean = false,
    val http_status: Int? = null,
    val final_url: String? = null,
    val title: String? = null,
    val is_edu_page: Boolean = false,
    val suggested_login_mode: String = "backend_http",
    val evidence: List<Map<String, Any>> = emptyList(),
    val error: String? = null,
)

data class EduConnectionFromUrlRequest(
    val portal_url: String,
    val university_id: String? = null,
)

data class EduConnectionContinueRequest(
    val username: String? = null,
    val password: String? = null,
    val captcha: String? = null,
    val sms_code: String? = null,
    val mfa_code: String? = null,
    val action: String? = null,
    val cookies: Map<String, String>? = null,
    val cookie_jar: List<EduCookieDto>? = null,
    val current_url: String? = null,
    val user_agent: String? = null,
    val pre_login_token: String? = null,
)

data class EduPreLoginResult(
    val pre_login_token: String = "",
    val captcha_required: Boolean = false,
    val captcha_type: String = "none",
    val captcha_image_base64: String? = null,
    val captcha_image_url: String? = null,
    val expires_at: String = "",
)

data class EduScheduleItemsResponse(
    val semester: String? = null,
    val items_count: Int = 0,
    val items: List<EduScheduleItemDto> = emptyList(),
)
data class EduScheduleItemDto(
    val id: String? = null,
    val semester: String? = null,
    val course_code: String? = null,
    val course_name: String? = null,
    val teacher: String? = null,
    val teachers: List<String>? = null,
    val location: String? = null,
    val campus: String? = null,
    val building: String? = null,
    val classroom: String? = null,
    val weekday: Int? = null,
    val start_section: Int? = null,
    val end_section: Int? = null,
    val start_time: String? = null,
    val end_time: String? = null,
    val weeks: String? = null,
    val week_text: String? = null,
    val credit: Double? = null,
    val course_nature: String? = null,
    val course_category: String? = null,
    val course_type: String? = null,
    val teaching_class: String? = null,
    val class_name: String? = null,
    val college: String? = null,
    val department: String? = null,
    val assessment_method: String? = null,
    val exam_type: String? = null,
    val total_hours: Double? = null,
    val theory_hours: Double? = null,
    val practice_hours: Double? = null,
    val language: String? = null,
    val note: String? = null,
    val semester_id: String? = null,
    val extra_info: Map<String, Any?>? = null,
    val is_stale: Boolean = false,
    val last_seen_at: String? = null,
)

data class EduGradeItemsResponse(
    val semester: String? = null,
    val items_count: Int = 0,
    val items: List<EduGradeItemDto> = emptyList(),
)
data class EduGradeItemDto(
    val id: String? = null,
    val semester: String? = null,
    val course_code: String? = null,
    val course_name: String? = null,
    val credit: Double? = null,
    val score: String? = null,
    val grade_point: Double? = null,
    val category: String? = null,
    val status: String? = null,
    val is_stale: Boolean = false,
    val last_seen_at: String? = null,
)
data class EduExamItemsResponse(
    val semester: String? = null,
    val items_count: Int = 0,
    val items: List<EduExamItemDto> = emptyList(),
)
data class EduExamItemDto(
    val id: String? = null,
    val semester: String? = null,
    val course_code: String? = null,
    val course_name: String? = null,
    val exam_type: String? = null,
    val location: String? = null,
    val seat: String? = null,
    val starts_at: String? = null,
    val ends_at: String? = null,
    val notes: String? = null,
    val is_stale: Boolean = false,
    val last_seen_at: String? = null,
)

/** 通用分页响应，对应后端 Page。 */
data class PagedResponse<T>(
    val items: List<T> = emptyList(),
    val total: Int = 0,
    val page: Int = 1,
    val page_size: Int = 20,
    val has_more: Boolean = false,
)

// ── 校园通知 ──
data class NoticeDto(
    val id: String,
    val title: String,
    val source: String? = null,
    val time: String? = null,
    val unread: Boolean = false,
    val category: String? = null,
    val content: String? = null,
)

// ── 课程 ──
data class CourseDto(
    val id: String,
    val name: String,
    val code: String? = null,
    val semester: String? = null,
    val description: String? = null,
    val teacher_id: String? = null,
    val teacher_name: String? = null,
    val status: String? = null,
    val provider: String? = null,
    val external_id: String? = null,
    val source_url: String? = null,
    val last_synced_at: String? = null
)

data class CourseContentItemDto(
    val id: String,
    val external_id: String,
    val kind: String,
    val title: String,
    val parent_external_id: String? = null,
    val description: String? = null,
    val author_name: String? = null,
    val status: String = "unknown",
    val deadline: String? = null,
    val published_at: String? = null,
    val mime_type: String? = null,
    val cached: Boolean = false,
    val can_download: Boolean = false,
    val can_open: Boolean = true,
)

data class CourseSectionStatusDto(
    val section: String,
    val status: String,
    val item_count: Int = 0,
    val last_synced_at: String? = null,
    val error_code: String? = null,
)

data class CourseContentSummaryDto(
    val course_id: String,
    val provider: String? = null,
    val cover_url: String? = null,
    val teacher_name: String? = null,
    val school_name: String? = null,
    val class_name: String? = null,
    val student_count: Int? = null,
    val sections: List<CourseSectionStatusDto> = emptyList(),
)

data class CourseContentPageDto(
    val items: List<CourseContentItemDto> = emptyList(),
    val total: Int = 0,
    val page: Int = 1,
    val page_size: Int = 100,
    val has_more: Boolean = false,
)

data class CourseResourceOpenDto(val url: String? = null, val mode: String? = null)

// ── 交互课堂（生成与运行都经 CampusMate 后端；客户端绝不持有 OpenMAIC 凭据）──
//
// 注意：DTO 里**永远**不出现 ACCESS_CODE / Cookie / Token / Provider Key。
// 课堂地址只有通过 ClassroomUrlPolicy 校验后才会被打开。
data class InteractiveClassroomItemDto(
    @Json(name = "url") val url: String? = null,
    @Json(name = "session_id") val sessionId: String? = null,
    @Json(name = "classroom_id") val classroomId: String? = null,
    @Json(name = "mode") val mode: String? = null,
    @Json(name = "scenes_count") val scenesCount: Int? = null,
    @Json(name = "created_at") val createdAt: String? = null,
    /** 无法打开时的原因（未配置公开课堂地址 / 缺少可信课堂标识）。 */
    @Json(name = "url_unavailable_reason") val urlUnavailableReason: String? = null,
)

data class InteractiveClassroomDto(
    @Json(name = "enabled") val enabled: Boolean = false,
    @Json(name = "items") val items: List<InteractiveClassroomItemDto> = emptyList(),
) {
    fun existingClassroomUrls(): List<String> = if (enabled) items.mapNotNull { it.url } else emptyList()
}

/** 服务状态：configured/available/unavailable/incompatible/degraded 必须可区分。 */
data class InteractiveClassroomStatusDto(
    @Json(name = "enabled") val enabled: Boolean = false,
    @Json(name = "configured") val configured: Boolean = false,
    @Json(name = "available") val available: Boolean = false,
    @Json(name = "unavailable") val unavailable: Boolean = false,
    @Json(name = "incompatible") val incompatible: Boolean = false,
    @Json(name = "degraded") val degraded: Boolean = false,
    @Json(name = "compatibility") val compatibility: String? = null,
    @Json(name = "version") val version: String? = null,
    @Json(name = "capabilities") val capabilities: Map<String, Boolean> = emptyMap(),
    @Json(name = "unavailable_capabilities") val unavailableCapabilities: List<String> = emptyList(),
    @Json(name = "embed_origin") val embedOrigin: String? = null,
    @Json(name = "browser_embed_available") val browserEmbedAvailable: Boolean = false,
    @Json(name = "browser_embed_reason") val browserEmbedReason: String? = null,
    @Json(name = "external_3d_available") val external3dAvailable: Boolean = true,
    @Json(name = "poll_interval_ms") val pollIntervalMs: Int = 5000,
    @Json(name = "reason") val reason: String? = null,
)

data class InteractiveClassroomMaterialDto(
    @Json(name = "id") val id: String,
    @Json(name = "title") val title: String,
    @Json(name = "kind") val kind: String? = null,
)

/** 生成**之前**的计划（只读，不创建任何任务）。 */
data class InteractiveClassroomPlanDto(
    @Json(name = "course_id") val courseId: String,
    @Json(name = "course_name") val courseName: String? = null,
    @Json(name = "mode") val mode: String = "adaptive",
    @Json(name = "mode_label") val modeLabel: String? = null,
    @Json(name = "requested_mode") val requestedMode: String? = null,
    @Json(name = "adaptive_reason") val adaptiveReason: String? = null,
    @Json(name = "intent_note") val intentNote: String? = null,
    @Json(name = "materials") val materials: List<InteractiveClassroomMaterialDto> = emptyList(),
    @Json(name = "context_warnings") val contextWarnings: List<String> = emptyList(),
    @Json(name = "can_generate") val canGenerate: Boolean = false,
    @Json(name = "external_3d_available") val external3dAvailable: Boolean = true,
    @Json(name = "reason") val reason: String? = null,
)

data class InteractiveClassroomGenerateRequest(
    @Json(name = "mode") val mode: String = "adaptive",
    @Json(name = "learning_objective") val learningObjective: String? = null,
    @Json(name = "current_difficulty") val currentDifficulty: String? = null,
    @Json(name = "desired_duration_minutes") val desiredDurationMinutes: Int? = null,
    @Json(name = "difficulty_level") val difficultyLevel: String? = null,
    @Json(name = "wants_more_practice") val wantsMorePractice: Boolean = false,
    @Json(name = "selected_material_ids") val selectedMaterialIds: List<String> = emptyList(),
)

data class InteractiveClassroomSessionDto(
    @Json(name = "session_id") val sessionId: String,
    @Json(name = "course_id") val courseId: String? = null,
    @Json(name = "mode") val mode: String? = null,
    @Json(name = "requested_mode") val requestedMode: String? = null,
    @Json(name = "adaptive_reason") val adaptiveReason: String? = null,
    @Json(name = "status") val status: String = "queued",
    @Json(name = "step") val step: String = "queued",
    @Json(name = "progress") val progress: Int = 0,
    @Json(name = "message") val message: String? = null,
    @Json(name = "error") val error: String? = null,
    @Json(name = "error_code") val errorCode: String? = null,
    @Json(name = "url") val url: String? = null,
    /** 无法构造公开地址时的**可操作**原因（未配置公开 Origin / 缺少可信课堂标识）。 */
    @Json(name = "url_unavailable_reason") val urlUnavailableReason: String? = null,
    @Json(name = "scenes_count") val scenesCount: Int? = null,
    @Json(name = "terminal") val terminal: Boolean = false,
    @Json(name = "retryable") val retryable: Boolean = false,
    @Json(name = "partial") val partial: Boolean = false,
    @Json(name = "updated_at") val updatedAt: String? = null,
)

data class InteractiveClassroomGenerateResponse(
    @Json(name = "accepted") val accepted: Boolean = true,
    @Json(name = "session") val session: InteractiveClassroomSessionDto,
    @Json(name = "poll_interval_ms") val pollIntervalMs: Int = 5000,
    @Json(name = "mode") val mode: String? = null,
    @Json(name = "adaptive_reason") val adaptiveReason: String? = null,
    /** 个性化来源：snapshot（原任务快照，权威）/ client_body / legacy_mode_only / request。 */
    @Json(name = "request_source") val requestSource: String? = null,
    @Json(name = "request_source_note") val requestSourceNote: String? = null,
    /** 学生指定但无法解析（不存在 / 已删除 / 越权）的资料 id。 */
    @Json(name = "materials_unresolved") val materialsUnresolved: List<String> = emptyList(),
    @Json(name = "materials_warning") val materialsWarning: String? = null,
)

/** 真实课堂组成（回读统计，绝不根据请求形态推断）。 */
data class InteractiveClassroomCompositionDto(
    @Json(name = "classroom_id") val classroomId: String? = null,
    @Json(name = "scene_total") val sceneTotal: Int = 0,
    @Json(name = "scenes") val scenes: List<InteractiveClassroomSceneCountDto> = emptyList(),
    @Json(name = "widget_types") val widgetTypes: List<InteractiveClassroomWidgetCountDto> = emptyList(),
    @Json(name = "has_whiteboard") val hasWhiteboard: Boolean = false,
    @Json(name = "has_tts") val hasTts: Boolean = false,
    @Json(name = "has_multi_agent") val hasMultiAgent: Boolean = false,
    @Json(name = "requires_external_3d") val requiresExternal3d: Boolean = false,
    @Json(name = "external_3d_available") val external3dAvailable: Boolean = true,
    @Json(name = "degraded") val degraded: Boolean = false,
    @Json(name = "error") val error: String? = null,
)

data class InteractiveClassroomSceneCountDto(
    @Json(name = "type") val type: String,
    @Json(name = "count") val count: Int = 0,
)

data class InteractiveClassroomWidgetCountDto(
    @Json(name = "widget_type") val widgetType: String,
    @Json(name = "count") val count: Int = 0,
)

// ── 课程知识点掌握（学习通课程图谱页观测，非本地推断）──
data class KnowledgePointDto(
    val external_id: String,
    val name: String,
    val tags: List<String> = emptyList(),
    val position: Int = 0,
)

data class CourseKnowledgeGraphDto(
    val course_id: String,
    val available: Boolean = false,
    val synced_at: String? = null,
    val knowledge_point_count: Int = 0,
    val own_mastery_rate: Double? = null,
    val class_mastery_rate: Double? = null,
    val mastery_gap_vs_class: Double? = null,
    val own_completion_rate: Double? = null,
    val class_completion_rate: Double? = null,
    val tags: List<String> = emptyList(),
    val points: List<KnowledgePointDto> = emptyList(),
)

// 全校活动列表（校园动态 / 我的活动）
data class ActivityDto(
    val id: String,
    val author_id: String? = null,
    val author_name: String? = null,
    val title: String,
    val summary: String? = null,
    val content: String? = null,
    val category: String? = null,
    val location: String? = null,
    val registration_deadline: String? = null,
    val starts_at: String? = null,
    val ends_at: String? = null,
    val capacity: Int? = null,
    val status: String? = null,
    val published_at: String? = null,
    val created_at: String? = null,
    val updated_at: String? = null,
)

// ── 个人待办（云端） ──
data class PersonalTaskDto(
    val id: String,
    val user_id: String? = null,
    val title: String,
    val description: String? = null,
    val deadline: String? = null,
    val source_name: String? = null,
    val source_text: String? = null,
    val priority: String? = null,
    val importance: String? = null,
    val status: String? = null,
    val created_at: String? = null,
    val updated_at: String? = null,
)

data class ImportanceRankRequest(val task_ids: List<String>? = null)
data class ImportanceRankItemDto(val task_id: String = "", val importance: String = "unknown", val reason: String? = null, val mode: String = "rules")
data class ImportanceRankResponseDto(val updated: List<ImportanceRankItemDto> = emptyList(), val skipped: List<String> = emptyList(), val mode: String = "rules", val total: Int = 0)

data class PersonalTaskCreateRequest(
    val title: String,
    val description: String? = null,
    val deadline: String? = null,
    val source_name: String? = null,
    val source_text: String? = null,
    val priority: String = "medium",
    val materials: List<String>? = null,
    val submission_method: String? = null,
    val location: String? = null,
    val importance: String? = "unknown",
)

data class PersonalTaskUpdateRequest(
    val title: String? = null,
    val description: String? = null,
    val deadline: String? = null,
    val source_name: String? = null,
)

data class TaskImportAnalyzeRequest(val content: String, val source_name: String? = null)
data class TaskImportDraftDto(
    val title: String,
    val description: String? = null,
    val deadline: String? = null,
    val source_name: String? = null,
    val source_text: String? = null,
    val priority: String = "medium",
    val importance: String = "unknown",
    val confidence: Double = 1.0,
    val materials: List<String> = emptyList(),
    val submission_method: String? = null,
    val location: String? = null,
    val needs_confirmation: Boolean = false,
    val warnings: List<String> = emptyList(),
    val selected: Boolean = true,
    val existing_task_id: String? = null,
    val existing_status: String? = null,
)
data class TaskImportAnalyzeResponse(
    val mode: String,
    val split_reason: String = "",
    val needs_user_confirmation: Boolean = false,
    val tasks: List<TaskImportDraftDto> = emptyList(),
)
data class TaskImportCommitRequest(val tasks: List<PersonalTaskCreateRequest>)
data class TaskImportExistingDto(val task_id: String, val title: String, val status: String)
data class TaskImportCommitResponse(
    val created: List<PersonalTaskDto> = emptyList(),
    val skipped_existing: List<TaskImportExistingDto> = emptyList(),
)

data class StudySessionDto(
    val id: String,
    val user_id: String,
    val mode: String,
    val experience_mode: String = "QUIET",
    val goal: String? = null,
    val related_task_id: String? = null,
    val started_at: String,
    val paused_at: String? = null,
    val ended_at: String? = null,
    val planned_duration_seconds: Int = 0,
    val duration_seconds: Int = 0,
    val pause_seconds: Int = 0,
    val status: String,
    val behavior_summary: StudyBehaviorSummaryDto? = null,
)

data class StudySessionCreateRequest(
    val mode: String,
    val experience_mode: String = "QUIET",
    val planned_duration_seconds: Int? = null,
    val goal: String? = null,
    val related_task_id: String? = null,
)

data class StudySessionFinishRequest(
    val self_report: String? = null,
    val self_report_tags: List<String>? = null,
    val behavior_summary: StudyBehaviorSummaryDto? = null,
)

data class StudyBehaviorSummaryDto(
    val observed_seconds: Int,
    val study_seconds: Int,
    val paused_seconds: Int,
    val longest_continuous_study_seconds: Int,
    val meaningful_switch_count: Int,
    val phone_interaction_count: Int,
    val possible_distraction_count: Int,
    val absent_count: Int,
    val reminder_count: Int,
    val model_version: String,
)

data class StudyGoalDto(val target_minutes: Int, val updated_at: String)
data class StudyGoalUpdateRequest(val target_minutes: Int)
data class TaskBreakdownRequest(val task_id: String? = null, val goal: String? = null)
data class TaskBreakdownStepDto(
    val step_number: Int,
    val title: String,
    val description: String,
    val estimated_minutes: Int = 0,
    val dependencies: List<Int> = emptyList(),
    val completion_criteria: String = "完成这一步的产出已确认",
    val is_policy_step: Boolean = false,
    val knowledge_source: String? = null,
    val knowledge_document_id: String? = null,
    val knowledge_status: String? = null,
)
data class TaskBreakdownResponseDto(
    val mode: String,
    val steps: List<TaskBreakdownStepDto> = emptyList(),
    val goal: String,
    val related_task_id: String? = null,
    val related_task_title: String? = null,
    val warnings: List<String> = emptyList(),
)

// ── 个人中心：文件 / 收藏 ──
data class PersonalFileDto(
    val id: String,
    val name: String,
    val category: String? = null,
    val size_label: String? = null,
    val updated_at: String? = null,
    val source: String? = null,
    val is_favorite: Boolean = false,
)

data class PersonalFileCreateRequest(
    val name: String,
    val category: String? = null,
    val source: String? = null,
    val size_label: String? = null,
)

data class FileFavoriteToggleRequest(val favorite: Boolean)

data class FavoriteDto(
    val id: String,
    val title: String,
    val type: String? = null,
    val subtitle: String? = null,
    val saved_at: String? = null,
    val source_route: String? = null,
)

data class FavoriteCreateRequest(
    val id: String,
    val title: String,
    val type: String? = null,
    val subtitle: String? = null,
    val saved_at: String? = null,
    val source_route: String? = null,
)

data class HomeBannerDto(
    val id: String,
    val eyebrow: String,
    val title: String,
    val subtitle: String,
    val cta_label: String,
    val image_url: String,
    val action_key: String,
    val theme_key: String,
    val sort_order: Int,
    val status: String,
    val starts_at: String? = null,
    val ends_at: String? = null,
    val created_at: String,
    val updated_at: String,
)

data class HomeBannerFeedDto(
    val items: List<HomeBannerDto>,
    val updated_at: String? = null,
)

interface ApiService {

    @POST("notices/{noticeId}/workflow")
    suspend fun analyzeNoticeWorkflow(@Path("noticeId") noticeId: String): Response<NoticeWorkflowDto>

    @POST("notice-workflows/{workflowId}/confirm")
    suspend fun confirmNoticeWorkflow(@Path("workflowId") workflowId: String, @Body request: Map<String, Boolean>): Response<NoticeWorkflowDto>
    @GET("home-banners")
    suspend fun homeBanners(): Response<HomeBannerFeedDto>

    @GET("health")
    suspend fun health(): Response<HealthResponse>

    @GET("knowledge/status")
    suspend fun knowledgeStatus(): Response<KnowledgeStatusResponse>

    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): Response<LoginResponse>

    @GET("auth/me")
    suspend fun me(): Response<MeResponse>

    @GET("universities")
    suspend fun listUniversities(
        @Query("q") query: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
    ): Response<PagedResponse<UniversityDto>>

    @PUT("profile/university")
    suspend fun selectUniversity(@Body request: UniversitySelectionRequest): Response<UniversitySelectionResponse>

    @GET("community/posts/categories")
    suspend fun listCommunityCategories(): Response<Map<String, List<CategoryMetaDto>>>

    @GET("community/posts")
    suspend fun listCommunityPosts(
        @Query("q") query: String? = null,
        @Query("category") category: String? = null,
        @Query("sort") sort: String = "time",
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20,
    ): Response<PagedResponse<CommunityPostDto>>

    @POST("community/posts")
    suspend fun createCommunityPost(@Body request: CommunityPostCreateRequest): Response<CommunityPostDto>

    @GET("community/posts/{postId}")
    suspend fun getCommunityPost(@Path("postId") postId: String): Response<CommunityPostDto>

    @PUT("community/posts/{postId}")
    suspend fun updateCommunityPost(@Path("postId") postId: String, @Body request: CommunityPostUpdateRequest): Response<CommunityPostDto>

    @DELETE("community/posts/{postId}")
    suspend fun deleteCommunityPost(@Path("postId") postId: String): Response<CommunityPostDto>

    @POST("community/posts/{postId}/like")
    suspend fun likeCommunityPost(@Path("postId") postId: String): Response<CommunityPostDto>

    @DELETE("community/posts/{postId}/like")
    suspend fun unlikeCommunityPost(@Path("postId") postId: String): Response<CommunityPostDto>

    @POST("community/posts/{postId}/favorite")
    suspend fun favoriteCommunityPost(@Path("postId") postId: String): Response<CommunityPostDto>

    @DELETE("community/posts/{postId}/favorite")
    suspend fun unfavoriteCommunityPost(@Path("postId") postId: String): Response<CommunityPostDto>

    @GET("community/posts/{postId}/comments")
    suspend fun listCommunityComments(@Path("postId") postId: String): Response<PagedResponse<CommentDto>>

    @POST("community/posts/{postId}/comments")
    suspend fun createCommunityComment(@Path("postId") postId: String, @Body request: CommentCreateRequest): Response<CommentDto>

    @POST("community/reports")
    suspend fun reportCommunity(@Body request: CommunityReportRequest): Response<Unit>

    @Multipart
    @POST("community/upload-image")
    suspend fun uploadCommunityImage(@Part image: MultipartBody.Part): Response<UploadImageResponse>

    @GET("academic/status")
    suspend fun academicStatus(): Response<AcademicStatusDto>

    @GET("academic/providers")
    suspend fun academicProviders(): Response<AcademicProvidersResponse>

    @POST("academic/bind")
    suspend fun bindAcademic(@Body request: AcademicBindRequest): Response<AcademicStatusDto>

    @DELETE("academic/binding")
    suspend fun disconnectAcademic(): Response<Unit>

    // ===== CampusMate EduConnector =====
    @GET("edu/detect")
    suspend fun eduDetect(@Query("university_id") universityId: String): Response<EduDetectResult>

    @GET("edu/config/{universityId}")
    suspend fun getEduConfig(@Path("universityId") universityId: String): Response<EduSystemConfigDto>

    @GET("edu/binding")
    suspend fun getEduBinding(): Response<EduBindingDto?>

    @POST("edu/bind")
    suspend fun eduBind(@Body request: EduBindRequest): Response<EduBindingDto>

    @DELETE("edu/binding")
    suspend fun eduUnbind(): Response<Unit>

    @POST("edu/sync/profile")
    suspend fun eduSyncProfile(): Response<EduSyncResult>

    @POST("edu/sync/schedule")
    suspend fun eduSyncSchedule(@Query("semester") semester: String? = null): Response<EduSyncResult>

    @POST("edu/sync/grade")
    suspend fun eduSyncGrade(@Query("semester") semester: String? = null): Response<EduSyncResult>

    @POST("edu/sync/exam")
    suspend fun eduSyncExam(@Query("semester") semester: String? = null): Response<EduSyncResult>

    @GET("edu/sync/records")
    suspend fun getEduSyncRecords(@Query("limit") limit: Int = 20): Response<List<EduSyncRecord>>

    // ===== EduConnection 状态机 =====
    @POST("edu/discovery/probe")
    suspend fun eduProbe(@Body request: EduProbeRequest): Response<EduProbeResult>

    @POST("edu/connections/from-url")
    suspend fun eduCreateConnectionFromUrl(@Body request: EduConnectionFromUrlRequest): Response<EduConnectionDto>

    @POST("edu/connections")
    suspend fun eduCreateConnection(@Body request: Map<String, String>): Response<EduConnectionDto>

    @GET("edu/connections/{connectionId}")
    suspend fun eduGetConnection(@Path("connectionId") connectionId: String): Response<EduConnectionDto>

    @POST("edu/connections/{connectionId}/continue")
    suspend fun eduContinueConnection(
        @Path("connectionId") connectionId: String,
        @Body request: EduConnectionContinueRequest,
    ): Response<EduConnectionDto>

    @POST("edu/connections/{connectionId}/pre-login")
    suspend fun eduPreLogin(@Path("connectionId") connectionId: String): Response<EduPreLoginResult>

    @GET("edu/schedule/semesters")
    suspend fun eduScheduleSemesters(): Response<List<String>>

    @GET("edu/schedule/items")
    suspend fun eduScheduleItems(@Query("semester") semester: String? = null): Response<EduScheduleItemsResponse>

    @GET("edu/grade/semesters")
    suspend fun eduGradeSemesters(): Response<List<String>>

    @GET("edu/grade/items")
    suspend fun eduGradeItems(@Query("semester") semester: String? = null): Response<EduGradeItemsResponse>

    @GET("edu/exam/semesters")
    suspend fun eduExamSemesters(): Response<List<String>>

    @GET("edu/exam/items")
    suspend fun eduExamItems(@Query("semester") semester: String? = null): Response<EduExamItemsResponse>

    @POST("auth/refresh")
    suspend fun refresh(@Body request: RefreshRequest): Response<LoginResponse>

    @POST("counselor/chat")
    suspend fun chat(@Body request: ChatRequest): Response<ChatResponse>

    @POST("focus/ai/ask")
    suspend fun askFocusAi(@Body request: FocusAiAskRequest): Response<FocusAiAskResponse>

    @POST("focus/realtime-voice/sessions")
    suspend fun createFocusRealtimeVoiceSession(): Response<FocusRealtimeVoiceSessionDto>

    @DELETE("focus/realtime-voice/sessions/{sessionId}")
    suspend fun stopFocusRealtimeVoiceSession(@Path("sessionId") sessionId: String): Response<FocusRealtimeVoiceStopDto>

    @POST("notices/extract-multi")
    suspend fun extractNotice(@Body request: NoticeExtractRequest): Response<MultiNoticeExtractResponseDto>

    @POST("notices/ingest")
    suspend fun ingestNotice(@Body request: NoticeIngestRequest): Response<Unit> // 假设后端返回200 OK即可

    @POST("notices/ingest-batch")
    suspend fun ingestNoticeBatch(@Body request: NoticeBatchIngestRequest): Response<NoticeBatchIngestResponse>

    @POST("chaoxing/login")
    suspend fun loginChaoxing(@Body request: ChaoxingLoginRequest): Response<Unit>

    @POST("chaoxing/sync")
    suspend fun syncChaoxing(): Response<Unit>

    @POST("chaoxing/disconnect")
    suspend fun disconnectChaoxing(): Response<Unit>

    @GET("chaoxing/status")
    suspend fun getChaoxingStatus(): Response<ChaoxingSyncStatusResponse>

    // 校园通知列表（聚合学生可见班级的已发布通知）
    @GET("notices")
    suspend fun listNotices(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
    ): Response<PagedResponse<NoticeDto>>

    // 课程列表
    @GET("courses")
    suspend fun listCourses(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 100,
    ): Response<PagedResponse<CourseDto>>

    @GET("courses/{courseId}/content-summary")
    suspend fun getCourseContentSummary(
        @Path("courseId") courseId: String,
    ): Response<CourseContentSummaryDto>

    @GET("courses/{courseId}/content")
    suspend fun getCourseContent(
        @Path("courseId") courseId: String,
        @Query("page_size") pageSize: Int = 500,
    ): Response<CourseContentPageDto>

    @POST("courses/{courseId}/sync")
    suspend fun syncCourseContent(
        @Path("courseId") courseId: String,
        @Query("sections") sections: String? = null,
    ): Response<Unit>

    @GET("courses/{courseId}/knowledge-graph")
    suspend fun getCourseKnowledgeGraph(
        @Path("courseId") courseId: String,
    ): Response<CourseKnowledgeGraphDto>

    // 查询后端已生成的交互课堂（只读，绝不调用 OpenMAIC 生成）
    @GET("courses/{courseId}/interactive-classroom")
    suspend fun getInteractiveClassroom(
        @Path("courseId") courseId: String,
    ): Response<InteractiveClassroomDto>

    /** 服务状态（configured/available/incompatible/degraded 可区分）。 */
    @GET("courses/{courseId}/interactive-classroom/status")
    suspend fun getInteractiveClassroomStatus(
        @Path("courseId") courseId: String,
    ): Response<InteractiveClassroomStatusDto>

    /** 生成前的只读计划：课程、可选资料、推荐形态与理由。不创建任何任务。 */
    @GET("courses/{courseId}/interactive-classroom/plan")
    suspend fun getInteractiveClassroomPlan(
        @Path("courseId") courseId: String,
        @Query("mode") mode: String = "adaptive",
    ): Response<InteractiveClassroomPlanDto>

    /** 明确提交一次生成（调用方必须先让学生确认）。 */
    @POST("courses/{courseId}/interactive-classroom/generate")
    suspend fun generateInteractiveClassroom(
        @Path("courseId") courseId: String,
        @Body body: InteractiveClassroomGenerateRequest,
    ): Response<InteractiveClassroomGenerateResponse>

    /** 轮询进度（服务端会现场轮询一次 OpenMAIC）。 */
    @GET("courses/{courseId}/interactive-classroom/jobs/{sessionId}")
    suspend fun getInteractiveClassroomJob(
        @Path("courseId") courseId: String,
        @Path("sessionId") sessionId: String,
    ): Response<InteractiveClassroomSessionDto>

    /** 重试 = 重新提交一个新任务（OpenMAIC 没有原生 retry）。 */
    @POST("courses/{courseId}/interactive-classroom/{sessionId}/retry")
    suspend fun retryInteractiveClassroom(
        @Path("courseId") courseId: String,
        @Path("sessionId") sessionId: String,
        @Body body: InteractiveClassroomGenerateRequest,
    ): Response<InteractiveClassroomGenerateResponse>

    /** 回读这节课**真实**包含的内容。 */
    @GET("courses/{courseId}/interactive-classroom/{sessionId}/composition")
    suspend fun getInteractiveClassroomComposition(
        @Path("courseId") courseId: String,
        @Path("sessionId") sessionId: String,
    ): Response<InteractiveClassroomCompositionDto>

    @GET("courses/{courseId}/resources/{itemId}/open")
    suspend fun openCourseResource(
        @Path("courseId") courseId: String,
        @Path("itemId") itemId: String,
    ): Response<CourseResourceOpenDto>

    @Streaming
    @GET("courses/{courseId}/resources/{itemId}/download")
    suspend fun downloadCourseResource(
        @Path("courseId") courseId: String,
        @Path("itemId") itemId: String,
    ): Response<ResponseBody>

    // 全校活动列表（校园动态 / 我的活动）
    @GET("activities")
    suspend fun listActivities(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
    ): Response<PagedResponse<ActivityDto>>

    // 个人待办（云端同步）
    @GET("tasks")
    suspend fun listTasks(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 200,
    ): Response<PagedResponse<PersonalTaskDto>>

    @POST("tasks")
    suspend fun createTask(@Body request: PersonalTaskCreateRequest): Response<PersonalTaskDto>

    @POST("tasks/import/analyze")
    suspend fun analyzeTaskImport(@Body request: TaskImportAnalyzeRequest): Response<TaskImportAnalyzeResponse>

    @POST("tasks/import/commit")
    suspend fun commitTaskImport(@Body request: TaskImportCommitRequest): Response<TaskImportCommitResponse>

    @POST("tasks/rank-importance")
    suspend fun rankTaskImportance(@Body request: ImportanceRankRequest): Response<ImportanceRankResponseDto>

    @PATCH("tasks/{taskId}")
    suspend fun updateTask(
        @Path("taskId") taskId: String,
        @Body request: PersonalTaskUpdateRequest,
    ): Response<PersonalTaskDto>

    @POST("tasks/{taskId}/complete")
    suspend fun completeTask(@Path("taskId") taskId: String): Response<PersonalTaskDto>

    @POST("tasks/{taskId}/restore")
    suspend fun restoreTask(@Path("taskId") taskId: String): Response<PersonalTaskDto>

    @DELETE("tasks/{taskId}")
    suspend fun deleteTask(@Path("taskId") taskId: String): Response<PersonalTaskDto>

    @GET("study/sessions")
    suspend fun listStudySessions(
        @Query("status") status: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 100,
    ): Response<List<StudySessionDto>>

    @GET("study/sessions/active")
    suspend fun activeStudySession(): Response<StudySessionDto?>

    @POST("study/sessions")
    suspend fun createStudySession(@Body request: StudySessionCreateRequest): Response<StudySessionDto>

    @POST("study/sessions/{sessionId}/pause")
    suspend fun pauseStudySession(@Path("sessionId") sessionId: String): Response<StudySessionDto>

    @POST("study/sessions/{sessionId}/resume")
    suspend fun resumeStudySession(@Path("sessionId") sessionId: String): Response<StudySessionDto>

    @POST("study/sessions/{sessionId}/finish")
    suspend fun finishStudySession(
        @Path("sessionId") sessionId: String,
        @Body request: StudySessionFinishRequest = StudySessionFinishRequest(),
    ): Response<StudySessionDto>

    @GET("study/goals/daily")
    suspend fun getDailyStudyGoal(): Response<StudyGoalDto>

    @PUT("study/goals/daily")
    suspend fun updateDailyStudyGoal(@Body request: StudyGoalUpdateRequest): Response<StudyGoalDto>

    @POST("study/task-breakdown")
    suspend fun breakdownStudyGoal(@Body request: TaskBreakdownRequest): Response<TaskBreakdownResponseDto>

    @POST("study/task-breakdown")
    suspend fun breakdownStudyTask(@Body request: TaskBreakdownRequest): Response<TaskBreakdownResponseDto>

    // 个人中心：文件
    @GET("personal-hub/files")
    suspend fun listFiles(): Response<List<PersonalFileDto>>

    @POST("personal-hub/files")
    suspend fun createFile(@Body request: PersonalFileCreateRequest): Response<PersonalFileDto>

    @POST("personal-hub/files/{fileId}/favorite")
    suspend fun toggleFileFavorite(
        @Path("fileId") fileId: String,
        @Body request: FileFavoriteToggleRequest,
    ): Response<PersonalFileDto>

    @DELETE("personal-hub/files/{fileId}")
    suspend fun deleteFile(@Path("fileId") fileId: String): Response<Unit>

    // 个人中心：收藏
    @GET("personal-hub/favorites")
    suspend fun listFavorites(): Response<List<FavoriteDto>>

    @POST("personal-hub/favorites")
    suspend fun addFavorite(@Body request: FavoriteCreateRequest): Response<FavoriteDto>

    @DELETE("personal-hub/favorites/{favoriteId}")
    suspend fun removeFavorite(@Path("favoriteId") favoriteId: String): Response<Unit>

    @Multipart
    @POST("contributions/expression-samples")
    suspend fun uploadExpressionContribution(
        @Part image: MultipartBody.Part,
        @Part("label") label: RequestBody,
        @Part("consent") consent: RequestBody,
        @Part("model_version") modelVersion: RequestBody,
    ): Response<ExpressionContributionResponse>

    @DELETE("contributions/expression-samples/{sampleId}")
    suspend fun deleteExpressionContribution(
        @Path("sampleId") sampleId: String,
    ): Response<ExpressionContributionResponse>

    @GET("edu/systems/{universityId}")
    suspend fun listEduSystems(@Path("universityId") universityId: String): Response<List<EduSystemDto>>

    // ===== QR 扫码登录 =====
    @POST("auth/qr/scan")
    suspend fun qrScan(@Body request: QrScanRequest): Response<QrScanResponse>

    @POST("auth/qr/confirm")
    suspend fun qrConfirm(@Body request: QrConfirmRequest): Response<QrConfirmResponse>

    @POST("auth/qr/cancel")
    suspend fun qrCancel(@Body request: QrScanRequest): Response<Map<String, Any>>

    // ===== Agent Runtime =====
    @GET("agent-runtime/capabilities")
    suspend fun agentCapabilities(): Response<AgentCapabilitiesDto>

    @POST("agent-jobs")
    suspend fun agentCreateJob(
        @Body body: Map<String, Any?>,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<AgentJobDto>

    @GET("agent-jobs/{jobId}")
    suspend fun agentGetJob(@Path("jobId") jobId: String): Response<AgentJobDto>

    @GET("agent-jobs")
    suspend fun agentListJobs(): Response<List<AgentJobDto>>

    @GET("agent-runs/{runId}")
    suspend fun agentGetRun(@Path("runId") runId: String): Response<AgentRunDto>

    @POST("agent-runs/{runId}/cancel")
    suspend fun agentCancelRun(
        @Path("runId") runId: String,
        @Body request: Map<String, String>,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<AgentRunDto>

    @POST("agent-runs/{runId}/pause")
    suspend fun agentPauseRun(
        @Path("runId") runId: String,
        @Body request: Map<String, String>,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<AgentRunDto>

    @POST("agent-runs/{runId}/resume")
    suspend fun agentResumeRun(
        @Path("runId") runId: String,
        @Body request: Map<String, String>,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<AgentRunDto>

    @POST("agent-runs/{runId}/retry")
    suspend fun agentRetryRun(
        @Path("runId") runId: String,
        @Body request: Map<String, String>,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<AgentRunDto>

    @GET("agent-runs/{runId}/events")
    suspend fun agentListRunEvents(@Path("runId") runId: String): Response<List<AgentEventDto>>

    @POST("agent-approvals/{approvalId}/decision")
    suspend fun agentDecideApproval(
        @Path("approvalId") approvalId: String,
        @Body request: ApprovalDecisionRequest,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<AgentApprovalDto>

    @GET("agent-artifacts/{artifactId}")
    suspend fun agentGetArtifact(@Path("artifactId") artifactId: String): Response<AgentArtifactDto>

    @GET("student-goals")
    suspend fun listStudentGoals(): Response<StudentGoalPageDto>

    @POST("student-goals")
    suspend fun createStudentGoal(@Body request: StudentGoalCreateRequest): Response<StudentGoalCreateResultDto>

    @GET("learning-plans/{planId}/summary")
    suspend fun getLearningPlanSummary(@Path("planId") planId: String): Response<LearningPlanSummaryDto>

    @POST("learning-plans/{planId}/decision")
    suspend fun decideLearningPlan(@Path("planId") planId: String, @Body request: Map<String, String>): Response<Map<String, Any?>>

    @POST("learning-plans/{planId}/execute")
    suspend fun executeLearningPlan(@Path("planId") planId: String): Response<Map<String, Any?>>

    @POST("learning-plans/{planId}/replan")
    suspend fun replanLearningPlan(@Path("planId") planId: String, @Header("Idempotency-Key") idempotencyKey: String): Response<Map<String, Any?>>

    // ===== 学生世界模型（只读消费 + 数据源控制）=====

    @GET("learner-state/snapshots")
    suspend fun learnerStateSnapshots(
        @Query("projection_kind") projectionKind: String,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20,
    ): Response<LearnerStateSnapshotPageDto>

    @GET("learner-state/forecasts")
    suspend fun learnerStateForecasts(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 10,
    ): Response<ForecastPageDto>

    @GET("learner-state/data-controls")
    suspend fun learnerStateDataControls(): Response<DataSourceControlListDto>

    @PUT("learner-state/data-controls/{sourceKey}")
    suspend fun updateLearnerStateDataControl(
        @Path("sourceKey") sourceKey: String,
        @Body request: Map<String, String>,
    ): Response<DataSourceControlDto>

    @GET("learner-state/model-transparency")
    suspend fun learnerStateModelTransparency(): Response<ModelTransparencyDto>

    @GET("adaptive-interventions")
    suspend fun listAdaptiveInterventions(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 5,
    ): Response<AdaptiveInterventionPageDto>

    @GET("adaptive-interventions/{interventionId}/outcome")
    suspend fun getAdaptiveInterventionOutcome(
        @Path("interventionId") interventionId: String,
    ): Response<AdaptiveInterventionOutcomeDto>

    // ===== Final Review =====
    @POST("final-review/campaigns")
    suspend fun agentCreateFinalReviewCampaign(
        @Body request: FinalReviewCampaignCreateRequest,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<FinalReviewCampaignDto>

    @GET("final-review/campaigns")
    suspend fun agentListFinalReviewCampaigns(): Response<List<FinalReviewCampaignDto>>

    @GET("final-review/campaigns/{campaignId}")
    suspend fun agentGetFinalReviewCampaign(@Path("campaignId") campaignId: String): Response<FinalReviewCampaignDto>

    @POST("final-review/campaigns/{campaignId}/plans/generate")
    suspend fun agentGenerateFinalReviewPlan(
        @Path("campaignId") campaignId: String,
        @Body request: Map<String, String>,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<FinalReviewPlanGenerateDto>

    @GET("final-review/campaigns/{campaignId}/plan-versions")
    suspend fun agentListFinalReviewPlanVersions(@Path("campaignId") campaignId: String): Response<List<FinalReviewPlanVersionDto>>

    @GET("final-review/campaigns/{campaignId}/plan-versions/{version}")
    suspend fun agentGetFinalReviewPlanVersion(
        @Path("campaignId") campaignId: String,
        @Path("version") version: Int,
    ): Response<FinalReviewPlanVersionDto>

    @POST("final-review/campaigns/{campaignId}/activate")
    suspend fun agentActivateFinalReviewPlan(
        @Path("campaignId") campaignId: String,
        @Body request: FinalReviewActivateRequest,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<Unit>

    @GET("final-review/campaigns/{campaignId}/agendas/today")
    suspend fun agentGetFinalReviewTodayAgenda(@Path("campaignId") campaignId: String): Response<FinalReviewDailyAgendaDto>

    @POST("final-review/daily-items/{itemId}/complete")
    suspend fun agentCompleteFinalReviewDailyItem(
        @Path("itemId") itemId: String,
        @Body request: FinalReviewCompleteItemRequest,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<Unit>

    @POST("final-review/campaigns/{campaignId}/daily-checkins")
    suspend fun agentFinalReviewDailyCheckin(
        @Path("campaignId") campaignId: String,
        @Body request: FinalReviewDailyCheckinRequest,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<Unit>

    @POST("final-review/campaigns/{campaignId}/adjustments/analyze")
    suspend fun agentAnalyzeFinalReviewAdjustments(
        @Path("campaignId") campaignId: String,
        @Body request: Map<String, String>,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<Unit>

    @GET("final-review/campaigns/{campaignId}/adjustment-proposals")
    suspend fun agentListFinalReviewAdjustmentProposals(@Path("campaignId") campaignId: String): Response<List<FinalReviewAdjustmentProposalDto>>

    @POST("final-review/adjustment-proposals/{proposalId}/decision")
    suspend fun agentDecideFinalReviewAdjustment(
        @Path("proposalId") proposalId: String,
        @Body request: ApprovalDecisionRequest,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<Unit>

    // ===== Course Research =====
    @POST("course-research/runs")
    suspend fun agentCreateCourseResearchRun(
        @Body request: CourseResearchRunCreateRequest,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<CourseResearchRunDto>

    @GET("course-research/runs")
    suspend fun agentListCourseResearchRuns(): Response<List<CourseResearchRunDto>>

    @GET("course-research/runs/{runId}")
    suspend fun agentGetCourseResearchRun(@Path("runId") runId: String): Response<CourseResearchRunDto>

    @POST("course-research/runs/{runId}/cancel")
    suspend fun agentCancelCourseResearchRun(
        @Path("runId") runId: String,
        @Body request: Map<String, String>,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<Unit>

    @GET("course-research/runs/{runId}/artifacts")
    suspend fun agentListCourseResearchArtifacts(@Path("runId") runId: String): Response<CourseResearchArtifactBundleDto>

    // ===== Notice Workflow =====
    @GET("notification-sources")
    suspend fun agentListNotificationSources(): Response<List<NotificationSourceDto>>

    @PATCH("notification-sources/{sourceId}")
    suspend fun agentPatchNotificationSource(
        @Path("sourceId") sourceId: String,
        @Body request: NotificationSourcePatchRequest,
    ): Response<NotificationSourceDto>

    @POST("notices/manual")
    suspend fun agentCreateManualNotice(
        @Body request: NoticeManualCreateRequest,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<NoticeManualResponseDto>

    @POST("notices/{noticeId}/workflow")
    suspend fun agentCreateNoticeWorkflow(
        @Path("noticeId") noticeId: String,
        @Body request: NoticeWorkflowCreateRequest,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<NoticeWorkflowDto>

    @GET("notice-workflows/{workflowId}")
    suspend fun agentGetNoticeWorkflow(@Path("workflowId") workflowId: String): Response<NoticeWorkflowDto>

    @POST("notice-workflows/{workflowId}/reanalyze")
    suspend fun agentReanalyzeNoticeWorkflow(
        @Path("workflowId") workflowId: String,
        @Body request: Map<String, String>,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<NoticeWorkflowDto>

    @POST("notice-workflow-actions/{actionId}/decision")
    suspend fun agentDecideNoticeWorkflowAction(
        @Path("actionId") actionId: String,
        @Body request: ApprovalDecisionRequest,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<NoticeWorkflowActionDto>

    @POST("notice-workflow-actions/{actionId}/execute")
    suspend fun agentExecuteNoticeWorkflowAction(
        @Path("actionId") actionId: String,
        @Body request: Map<String, String>,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<NoticeWorkflowActionDto>
}

// ===== QR 扫码登录 DTO =====

data class QrScanRequest(
    val session_id: String,
    val scan_token: String,
)

data class QrScanResponse(
    val session_id: String = "",
    val browser_name: String? = null,
    val os_name: String? = null,
    val device_label: String? = null,
    val expires_at: String = "",
    val status: String = "SCANNED",
)

data class QrConfirmRequest(
    val session_id: String,
    val scan_token: String,
    val trust_device: Boolean = false,
)

data class QrConfirmResponse(
    val session_id: String = "",
    val status: String = "CONFIRMED",
    val trust_device: Boolean = false,
)

data class EduSystemDto(
    val id: String = "",
    val university_id: String = "",
    val system_key: String = "",
    val name: String? = null,
    val system_type: String = "unknown",
    val provider: String = "unknown",
    val login_execution_mode: String = "unsupported",
    val status: String = "active",
    val is_mock: Boolean = false,
    val supported_features: List<String> = emptyList(),
)

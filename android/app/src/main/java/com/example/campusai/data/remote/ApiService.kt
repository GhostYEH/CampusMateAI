package com.example.campusai.data.remote

import com.example.campusai.data.model.ExtractResult
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
    val expression_signal: ExpressionSignalRequest? = null,
)
data class ChatResponse(val answer: String? = null, val message: String? = null)
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
)

data class PersonalTaskUpdateRequest(
    val title: String? = null,
    val description: String? = null,
    val deadline: String? = null,
    val source_name: String? = null,
)

data class StudySessionDto(
    val id: String,
    val user_id: String,
    val mode: String,
    val goal: String? = null,
    val related_task_id: String? = null,
    val started_at: String,
    val paused_at: String? = null,
    val ended_at: String? = null,
    val duration_seconds: Int = 0,
    val pause_seconds: Int = 0,
    val status: String,
)

data class StudySessionCreateRequest(
    val mode: String,
    val goal: String? = null,
    val related_task_id: String? = null,
)

data class StudySessionFinishRequest(
    val self_report: String? = null,
    val self_report_tags: List<String>? = null,
)

data class StudyGoalDto(val target_minutes: Int, val updated_at: String)
data class StudyGoalUpdateRequest(val target_minutes: Int)

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

interface ApiService {
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
    suspend fun syncCourseContent(@Path("courseId") courseId: String): Response<Unit>

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

    // 个人待办（云端同步）
    @GET("tasks")
    suspend fun listTasks(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 200,
    ): Response<PagedResponse<PersonalTaskDto>>

    @POST("tasks")
    suspend fun createTask(@Body request: PersonalTaskCreateRequest): Response<PersonalTaskDto>

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

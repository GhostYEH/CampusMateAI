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
    val author_name: String = "校园同学",
    val is_anonymous: Boolean = false,
    val like_count: Int = 0,
    val comment_count: Int = 0,
    val favorite_count: Int = 0,
    val created_at: String = "",
)
data class CommunityPostCreateRequest(
    val title: String,
    val content: String,
    val category: String = "campus",
    val images: List<String> = emptyList(),
    val is_anonymous: Boolean = false,
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
    val system_type: String = "undergrad",
    val external_student_id: String? = null,
    val external_student_name: String? = null,
    val connection_status: String = "unbound",
    val session_type: String? = null,
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

// ── 全校活动（同时作为「校园动态」与「我的活动」数据源） ──
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
    val status: String? = null,
    val created_at: String? = null,
    val updated_at: String? = null,
)

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

    @GET("community/posts")
    suspend fun listCommunityPosts(
        @Query("q") query: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 30,
    ): Response<PagedResponse<CommunityPostDto>>

    @POST("community/posts")
    suspend fun createCommunityPost(@Body request: CommunityPostCreateRequest): Response<CommunityPostDto>

    @POST("community/posts/{postId}/like")
    suspend fun likeCommunityPost(@Path("postId") postId: String): Response<CommunityPostDto>

    @POST("community/posts/{postId}/favorite")
    suspend fun favoriteCommunityPost(@Path("postId") postId: String): Response<CommunityPostDto>

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
}

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

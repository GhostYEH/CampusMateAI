package com.example.campusai.data.remote

import com.example.campusai.data.model.ExtractResult
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.*

data class LoginRequest(val username: String, val password: String)
data class LoginResponse(val access_token: String, val refresh_token: String)
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
data class ExtractRequest(val text: String)
data class HealthResponse(val mode: String? = null)
data class KnowledgeStatusResponse(
    val mode: String? = null,
    val document_count: Int? = null,
    val index_ready: Boolean? = null,
)
data class MeResponse(val user: UserResponse? = null)
data class UserResponse(
    val name: String,
    val role: String,
    val detail: String = "",
    val account_id: String? = null,
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
)

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

    @POST("counselor/chat")
    suspend fun chat(@Body request: ChatRequest): Response<ChatResponse>

    @POST("notices/extract-multi")
    suspend fun extractNotice(@Body request: ExtractRequest): Response<ExtractResult>

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
}

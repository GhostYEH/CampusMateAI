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

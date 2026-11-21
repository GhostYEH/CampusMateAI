package com.example.campusai.data.remote

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

data class LearningIdentity(val uid: String, val name: String)
data class LearningMember(val uid: String, val name: String, val status: String)
data class LearningRoomSummary(val id: String, val title: String, val host_uid: String)
data class LearningRooms(val items: List<LearningRoomSummary>)
data class LearningRoom(
    val id: String, val title: String, val host_uid: String,
    val scene_index: Int, val scene_count: Int, val members: List<LearningMember>,
)
data class LearningInvitation(val room_id: String, val title: String, val host_name: String)
data class LearningInvitations(val items: List<LearningInvitation>)
data class LearningMessage(val id: Long, val uid: String, val name: String, val content: String)
data class LearningMessages(val items: List<LearningMessage>)
data class NativeRoomRequest(val title: String)
data class LearningInviteRequest(val uid: String)
data class LearningMessageRequest(val content: String, val client_id: String)
data class LearningCursorRequest(val scene_index: Int)
data class ClassroomRtcStatus(val available: Boolean, val reason: String?)
data class ClassroomRtcToken(
    val provider: String, val app_id: String, val room_id: String, val user_id: String,
    val token: String, val expires_at: Long, val refresh_after_seconds: Int,
)

data class LearningAttentionRequest(val state: String, val source: String)
data class LearningTeacherNudge(
    val id: Long,
    val from_uid: String?,
    val target_uid: String?,
    val kind: String,
    val content: String,
    val created_at: String,
)
data class LearningAttentionReport(
    val state: String,
    val updated_at: String,
    val teacher_reminder: LearningTeacherNudge?,
)
data class LearningSupervisionMember(
    val uid: String,
    val name: String = "",
    val is_host: Boolean = false,
    val state: String,
    val source: String,
    val updated_at: String?,
    val online: Boolean,
    val attention_age_seconds: Int?,
)
data class LearningSupervisionStats(
    val total: Int,
    val online: Int,
    val focused: Int,
    val needs_attention: Int,
)
data class LearningSupervision(
    val me: LearningSupervisionMember,
    val members: List<LearningSupervisionMember>,
    val stats: LearningSupervisionStats?,
    val teacher_summary: String?,
    val teacher_name: String,
    val nudges: List<LearningTeacherNudge>,
)
data class LearningNudgeRequest(val target_uid: String? = null, val content: String? = null)

/** CampusMate control plane only. Media is handled by the RTC SDK. */
interface LearningRoomApi {
    @GET("magicclass/learning-space/identity") suspend fun identity(): LearningIdentity
    @GET("magicclass/learning-space/rtc/status") suspend fun rtcStatus(): ClassroomRtcStatus
    @GET("magicclass/learning-space/rooms") suspend fun rooms(): LearningRooms
    @GET("magicclass/learning-space/invitations") suspend fun invitations(): LearningInvitations
    @POST("magicclass/learning-space/rooms/native")
    suspend fun create(@Body body: NativeRoomRequest): LearningRoom
    @GET("magicclass/learning-space/rooms/{id}")
    suspend fun room(@Path("id") id: String): LearningRoom
    @POST("magicclass/learning-space/rooms/{id}/invitations")
    suspend fun invite(@Path("id") id: String, @Body body: LearningInviteRequest)
    @POST("magicclass/learning-space/invitations/{id}/accept")
    suspend fun accept(@Path("id") id: String): LearningRoom
    @POST("magicclass/learning-space/invitations/{id}/decline")
    suspend fun decline(@Path("id") id: String)
    @POST("magicclass/learning-space/rooms/{id}/rtc-token")
    suspend fun rtcToken(@Path("id") id: String): ClassroomRtcToken
    @POST("magicclass/learning-space/rooms/{id}/leave")
    suspend fun leave(@Path("id") id: String)
    @GET("magicclass/learning-space/rooms/{id}/messages")
    suspend fun messages(@Path("id") id: String, @Query("after") after: Long): LearningMessages
    @POST("magicclass/learning-space/rooms/{id}/messages")
    suspend fun send(@Path("id") id: String, @Body body: LearningMessageRequest): Map<String, Any>
    @PATCH("magicclass/learning-space/rooms/{id}/cursor")
    suspend fun cursor(@Path("id") id: String, @Body body: LearningCursorRequest)
    @PUT("magicclass/learning-space/rooms/{id}/attention")
    suspend fun reportAttention(@Path("id") id: String, @Body body: LearningAttentionRequest): LearningAttentionReport
    @GET("magicclass/learning-space/rooms/{id}/supervision")
    suspend fun supervision(@Path("id") id: String, @Query("after") after: Long): LearningSupervision
    @POST("magicclass/learning-space/rooms/{id}/nudges")
    suspend fun nudge(@Path("id") id: String, @Body body: LearningNudgeRequest): LearningTeacherNudge
}

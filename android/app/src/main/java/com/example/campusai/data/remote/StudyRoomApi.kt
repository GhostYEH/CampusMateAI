package com.example.campusai.data.remote

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * 多人在线自习室（互相监督）——纯 HTTP 轮询，无音视频。
 *
 * 契约见 docs/api/05-study.md「多人在线自习室」。所有可选字段都带默认值，
 * 这样 Moshi 在字段缺省时不会抛错。
 */
data class StudyRoomIdentity(val uid: String, val name: String = "")
data class StudyRoomTimer(
    val phase: String = "idle",
    val running: Boolean = false,
    val paused: Boolean = false,
    val remaining_seconds: Int = 0,
    val server_time: String = "",
)
data class StudyRoomMember(
    val uid: String,
    val name: String = "",
    val status: String = "accepted",
    val study_state: String = "idle",
    val online: Boolean = false,
    val last_seen_at: String? = null,
    val status_message: String = "",
)
data class StudyRoom(
    val id: String,
    val title: String,
    val host_uid: String,
    val active: Int = 1,
    val created_at: String = "",
    val focus_minutes: Int = 25,
    val break_minutes: Int = 5,
    val timer: StudyRoomTimer = StudyRoomTimer(),
    val members: List<StudyRoomMember> = emptyList(),
)
data class StudyRoomSummary(
    val id: String,
    val title: String,
    val host_uid: String = "",
    val created_at: String = "",
    val member_count: Int = 0,
)
data class StudyRoomList(val items: List<StudyRoomSummary> = emptyList())
data class StudyRoomInvitation(
    val room_id: String,
    val title: String,
    val host_uid: String = "",
    val host_name: String = "",
    val updated_at: String = "",
)
data class StudyRoomInvitations(val items: List<StudyRoomInvitation> = emptyList())
data class StudyRoomMessage(
    val id: Long,
    val uid: String = "",
    val name: String = "",
    val content: String = "",
    val created_at: String = "",
)
data class StudyRoomMessages(val items: List<StudyRoomMessage> = emptyList())

data class StudyRoomCreateRequest(val title: String, val focus_minutes: Int = 25, val break_minutes: Int = 5)
data class StudyRoomInviteRequest(val uid: String)
data class StudyRoomStateRequest(val study_state: String, val status_message: String? = null)
data class StudyRoomTimerRequest(val action: String, val focus_minutes: Int? = null, val break_minutes: Int? = null)
data class StudyRoomMessageRequest(val content: String, val client_id: String)

interface StudyRoomApi {
    @GET("study/rooms/identity") suspend fun identity(): StudyRoomIdentity
    @GET("study/rooms/students/{uid}") suspend fun student(@Path("uid") uid: String): StudyRoomIdentity
    @GET("study/rooms/") suspend fun rooms(): StudyRoomList
    @GET("study/rooms/invitations") suspend fun invitations(): StudyRoomInvitations
    @POST("study/rooms/") suspend fun create(@Body body: StudyRoomCreateRequest): StudyRoom
    @GET("study/rooms/{id}") suspend fun room(@Path("id") id: String): StudyRoom
    @POST("study/rooms/{id}/invitations") suspend fun invite(@Path("id") id: String, @Body body: StudyRoomInviteRequest)
    @POST("study/rooms/invitations/{id}/accept") suspend fun accept(@Path("id") id: String): StudyRoom
    @POST("study/rooms/invitations/{id}/decline") suspend fun decline(@Path("id") id: String)
    @PATCH("study/rooms/{id}/state") suspend fun setState(@Path("id") id: String, @Body body: StudyRoomStateRequest)
    @POST("study/rooms/{id}/heartbeat") suspend fun heartbeat(@Path("id") id: String): Map<String, Any>
    @POST("study/rooms/{id}/timer") suspend fun timer(@Path("id") id: String, @Body body: StudyRoomTimerRequest): StudyRoom
    @GET("study/rooms/{id}/messages") suspend fun messages(@Path("id") id: String, @Query("after") after: Long): StudyRoomMessages
    @POST("study/rooms/{id}/messages") suspend fun send(@Path("id") id: String, @Body body: StudyRoomMessageRequest): Map<String, Any>
    @POST("study/rooms/{id}/leave") suspend fun leave(@Path("id") id: String)
}

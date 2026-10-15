package com.example.campusai.ui.screens.classroom

import android.app.Application
import android.os.SystemClock
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.campusai.data.classroom.ClassroomCall
import com.example.campusai.data.classroom.ClassroomCallPhase
import com.example.campusai.data.classroom.ClassroomCallService
import com.example.campusai.data.remote.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.util.UUID

data class LearningRoomUiState(
    val identity: LearningIdentity? = null,
    val rooms: List<LearningRoomSummary> = emptyList(),
    val invitations: List<LearningInvitation> = emptyList(),
    val room: LearningRoom? = null,
    val messages: List<LearningMessage> = emptyList(),
    val rtcStatus: ClassroomRtcStatus? = null,
    val busy: Boolean = false,
    val notice: String? = null,
    val sentVersion: Int = 0,
)

class LearningRoomViewModel(application: Application) : AndroidViewModel(application) {
    private val api = ApiClient.learningRooms
    private val mutableState = MutableStateFlow(LearningRoomUiState())
    val state = mutableState.asStateFlow()
    val call = ClassroomCall(application) { renewToken() }
    private var foreground = false
    private var uiVisible = false
    private var pollJob: Job? = null
    private var tokenJob: Job? = null
    private var renewalJob: Job? = null
    private var epoch = 0
    private var cursor = 0L
    private var tokenDeadlineMs = 0L
    private var messageAttempt: Triple<String, String, String>? = null

    init {
        viewModelScope.launch {
            call.state.collect { state ->
                if (state.phase in listOf(ClassroomCallPhase.OFF, ClassroomCallPhase.ERROR)) {
                    ClassroomCallService.stop(getApplication())
                    if (!uiVisible) stopInBackground()
                }
            }
        }
    }

    fun foreground(visible: Boolean) {
        uiVisible = visible
        pollJob?.cancel()
        if (!visible) {
            call.camera(false)
            if (call.state.value.phase !in listOf(ClassroomCallPhase.CONNECTED, ClassroomCallPhase.RECONNECTING)) {
                stopInBackground()
                return
            }
        }
        foreground = true
        pollJob = viewModelScope.launch {
            while (true) {
                val selected = mutableState.value.room?.id
                val requestEpoch = epoch
                var backlog = false
                try {
                    if (mutableState.value.identity == null) {
                        val identity = api.identity()
                        mutableState.update { it.copy(identity = identity) }
                    }
                    val rooms = api.rooms().items
                    val invitations = api.invitations().items
                    val status = api.rtcStatus()
                    mutableState.update { it.copy(rooms = rooms, invitations = invitations, rtcStatus = status) }
                    if (selected != null) {
                        val room = api.room(selected)
                        val messages = api.messages(selected, cursor).items
                        if (epoch == requestEpoch) {
                            if (messages.isNotEmpty()) cursor = messages.last().id
                            backlog = messages.size == 100
                            mutableState.update { it.copy(room = room,
                                messages = (it.messages + messages).distinctBy { message -> message.id }.takeLast(300)) }
                        }
                    }
                } catch (error: CancellationException) {
                    throw error
                } catch (error: Exception) {
                    if (epoch == requestEpoch) {
                        if (selected != null && error is HttpException && error.code() in listOf(401, 403, 404, 410)) {
                            select(null)
                        }
                        mutableState.update { it.copy(notice = readable(error)) }
                    }
                }
                delay(if (backlog) 100 else 3_000)
            }
        }
    }

    private fun stopInBackground() {
        foreground = false
        pollJob?.cancel()
        disconnect()
    }

    private fun select(room: LearningRoom?) {
        epoch++
        disconnect()
        cursor = 0
        messageAttempt = null
        mutableState.update { it.copy(room = room, messages = emptyList()) }
    }

    private fun action(block: suspend () -> Unit) {
        if (mutableState.value.busy) return
        viewModelScope.launch {
            mutableState.update { it.copy(busy = true, notice = null) }
            try {
                block()
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                mutableState.update { it.copy(notice = readable(error)) }
            } finally {
                mutableState.update { it.copy(busy = false) }
            }
        }
    }

    fun create(title: String) = action { select(api.create(NativeRoomRequest(title.trim()))) }
    fun join(id: String, accept: Boolean = false) = action {
        select(if (accept) api.accept(id) else api.room(id))
    }
    fun decline(id: String) = action {
        api.decline(id)
        mutableState.update { it.copy(invitations = it.invitations.filterNot { invitation -> invitation.room_id == id }) }
    }
    fun invite(uid: String) = action {
        val room = mutableState.value.room ?: return@action
        api.invite(room.id, LearningInviteRequest(uid.trim()))
        val updated = api.room(room.id)
        mutableState.update { it.copy(room = updated, notice = "邀请已发送，对方接受后即可加入通话") }
    }
    fun leave() = action {
        val room = mutableState.value.room ?: return@action
        // Release the device immediately, even when the HTTP leave request fails.
        disconnect()
        api.leave(room.id)
        select(null)
    }
    fun returnToList() { select(null) } // Keeps membership; does not end the shared classroom.
    fun send(content: String) = action {
        val room = mutableState.value.room ?: return@action
        val text = content.trim()
        if (text.isEmpty()) return@action
        val attempt = messageAttempt?.takeIf { it.first == room.id && it.second == text }
            ?: Triple(room.id, text, UUID.randomUUID().toString()).also { messageAttempt = it }
        api.send(room.id, LearningMessageRequest(text, attempt.third))
        messageAttempt = null
        mutableState.update { it.copy(sentVersion = it.sentVersion + 1) }
    }
    fun page(index: Int) = action {
        val room = mutableState.value.room ?: return@action
        api.cursor(room.id, LearningCursorRequest(index))
        mutableState.update { it.copy(room = room.copy(scene_index = index)) }
    }

    fun connect() {
        if (!uiVisible) return
        if (tokenJob?.isActive == true && call.state.value.phase != ClassroomCallPhase.ERROR) return
        tokenJob?.cancel()
        val roomId = mutableState.value.room?.id ?: return
        val requestEpoch = epoch
        tokenJob = viewModelScope.launch {
            try {
                val token = api.rtcToken(roomId)
                if (!foreground || epoch != requestEpoch) return@launch
                // Protocol TTL is 120s. Reserve 10s for HTTP transit and shutdown;
                // wall-clock changes on a handset must not break a live call.
                tokenDeadlineMs = SystemClock.elapsedRealtime() + 110_000L
                ClassroomCallService.start(getApplication(), false, ::disconnect)
                call.connect(token)
                while (true) {
                    delay(token.refresh_after_seconds * 1_000L)
                    if (call.state.value.phase in listOf(ClassroomCallPhase.OFF, ClassroomCallPhase.ERROR)) break
                    renewToken()
                }
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                if (epoch == requestEpoch) {
                    call.disconnect()
                    mutableState.update { it.copy(notice = readable(error)) }
                }
            }
        }
    }

    private fun renewToken() {
        if (!foreground || renewalJob?.isActive == true) return
        val roomId = mutableState.value.room?.id ?: return
        val requestEpoch = epoch
        renewalJob = viewModelScope.launch {
            var retryMs = 1_000L
            while (foreground && epoch == requestEpoch) {
                try {
                    val token = api.rtcToken(roomId)
                    if (epoch != requestEpoch) return@launch
                    call.updateToken(token.token)
                    tokenDeadlineMs = SystemClock.elapsedRealtime() + 110_000L
                    return@launch
                } catch (error: CancellationException) {
                    throw error
                } catch (error: Exception) {
                    if (error is HttpException && error.code() in listOf(401, 403, 404, 410) ||
                        SystemClock.elapsedRealtime() >= tokenDeadlineMs) {
                        disconnect()
                        mutableState.update { it.copy(notice = "通话凭证已失效，请重新加入课堂") }
                        return@launch
                    }
                    delay(retryMs)
                    retryMs = (retryMs * 2).coerceAtMost(8_000)
                }
            }
        }
    }

    fun disconnect() {
        tokenJob?.cancel(); tokenJob = null
        renewalJob?.cancel(); renewalJob = null
        call.disconnect()
        ClassroomCallService.stop(getApplication())
    }
    fun microphone(enabled: Boolean) {
        if (enabled && !uiVisible) return
        try {
            // Promote to the microphone service type while the app is visible,
            // before capture starts, so Android 14 permits background audio.
            ClassroomCallService.start(getApplication(), enabled, ::disconnect)
            call.microphone(enabled)
        } catch (_: Exception) {
            call.microphone(false)
            notice("无法启动麦克风通话服务，请检查系统权限")
        }
    }
    fun notice(message: String) { mutableState.update { it.copy(notice = message) } }
    private fun readable(error: Exception): String = when (error) {
        is HttpException -> when (error.code()) {
            401 -> "登录已失效，请重新登录"
            403 -> "只有课堂发起人可以执行此操作"
            404, 410 -> "课堂或邀请已失效，请返回列表"
            409 -> "课堂或成员数量已达上限，或当前操作与课堂状态冲突"
            422 -> "请检查 UID、课堂标题或消息内容"
            503 -> "课堂音视频尚未配置或暂不可用"
            else -> "服务暂不可用，请稍后重试"
        }
        else -> "网络连接失败，请检查网络后重试"
    }
    override fun onCleared() { disconnect(); super.onCleared() }
}

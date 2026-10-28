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
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
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
    val sentRoomId: String? = null,
    val sentDraft: String? = null,
    val pendingMessage: PendingRoomMessage? = null,
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
    private var microphoneJob: Job? = null
    private var expiryJob: Job? = null
    private val serviceOwner = Any()
    private var epoch = 0
    private var cursor = 0L
    private var tokenDeadlineMs = 0L
    private val messageOutbox = MessageOutbox()
    private var sessionToken = ApiClient.currentAccessToken()

    init {
        viewModelScope.launch {
            call.state.collect { state ->
                if (state.phase in listOf(ClassroomCallPhase.OFF, ClassroomCallPhase.ERROR)) {
                    stopCallJobs()
                    ClassroomCallService.stop(getApplication(), serviceOwner)
                    if (!uiVisible) stopInBackground()
                }
            }
        }
    }

    fun foreground(visible: Boolean) {
        uiVisible = visible
        pollJob?.cancel()
        if (!visible) {
            microphoneJob?.cancel()
            call.camera(false)
            if (call.state.value.phase !in listOf(ClassroomCallPhase.CONNECTED, ClassroomCallPhase.RECONNECTING)) {
                stopInBackground()
                return
            }
        }
        foreground = true
        pollJob = viewModelScope.launch {
            while (true) {
                if (!checkSession()) {
                    delay(3_000)
                    continue
                }
                val selected = mutableState.value.room?.id
                val requestEpoch = epoch
                try {
                    val identity = api.identity()
                    val previousIdentity = mutableState.value.identity
                    if (previousIdentity != null && previousIdentity.uid != identity.uid) {
                        select(null)
                        messageOutbox.clear()
                        mutableState.update { it.copy(identity = identity, rooms = emptyList(), invitations = emptyList(), pendingMessage = null) }
                        continue
                    }
                    mutableState.update { it.copy(identity = identity) }
                    val rooms = api.rooms().items
                    val invitations = api.invitations().items
                    val status = api.rtcStatus()
                    mutableState.update { it.copy(rooms = rooms, invitations = invitations, rtcStatus = status) }
                    if (selected != null) {
                        val room = api.room(selected)
                        if (epoch == requestEpoch) mutableState.update { it.copy(room = room) }
                        while (epoch == requestEpoch) {
                            val messages = api.messages(selected, cursor).items
                            if (epoch != requestEpoch) break
                            if (messages.isNotEmpty()) cursor = messages.last().id
                            mutableState.update {
                                it.copy(messages = (it.messages + messages).distinctBy { message -> message.id }.takeLast(300))
                            }
                            if (messages.size < 100) break
                            delay(100)
                        }
                    }
                } catch (error: CancellationException) {
                    throw error
                } catch (error: Exception) {
                    if (epoch == requestEpoch) {
                        if (error is HttpException && error.code() == 401) {
                            select(null)
                            messageOutbox.clear()
                            mutableState.update { it.copy(identity = null, rooms = emptyList(), invitations = emptyList(), pendingMessage = null) }
                        } else if (selected != null && error is HttpException && error.code() in listOf(403, 404, 410)) {
                            select(null)
                        }
                        mutableState.update { it.copy(notice = readable(error)) }
                    }
                }
                delay(if (uiVisible) 3_000 else 15_000)
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
        mutableState.update { it.copy(room = room, messages = emptyList(), pendingMessage = room?.id?.let(messageOutbox::get)) }
    }

    private fun checkSession(): Boolean {
        val current = ApiClient.currentAccessToken()
        if (current != sessionToken) {
            sessionToken = current
            select(null)
            messageOutbox.clear()
            mutableState.update {
                it.copy(identity = null, rooms = emptyList(), invitations = emptyList(), pendingMessage = null,
                    notice = "登录状态已变更，请重新进入课堂并检查未确认的消息")
            }
            return false
        }
        return !current.isNullOrBlank()
    }

    private fun action(block: suspend () -> Unit) {
        if (!checkSession()) return
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
        messageOutbox.get(room.id)?.let(messageOutbox::remove)
        select(null)
    }
    fun returnToList() { select(null) } // Keeps membership; does not end the shared classroom.
    fun send(content: String) = action {
        val room = mutableState.value.room ?: return@action
        if (content.isBlank()) return@action
        val attempt = messageOutbox.begin(room.id, content, UUID.randomUUID().toString())
        if (attempt == null) {
            mutableState.update { it.copy(notice = "请先重试或放弃上一条发送结果不确定的消息") }
            return@action
        }
        mutableState.update { it.copy(pendingMessage = attempt) }
        deliver(attempt)
    }

    fun retryMessage() = action {
        val roomId = mutableState.value.room?.id ?: return@action
        messageOutbox.get(roomId)?.let { deliver(it) }
    }

    fun discardPendingMessage() {
        val roomId = mutableState.value.room?.id ?: return
        messageOutbox.get(roomId)?.let(messageOutbox::remove)
        mutableState.update { it.copy(pendingMessage = null) }
    }

    private suspend fun deliver(attempt: PendingRoomMessage) {
        if (!checkSession()) return
        api.send(attempt.roomId, LearningMessageRequest(attempt.draft.trim(), attempt.clientId))
        messageOutbox.remove(attempt)
        mutableState.update {
            it.copy(sentVersion = it.sentVersion + 1, sentRoomId = attempt.roomId, sentDraft = attempt.draft,
                pendingMessage = if (it.room?.id == attempt.roomId) null else it.pendingMessage)
        }
    }
    fun page(index: Int) = action {
        val room = mutableState.value.room ?: return@action
        api.cursor(room.id, LearningCursorRequest(index))
        mutableState.update { it.copy(room = room.copy(scene_index = index)) }
    }

    fun connect() {
        if (!checkSession()) return
        if (!uiVisible) return
        if (tokenJob?.isActive == true && call.state.value.phase != ClassroomCallPhase.ERROR) return
        tokenJob?.cancel()
        val roomId = mutableState.value.room?.id ?: return
        val requestEpoch = epoch
        call.prepareConnection()
        val session = call.sessionGeneration
        tokenJob = viewModelScope.launch {
            try {
                val requestedAt = SystemClock.elapsedRealtime()
                val token = api.rtcToken(roomId)
                if (!uiVisible || epoch != requestEpoch || session != call.sessionGeneration) return@launch
                // Protocol TTL is 120s. Reserve 10s for HTTP transit and shutdown;
                // wall-clock changes on a handset must not break a live call.
                tokenDeadlineMs = requestedAt + 110_000L
                prepareCallService(false)
                if (!uiVisible || epoch != requestEpoch || session != call.sessionGeneration) return@launch
                call.connect(token)
                if (call.state.value.phase == ClassroomCallPhase.ERROR) return@launch
                watchTokenExpiry()
                while (true) {
                    delay(token.refresh_after_seconds * 1_000L)
                    if (call.state.value.phase in listOf(ClassroomCallPhase.OFF, ClassroomCallPhase.ERROR)) break
                    renewToken()
                }
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                if (epoch == requestEpoch) {
                    disconnect()
                    mutableState.update { it.copy(notice = readable(error)) }
                }
            }
        }
    }

    private fun renewToken() {
        if (!foreground || renewalJob?.isActive == true) return
        val roomId = mutableState.value.room?.id ?: return
        val requestEpoch = epoch
        val session = call.sessionGeneration
        renewalJob = viewModelScope.launch {
            var retryMs = 1_000L
            while (foreground && epoch == requestEpoch) {
                try {
                    val requestedAt = SystemClock.elapsedRealtime()
                    val token = api.rtcToken(roomId)
                    if (epoch != requestEpoch || session != call.sessionGeneration) return@launch
                    call.updateToken(token.token)
                    tokenDeadlineMs = requestedAt + 110_000L
                    watchTokenExpiry()
                    return@launch
                } catch (error: CancellationException) {
                    throw error
                } catch (error: Exception) {
                    if (epoch != requestEpoch || session != call.sessionGeneration) return@launch
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

    private fun stopCallJobs() {
        tokenJob?.cancel(); tokenJob = null
        renewalJob?.cancel(); renewalJob = null
        microphoneJob?.cancel(); microphoneJob = null
        expiryJob?.cancel(); expiryJob = null
    }

    fun disconnect() {
        stopCallJobs()
        call.disconnect()
        ClassroomCallService.stop(getApplication(), serviceOwner)
    }

    private suspend fun prepareCallService(microphone: Boolean) {
        val ready = CompletableDeferred<Unit>()
        ClassroomCallService.start(getApplication(), serviceOwner, microphone, ::disconnect) { ready.complete(Unit) }
        check(withTimeoutOrNull(5_000L) { ready.await(); true } == true) {
            "Foreground call service did not become ready"
        }
    }

    private fun watchTokenExpiry() {
        expiryJob?.cancel()
        expiryJob = viewModelScope.launch {
            delay((tokenDeadlineMs - SystemClock.elapsedRealtime()).coerceAtLeast(0L))
            disconnect()
            notice("通话凭证已失效，请重新加入课堂")
        }
    }

    fun microphone(enabled: Boolean) {
        microphoneJob?.cancel()
        if (!enabled) {
            call.microphone(false)
            return
        }
        if (!uiVisible || call.state.value.phase != ClassroomCallPhase.CONNECTED) return
        val session = call.sessionGeneration
        microphoneJob = viewModelScope.launch {
            try {
                // Wait for Android to accept the microphone service type before
                // capturing, rather than assuming startForegroundService is ready.
                prepareCallService(true)
                if (uiVisible && session == call.sessionGeneration) call.microphone(true)
            } catch (error: CancellationException) {
                throw error
            } catch (_: Exception) {
                call.microphone(false)
                notice("无法启动麦克风通话服务，请检查系统权限")
            }
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

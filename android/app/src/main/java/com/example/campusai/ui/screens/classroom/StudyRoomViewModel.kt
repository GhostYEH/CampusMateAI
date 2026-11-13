package com.example.campusai.ui.screens.classroom

import android.app.Application
import android.os.SystemClock
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.campusai.data.remote.ApiClient
import com.example.campusai.data.remote.StudyRoom
import com.example.campusai.data.remote.StudyRoomCreateRequest
import com.example.campusai.data.remote.StudyRoomIdentity
import com.example.campusai.data.remote.StudyRoomInvitation
import com.example.campusai.data.remote.StudyRoomInviteRequest
import com.example.campusai.data.remote.StudyRoomMessage
import com.example.campusai.data.remote.StudyRoomMessageRequest
import com.example.campusai.data.remote.StudyRoomStateRequest
import com.example.campusai.data.remote.StudyRoomSummary
import com.example.campusai.data.remote.StudyRoomTimerRequest
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.util.UUID

data class StudyRoomUiState(
    val identity: StudyRoomIdentity? = null,
    val rooms: List<StudyRoomSummary> = emptyList(),
    val invitations: List<StudyRoomInvitation> = emptyList(),
    val room: StudyRoom? = null,
    val messages: List<StudyRoomMessage> = emptyList(),
    val busy: Boolean = false,
    val notice: String? = null,
    val fetchedAtElapsedMs: Long = 0L,
)

/**
 * 多人在线自习室（互相监督）——纯轮询，无音视频。
 * 与 [LearningRoomViewModel]（共同课堂）是两套能力：这里没有 RTC，只有
 * 成员在线状态、共享番茄钟与房内文字。
 */
class StudyRoomViewModel(application: Application) : AndroidViewModel(application) {
    private val api = ApiClient.studyRooms
    private val mutableState = MutableStateFlow(StudyRoomUiState())
    val state = mutableState.asStateFlow()
    private var pollJob: Job? = null
    private var visible = false
    private var cursor = 0L
    private var beatCounter = 0

    fun foreground(isVisible: Boolean) {
        visible = isVisible
        pollJob?.cancel()
        if (!isVisible) return
        pollJob = viewModelScope.launch {
            while (true) {
                val selected = mutableState.value.room?.id
                try {
                    val identity = api.identity()
                    val rooms = api.rooms().items
                    val invitations = api.invitations().items
                    mutableState.update { it.copy(identity = identity, rooms = rooms, invitations = invitations, notice = null) }
                    if (selected != null) {
                        val room = api.room(selected)
                        mutableState.update { it.copy(room = room, fetchedAtElapsedMs = SystemClock.elapsedRealtime()) }
                        pullMessages(selected)
                        if (beatCounter % 3 == 0) api.heartbeat(selected)
                        beatCounter++
                    }
                } catch (error: CancellationException) {
                    throw error
                } catch (error: Exception) {
                    mutableState.update { it.copy(notice = readable(error)) }
                }
                delay(if (visible) 5_000 else 15_000)
            }
        }
    }

    private suspend fun pullMessages(roomId: String) {
        var after = cursor
        while (true) {
            val page = api.messages(roomId, after).items
            if (page.isNotEmpty()) {
                cursor = page.last().id
                mutableState.update { it.copy(messages = (it.messages + page).distinctBy { m -> m.id }.sortedBy { m -> m.id }.takeLast(300)) }
            }
            if (page.size < 100) break
            after = cursor
        }
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

    private fun select(room: StudyRoom?) {
        cursor = 0L
        beatCounter = 0
        mutableState.update { it.copy(room = room, messages = emptyList(), fetchedAtElapsedMs = SystemClock.elapsedRealtime()) }
    }

    fun create(title: String) = action {
        val room = api.create(StudyRoomCreateRequest(title.trim().ifBlank { "自习室" }))
        select(room)
    }
    fun join(id: String) = action { select(api.room(id)) }
    fun accept(id: String) = action { select(api.accept(id)) }
    fun decline(id: String) = action {
        api.decline(id)
        mutableState.update { it.copy(invitations = it.invitations.filterNot { inv -> inv.room_id == id }) }
    }
    fun invite(uid: String) = action {
        val room = mutableState.value.room ?: return@action
        api.invite(room.id, StudyRoomInviteRequest(uid.trim()))
        mutableState.update { it.copy(room = api.room(room.id), notice = "邀请已发送") }
    }
    fun setState(studyState: String, statusMessage: String?) = action {
        val room = mutableState.value.room ?: return@action
        api.setState(room.id, StudyRoomStateRequest(studyState, statusMessage?.takeIf { it.isNotBlank() }))
        mutableState.update { it.copy(room = api.room(room.id)) }
    }
    fun controlTimer(action: String, focusMinutes: Int? = null, breakMinutes: Int? = null) = action {
        val room = mutableState.value.room ?: return@action
        val updated = api.timer(room.id, StudyRoomTimerRequest(action, focusMinutes, breakMinutes))
        mutableState.update { it.copy(room = updated, fetchedAtElapsedMs = SystemClock.elapsedRealtime()) }
    }
    fun send(content: String) = action {
        val room = mutableState.value.room ?: return@action
        if (content.isBlank()) return@action
        api.send(room.id, StudyRoomMessageRequest(content.trim(), UUID.randomUUID().toString()))
        pullMessages(room.id)
    }
    fun leave() = action {
        val room = mutableState.value.room ?: return@action
        api.leave(room.id)
        select(null)
    }
    fun returnToList() { select(null) }
    fun clearNotice() = mutableState.update { it.copy(notice = null) }

    private fun readable(error: Exception): String = when (error) {
        is HttpException -> when (error.code()) {
            401 -> "登录已失效，请重新登录"
            403 -> "只有发起人可以操作计时器或邀请同学"
            404, 410 -> "自习室或邀请已失效，请返回列表"
            409 -> "人数已达上限或与当前状态冲突"
            422 -> "请检查输入内容"
            else -> "服务暂不可用，请稍后重试"
        }
        else -> "网络连接失败，请检查网络后重试"
    }

    override fun onCleared() { pollJob?.cancel(); super.onCleared() }
}

package com.example.campusai.ui.screens.classroom

import android.app.Application
import android.os.SystemClock
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.campusai.data.remote.ApiClient
import com.example.campusai.data.remote.StudyRoom
import com.example.campusai.data.remote.StudyRoomApi
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
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
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
    val pendingMessage: PendingRoomMessage? = null,
    val sentVersion: Int = 0,
    val sentRoomId: String? = null,
    val sentDraft: String? = null,
)

/**
 * 多人在线自习室（互相监督）——纯轮询，无音视频。
 * 与 [LearningRoomViewModel]（共同课堂）是两套能力：这里没有 RTC，只有
 * 成员在线状态、共享番茄钟与房内文字。
 *
 * 轮询的每次挂起调用都受 [epoch] 约束：返回后如果用户已换房、返回列表或换号，
 * 迟到的房间详情、消息、游标与错误都不会写回当前页面。房内消息复用
 * [MessageOutbox] 的待确认语义，重试沿用首次发送的 client_id 与正文。
 */
class StudyRoomViewModel @JvmOverloads constructor(
    application: Application,
    private val api: StudyRoomApi = ApiClient.studyRooms,
) : AndroidViewModel(application) {
    private val mutableState = MutableStateFlow(StudyRoomUiState())
    val state = mutableState.asStateFlow()
    private var pollJob: Job? = null
    private var visible = false
    private var cursor = 0L
    private var beatCounter = 0
    private var epoch = 0
    private val messageMutex = Mutex()
    private val messageOutbox = MessageOutbox()

    fun foreground(isVisible: Boolean) {
        visible = isVisible
        pollJob?.cancel()
        if (!isVisible) return
        pollJob = viewModelScope.launch {
            while (true) {
                pollOnce()
                delay(if (visible) 5_000 else 15_000)
            }
        }
    }

    private suspend fun pollOnce() {
        val selected = mutableState.value.room?.id
        val requestEpoch = epoch
        try {
            val identity = api.identity()
            if (epoch != requestEpoch) return
            val previousIdentity = mutableState.value.identity
            if (previousIdentity != null && previousIdentity.uid != identity.uid) {
                // 换号：旧账号的房间、消息、游标与待重试消息都不能留给新账号。
                messageOutbox.clear()
                select(null)
                mutableState.update {
                    it.copy(identity = identity, rooms = emptyList(), invitations = emptyList(), pendingMessage = null)
                }
                return
            }
            val rooms = api.rooms().items
            val invitations = api.invitations().items
            if (epoch != requestEpoch) return
            mutableState.update {
                it.copy(identity = identity, rooms = rooms, invitations = invitations, notice = null)
            }
            if (selected == null) return
            val room = api.room(selected)
            if (!isCurrent(requestEpoch, selected)) return
            mutableState.update { it.copy(room = room, fetchedAtElapsedMs = SystemClock.elapsedRealtime()) }
            pullMessages(selected, requestEpoch)
            if (!isCurrent(requestEpoch, selected)) return
            if (beatCounter % 3 == 0) {
                api.heartbeat(selected)
                if (!isCurrent(requestEpoch, selected)) return
            }
            beatCounter++
        } catch (error: CancellationException) {
            throw error
        } catch (error: Exception) {
            if (epoch != requestEpoch) return
            if (error is HttpException && error.code() == 401) {
                messageOutbox.clear()
                select(null)
                mutableState.update {
                    it.copy(
                        identity = null,
                        rooms = emptyList(),
                        invitations = emptyList(),
                        pendingMessage = null,
                        notice = readable(error),
                    )
                }
            } else if (selected != null && error is HttpException && error.code() in listOf(403, 404, 410)) {
                select(null)
                mutableState.update { it.copy(notice = readable(error)) }
            } else {
                mutableState.update { it.copy(notice = readable(error)) }
            }
        }
    }

    /**
     * 增量拉取；同房间的轮询与发送后补拉共享一把锁，游标与消息一起更新。
     * 返回后先核对代次，旧房间的迟到分页不能推进当前房间的游标。
     */
    private suspend fun pullMessages(roomId: String, requestEpoch: Int) {
        messageMutex.withLock {
            var after = cursor
            while (true) {
                val page = api.messages(roomId, after).items
                if (!isCurrent(requestEpoch, roomId)) return
                if (page.isNotEmpty()) {
                    val lastId = page.last().id
                    if (lastId > after) after = lastId
                    cursor = maxOf(cursor, lastId)
                    mutableState.update { current ->
                        if (current.room?.id != roomId) {
                            current
                        } else {
                            current.copy(
                                messages = (current.messages + page)
                                    .distinctBy { message -> message.id }
                                    .sortedBy { message -> message.id }
                                    .takeLast(300),
                            )
                        }
                    }
                }
                if (page.size < 100) return
            }
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
        epoch++
        cursor = 0L
        beatCounter = 0
        mutableState.update {
            it.copy(
                room = room,
                messages = emptyList(),
                fetchedAtElapsedMs = SystemClock.elapsedRealtime(),
                pendingMessage = room?.id?.let(messageOutbox::get),
            )
        }
    }

    private fun isCurrent(requestEpoch: Int, roomId: String? = null): Boolean =
        epoch == requestEpoch && (roomId == null || mutableState.value.room?.id == roomId)

    private fun identityChanged(expectedUid: String?): Boolean {
        val current = mutableState.value.identity?.uid
        return expectedUid != null && current != null && current != expectedUid
    }

    fun create(title: String) = action {
        val room = api.create(StudyRoomCreateRequest(title.trim().ifBlank { "自习室" }))
        select(room)
    }
    fun join(id: String) = action {
        val requestEpoch = epoch
        val room = api.room(id)
        if (epoch != requestEpoch) return@action
        select(room)
    }
    fun accept(id: String) = action {
        val requestEpoch = epoch
        val room = api.accept(id)
        if (epoch != requestEpoch) return@action
        select(room)
    }
    fun decline(id: String) = action {
        api.decline(id)
        mutableState.update { it.copy(invitations = it.invitations.filterNot { inv -> inv.room_id == id }) }
    }
    fun invite(uid: String) = action {
        val room = mutableState.value.room ?: return@action
        val requestEpoch = epoch
        api.invite(room.id, StudyRoomInviteRequest(uid.trim()))
        val updated = api.room(room.id)
        if (!isCurrent(requestEpoch, room.id)) return@action
        mutableState.update { it.copy(room = updated, notice = "邀请已发送") }
    }
    fun setState(studyState: String, statusMessage: String?) = action {
        val room = mutableState.value.room ?: return@action
        val requestEpoch = epoch
        api.setState(room.id, StudyRoomStateRequest(studyState, statusMessage?.takeIf { it.isNotBlank() }))
        val updated = api.room(room.id)
        if (!isCurrent(requestEpoch, room.id)) return@action
        mutableState.update { it.copy(room = updated) }
    }
    fun controlTimer(action: String, focusMinutes: Int? = null, breakMinutes: Int? = null) = action {
        val room = mutableState.value.room ?: return@action
        val requestEpoch = epoch
        val updated = api.timer(room.id, StudyRoomTimerRequest(action, focusMinutes, breakMinutes))
        if (!isCurrent(requestEpoch, room.id)) return@action
        mutableState.update { it.copy(room = updated, fetchedAtElapsedMs = SystemClock.elapsedRealtime()) }
    }
    fun send(content: String) = action {
        val room = mutableState.value.room ?: return@action
        if (content.isBlank()) return@action
        val attempt = messageOutbox.begin(room.id, content.trim(), UUID.randomUUID().toString(), content)
        if (attempt == null) {
            mutableState.update { it.copy(notice = "请先重试或放弃上一条发送结果不确定的消息") }
            return@action
        }
        mutableState.update { it.copy(pendingMessage = attempt) }
        deliver(attempt, epoch, mutableState.value.identity?.uid)
    }

    fun retryMessage() = action {
        val room = mutableState.value.room ?: return@action
        val attempt = messageOutbox.get(room.id) ?: return@action
        mutableState.update { it.copy(pendingMessage = attempt) }
        deliver(attempt, epoch, mutableState.value.identity?.uid)
    }

    fun discardPendingMessage() {
        val roomId = mutableState.value.room?.id ?: return
        messageOutbox.get(roomId)?.let(messageOutbox::remove)
        mutableState.update { it.copy(pendingMessage = null) }
    }

    /**
     * 服务端确认才清除草稿与待确认状态；网络不确定/5xx 保留原 client_id 供重试，
     * 4xx 明确拒绝则清掉待确认状态，让用户修改后重新发送。
     */
    private suspend fun deliver(attempt: PendingRoomMessage, requestEpoch: Int, accountUid: String?) {
        if (!isCurrent(requestEpoch, attempt.roomId) || identityChanged(accountUid)) return
        try {
            api.send(attempt.roomId, StudyRoomMessageRequest(attempt.draft.trim(), attempt.clientId))
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: HttpException) {
            if (isDefinitiveRejection(error.code())) {
                messageOutbox.remove(attempt)
                mutableState.update {
                    if (it.room?.id == attempt.roomId) it.copy(pendingMessage = null) else it
                }
            }
            throw error
        }
        messageOutbox.remove(attempt)
        if (!isCurrent(requestEpoch, attempt.roomId) || identityChanged(accountUid)) {
            // 请求已被服务端接受，但页面已换房/换号：不在新页面显示旧发送结果。
            return
        }
        mutableState.update {
            it.copy(
                sentVersion = it.sentVersion + 1,
                sentRoomId = attempt.roomId,
                sentDraft = attempt.rawDraft,
                pendingMessage = if (it.room?.id == attempt.roomId) null else it.pendingMessage,
            )
        }
        try {
            pullMessages(attempt.roomId, requestEpoch)
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Exception) {
            // POST 已成功；补拉失败由下一次轮询接手，不能回写成发送失败。
        }
    }

    private fun isDefinitiveRejection(code: Int): Boolean =
        code in 400..499 && code != 408 && code != 429

    fun leave() = action {
        val room = mutableState.value.room ?: return@action
        api.leave(room.id)
        messageOutbox.get(room.id)?.let(messageOutbox::remove)
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

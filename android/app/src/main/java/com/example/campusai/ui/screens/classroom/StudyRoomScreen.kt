package com.example.campusai.ui.screens.classroom

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.campusai.data.remote.StudyRoom
import com.example.campusai.data.remote.StudyRoomMember

private data class StateChip(val key: String, val label: String, val color: Color)
private val STUDY_STATES = listOf(
    StateChip("focus", "专注中", Color(0xFF5BD68F)),
    StateChip("break", "休息中", Color(0xFFF5A64A)),
    StateChip("away", "离开", Color(0xFF9AA4B2)),
    StateChip("idle", "待命", Color(0xFF7AA0FF)),
)

private fun stateLabel(state: String): String = STUDY_STATES.firstOrNull { it.key == state }?.label ?: "待命"
private fun stateColor(state: String): Color = STUDY_STATES.firstOrNull { it.key == state }?.color ?: Color(0xFF9AA4B2)
private fun mmss(totalSeconds: Int): String {
    val value = totalSeconds.coerceAtLeast(0)
    return "%02d:%02d".format(value / 60, value % 60)
}

/** 多人在线自习室（互相监督）：成员状态 + 共享番茄钟 + 房内鼓励，无音视频。 */
@Composable
fun StudyRoomScreen(onBack: () -> Unit, model: StudyRoomViewModel = viewModel()) {
    val state by model.state.collectAsStateWithLifecycle()
    val owner = LocalLifecycleOwner.current
    var title by remember { mutableStateOf("") }
    var inviteUid by remember(state.room?.id) { mutableStateOf("") }
    val drafts = remember { mutableStateMapOf<String, String>() }
    val roomKey = state.room?.id
    val draft = roomKey?.let { drafts[it].orEmpty() } ?: ""
    var statusMsg by remember(state.room?.id) { mutableStateOf("") }
    var confirmDiscardMessage by remember { mutableStateOf(false) }
    var nowTick by remember { mutableIntStateOf(0) }

    DisposableEffect(owner, model) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> model.foreground(true)
                Lifecycle.Event.ON_STOP -> model.foreground(false)
                else -> Unit
            }
        }
        owner.lifecycle.addObserver(observer)
        if (owner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) model.foreground(true)
        onDispose { owner.lifecycle.removeObserver(observer); model.foreground(false) }
    }

    LaunchedEffect(state.room?.timer?.phase, state.room?.timer?.paused) {
        while (true) { nowTick++; kotlinx.coroutines.delay(1000) }
    }

    LaunchedEffect(state.sentVersion) {
        // 只清掉本次发送的原文本；用户继续输入或其他房间的草稿都保留。
        val roomId = state.room?.id ?: return@LaunchedEffect
        if (state.sentVersion > 0 &&
            state.sentRoomId == roomId &&
            state.sentDraft == drafts[roomId].orEmpty()
        ) {
            drafts[roomId] = ""
        }
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).imePadding(),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 120.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            TextButton(onClick = onBack) { Text("返回") }
            Text("多人自习室", style = MaterialTheme.typography.headlineSmall)
            state.identity?.let { SelectionContainer { Text("我的 UID：${it.uid}") } }
            Text("和同学进同一个自习室，互相看见谁在专注、共用一个番茄钟、发一句鼓励。不开启摄像头或音视频。", style = MaterialTheme.typography.bodySmall)
        }
        state.notice?.let { message ->
            item {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
                    Row(Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text(message, color = MaterialTheme.colorScheme.onErrorContainer, modifier = Modifier.weight(1f))
                        TextButton(onClick = model::clearNotice) { Text("知道了") }
                    }
                }
            }
        }

        val room = state.room
        if (room == null) {
            item {
                OutlinedTextField(value = title, onValueChange = { title = it.take(200) }, label = { Text("自习室名称") }, modifier = Modifier.fillMaxWidth())
                Button(onClick = { model.create(title) }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("创建自习室") }
            }
            if (state.invitations.isNotEmpty()) {
                item { Text("待接受的邀请", style = MaterialTheme.typography.titleMedium) }
                items(state.invitations) { invitation ->
                    ListItem(
                        headlineContent = { Text("${invitation.host_name} 邀请你进入「${invitation.title}」") },
                        trailingContent = {
                            Row {
                                TextButton(onClick = { model.accept(invitation.room_id) }, enabled = !state.busy) { Text("接受") }
                                TextButton(onClick = { model.decline(invitation.room_id) }, enabled = !state.busy) { Text("拒绝") }
                            }
                        },
                    )
                }
            }
            if (state.rooms.isNotEmpty()) {
                item { Text("我的自习室", style = MaterialTheme.typography.titleMedium) }
                items(state.rooms) { summary ->
                    ListItem(
                        headlineContent = { Text(summary.title) },
                        supportingContent = { Text("${summary.member_count} 人") },
                        trailingContent = { TextButton(onClick = { model.join(summary.id) }, enabled = !state.busy) { Text("进入") } },
                    )
                }
            }
            if (state.rooms.isEmpty() && state.invitations.isEmpty()) {
                item { Text("创建自习室后，用同学的 UID 邀请他们加入。", style = MaterialTheme.typography.bodySmall) }
            }
        } else {
            item {
                val remaining = if (room.timer.running) {
                    val elapsed = ((android.os.SystemClock.elapsedRealtime() - state.fetchedAtElapsedMs) / 1000).toInt()
                    (room.timer.remaining_seconds - elapsed).coerceAtLeast(0)
                } else room.timer.remaining_seconds
                Text(room.title, style = MaterialTheme.typography.titleLarge)
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                    Column(Modifier.fillMaxWidth().padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            when (room.timer.phase) { "focus" -> "专注中"; "break" -> "休息中"; else -> "待开始" } + if (room.timer.paused) " · 已暂停" else "",
                            style = MaterialTheme.typography.labelMedium,
                        )
                        Text(mmss(remaining), style = MaterialTheme.typography.displaySmall)
                        Text("${room.focus_minutes} 分钟专注 / ${room.break_minutes} 分钟休息", style = MaterialTheme.typography.bodySmall)
                        Spacer(Modifier.height(8.dp))
                        TimerControls(room, state.identity?.uid == room.host_uid, state.busy) { action -> model.controlTimer(action) }
                    }
                }
            }
            item {
                Text("成员（${room.members.count { it.status == "accepted" }}）", style = MaterialTheme.typography.titleMedium)
            }
            items(room.members.filter { it.status == "accepted" }, key = { it.uid }) { member ->
                MemberRow(member, isHost = member.uid == room.host_uid)
            }
            item {
                Text("我的状态", style = MaterialTheme.typography.titleMedium)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    STUDY_STATES.forEach { chip ->
                        FilterChip(
                            selected = room.members.firstOrNull { it.uid == state.identity?.uid }?.study_state == chip.key,
                            onClick = { model.setState(chip.key, null) },
                            label = { Text(chip.label) },
                            enabled = !state.busy,
                        )
                    }
                }
                OutlinedTextField(value = statusMsg, onValueChange = { statusMsg = it.take(140) }, label = { Text("状态语（可选）") }, modifier = Modifier.fillMaxWidth())
                TextButton(onClick = { model.setState(STUDY_STATES.first().key, statusMsg) }, enabled = !state.busy) { Text("保存状态语") }
            }
            if (state.identity?.uid == room.host_uid) {
                item {
                    Text("邀请同学", style = MaterialTheme.typography.titleMedium)
                    OutlinedTextField(value = inviteUid, onValueChange = { inviteUid = it.take(128) }, label = { Text("同学 UID") }, modifier = Modifier.fillMaxWidth())
                    Button(onClick = { model.invite(inviteUid); inviteUid = "" }, enabled = !state.busy && inviteUid.isNotBlank()) { Text("邀请") }
                }
            }
            item {
                Text("互相鼓励", style = MaterialTheme.typography.titleMedium)
            }
            if (state.messages.isEmpty()) {
                item { Text("还没有消息，发一句鼓励吧。", style = MaterialTheme.typography.bodySmall) }
            } else {
                items(state.messages, key = { it.id }) { message ->
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(message.name, color = MaterialTheme.colorScheme.primary)
                        Text(message.content)
                    }
                }
            }
            item {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = draft,
                        onValueChange = { value -> if (roomKey != null) drafts[roomKey] = value.take(2000) },
                        label = { Text("说点什么鼓励大家…") },
                        modifier = Modifier.weight(1f),
                    )
                    Spacer(Modifier.width(8.dp))
                    Button(
                        onClick = { model.send(draft) },
                        enabled = !state.busy && draft.isNotBlank() && state.pendingMessage == null,
                    ) { Text("发送") }
                }
                state.pendingMessage?.let { pending ->
                    Text("上一条消息发送结果不确定，重试会使用原消息 ID：${pending.draft}")
                    TextButton(onClick = model::retryMessage, enabled = !state.busy) { Text("重试上一条消息") }
                    TextButton(onClick = { confirmDiscardMessage = true }, enabled = !state.busy) { Text("放弃重试") }
                }
                Spacer(Modifier.height(8.dp))
                OutlinedButton(onClick = model::leave, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) {
                    Text(if (state.identity?.uid == room.host_uid) "结束自习室" else "离开自习室")
                }
            }
        }
    }

    if (confirmDiscardMessage) AlertDialog(
        onDismissRequest = { confirmDiscardMessage = false },
        title = { Text("放弃这条消息？") },
        text = { Text("如果服务端其实已经收到，它仍会出现在房内记录里。放弃后可以用新的消息重新发送。") },
        confirmButton = {
            TextButton(onClick = { confirmDiscardMessage = false; model.discardPendingMessage() }) { Text("放弃重试") }
        },
        dismissButton = {
            TextButton(onClick = { confirmDiscardMessage = false }) { Text("继续重试") }
        },
    )
}

@Composable
private fun TimerControls(room: StudyRoom, isHost: Boolean, busy: Boolean, onControl: (String) -> Unit) {
    if (!isHost) { Text("由发起人控制计时", style = MaterialTheme.typography.bodySmall); return }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        when (room.timer.phase) {
            "idle" -> Button(onClick = { onControl("start_focus") }, enabled = !busy) { Text("开始专注") }
            "focus" -> {
                if (room.timer.paused) Button(onClick = { onControl("resume") }, enabled = !busy) { Text("继续") }
                else Button(onClick = { onControl("pause") }, enabled = !busy) { Text("暂停") }
                OutlinedButton(onClick = { onControl("start_break") }, enabled = !busy) { Text("开始休息") }
            }
            "break" -> {
                if (room.timer.paused) Button(onClick = { onControl("resume") }, enabled = !busy) { Text("继续") }
                else Button(onClick = { onControl("pause") }, enabled = !busy) { Text("暂停") }
            }
        }
        if (room.timer.phase != "idle") TextButton(onClick = { onControl("reset") }, enabled = !busy) { Text("重置") }
    }
}

@Composable
private fun MemberRow(member: StudyRoomMember, isHost: Boolean) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Surface(color = if (member.online) stateColor(member.study_state).copy(alpha = 0.22f) else Color(0x22808080), shape = MaterialTheme.shapes.small) {
            Text(
                if (member.online) stateLabel(member.study_state) else "离开",
                modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                style = MaterialTheme.typography.labelSmall,
            )
        }
        Text(member.name + if (isHost) "（发起人）" else "", modifier = Modifier.weight(1f))
        if (!member.online) Text("离开", style = MaterialTheme.typography.bodySmall)
        member.status_message.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
    }
}

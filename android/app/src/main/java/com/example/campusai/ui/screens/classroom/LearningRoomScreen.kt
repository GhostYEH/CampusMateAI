package com.example.campusai.ui.screens.classroom

import android.Manifest
import android.os.Build
import android.content.pm.PackageManager
import android.view.TextureView
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.campusai.CampusAIApplication
import com.example.campusai.data.classroom.ClassroomCall
import com.example.campusai.data.classroom.ClassroomCallPhase
import com.example.campusai.data.focus.voice.AndroidTextToSpeechSynthesizer
import com.example.campusai.data.remote.LearningSupervision
import com.example.campusai.data.remote.LearningTeacherNudge
import com.example.campusai.ui.components.SpeechInputButton

@Composable
fun LearningRoomScreen(onBack: () -> Unit, model: LearningRoomViewModel = viewModel()) {
    val state by model.state.collectAsStateWithLifecycle()
    val call by model.call.state.collectAsStateWithLifecycle()
    val owner = LocalLifecycleOwner.current
    val context = LocalContext.current
    var title by remember { mutableStateOf("") }
    var inviteUid by remember(state.room?.id) { mutableStateOf("") }
    var draft by remember(state.room?.id) { mutableStateOf("") }
    var speechNotice by remember(state.room?.id) { mutableStateOf<String?>(null) }
    var confirmLeave by remember { mutableStateOf(false) }
    var confirmDiscardMessage by remember { mutableStateOf(false) }
    var microphoneRequestRoom by remember { mutableStateOf<String?>(null) }
    var cameraRequestRoom by remember { mutableStateOf<String?>(null) }
    var microphoneRequestSession by remember { mutableStateOf(-1) }
    var cameraRequestSession by remember { mutableStateOf(-1) }
    var notificationRequestRoom by remember { mutableStateOf<String?>(null) }
    val connected = call.phase == ClassroomCallPhase.CONNECTED
    val notificationPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (notificationRequestRoom == state.room?.id && owner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) {
            if (!granted) model.notice("通知权限未开启，通话期间可在系统的活动应用中停止服务")
            model.connect()
        }
    }
    val micPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted && microphoneRequestRoom == state.room?.id && microphoneRequestSession == model.call.sessionGeneration && owner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED) && model.call.state.value.phase == ClassroomCallPhase.CONNECTED) model.microphone(true)
        else if (!granted) model.notice("未获得麦克风权限，仍可听课或使用摄像头")
    }
    val cameraPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted && cameraRequestRoom == state.room?.id && cameraRequestSession == model.call.sessionGeneration && owner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED) && model.call.state.value.phase == ClassroomCallPhase.CONNECTED) model.call.camera(true)
        else if (!granted) model.notice("未获得摄像头权限，仍可参加语音讨论")
    }
    val attentionPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) model.setAttentionEnabled(true, true)
        else model.notice("未获得摄像头权限，无法开启课堂专注观察")
    }
    val teacherSpeech = remember(context) { AndroidTextToSpeechSynthesizer(context) }
    DisposableEffect(teacherSpeech) { onDispose { teacherSpeech.shutdown() } }
    var lastSpokenNudgeId by remember { mutableStateOf(0L) }
    LaunchedEffect(state.teacherReminder?.id) {
        val nudge = state.teacherReminder ?: return@LaunchedEffect
        if (nudge.id == lastSpokenNudgeId) return@LaunchedEffect
        lastSpokenNudgeId = nudge.id
        // 课堂麦克风开着时不要朗读私人提醒，避免被 RTC 其他同学听到；文字卡片仍然可见。
        if (!call.microphone) {
            teacherSpeech.speak(nudge.content, onDone = {}, onError = {})
        }
    }
    DisposableEffect(owner, model) {
        (context.applicationContext as? CampusAIApplication)?.repository?.expressionSessionManager
            ?.attachLifecycle(owner)
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> model.foreground(true)
                Lifecycle.Event.ON_STOP -> model.foreground(false)
                else -> Unit
            }
        }
        owner.lifecycle.addObserver(observer)
        if (owner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) model.foreground(true)
        onDispose {
            owner.lifecycle.removeObserver(observer)
            model.foreground(false)
            model.setAttentionEnabled(false, true)
            (context.applicationContext as? CampusAIApplication)?.repository?.expressionSessionManager
                ?.detachLifecycle()
        }
    }
    LaunchedEffect(state.sentVersion) {
        // A send can finish after the user has started another message or changed rooms.
        if (state.sentVersion > 0 && state.sentRoomId == state.room?.id && state.sentDraft == draft) {
            draft = ""
        }
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).imePadding(),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 120.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            TextButton(onClick = onBack) { Text("返回") }
            Text("同学一起学", style = MaterialTheme.typography.headlineSmall)
            state.identity?.let { SelectionContainer { Text("我的 UID：${it.uid}") } }
            Text("最多 8 人自由讨论；麦克风和摄像头由你分别开启。", style = MaterialTheme.typography.bodySmall)
        }
        state.notice?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
        state.rtcStatus?.takeUnless { it.available }?.let { item { Text(it.reason ?: "音视频暂不可用，可继续文字讨论") } }
        if (state.room == null) {
            item {
                OutlinedTextField(value = title, onValueChange = { title = it.take(200) }, label = { Text("讨论课堂名称") }, modifier = Modifier.fillMaxWidth())
                Button(onClick = { model.create(title) }, enabled = !state.busy && title.isNotBlank()) { Text("创建共同课堂") }
            }
            items(state.invitations, key = { "invite:${it.room_id}" }) { invitation ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text("${invitation.host_name} 邀请你：${invitation.title}")
                        Row {
                            Button(onClick = { model.join(invitation.room_id, true) }, enabled = !state.busy) { Text("接受并加入") }
                            TextButton(onClick = { model.decline(invitation.room_id) }, enabled = !state.busy) { Text("拒绝") }
                        }
                    }
                }
            }
            items(state.rooms, key = { "room:${it.id}" }) { room ->
                OutlinedButton(onClick = { model.join(room.id) }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("进入：${room.title}") }
            }
            if (state.rooms.isEmpty() && state.invitations.isEmpty()) item { Text("创建课堂后，用同学的 UID 邀请他们加入。") }
        } else {
            val room = checkNotNull(state.room)
            val host = room.host_uid == state.identity?.uid
            item {
                Text(room.title, style = MaterialTheme.typography.titleLarge)
                Text(when (call.phase) {
                    ClassroomCallPhase.OFF -> "尚未连接通话"
                    ClassroomCallPhase.CONNECTING -> "正在连接…"
                    ClassroomCallPhase.CONNECTED -> "通话中"
                    ClassroomCallPhase.RECONNECTING -> "网络中断，正在重连…"
                    ClassroomCallPhase.ERROR -> call.error ?: "连接失败"
                })
                call.rttMs?.let { Text("网络往返 ${it}ms${if (call.weakNetwork) " · 网络较弱，优先保证声音" else ""}", style = MaterialTheme.typography.bodySmall) }
                // RTT is a network diagnostic, not the measured mouth-to-ear delay.
                if (call.phase in listOf(ClassroomCallPhase.OFF, ClassroomCallPhase.ERROR)) {
                    Button(onClick = {
                        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                            notificationRequestRoom = room.id
                            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                        } else model.connect()
                    }, enabled = state.rtcStatus?.available == true) { Text("加入音视频通话") }
                    Text("入会时麦克风、摄像头均关闭。后台保留通话声音并关闭摄像头。", style = MaterialTheme.typography.bodySmall)
                } else TextButton(onClick = model::disconnect) { Text("断开通话，继续文字学习") }
                call.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
            state.teacherReminder?.let { nudge ->
                item { TeacherNudgeCard(nudge, onDismiss = model::dismissTeacherReminder) }
            }
            item {
                ClassroomSupervisionCard(
                    host = host,
                    attentionEnabled = state.attentionEnabled,
                    attentionState = state.attentionState,
                    supervision = state.supervision,
                    onToggle = {
                        if (state.attentionEnabled) model.setAttentionEnabled(false, true)
                        else if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                            model.setAttentionEnabled(true, true)
                        } else attentionPermission.launch(Manifest.permission.CAMERA)
                    },
                    onNudge = { uid -> model.sendNudge(uid) },
                    onBroadcast = { model.sendNudge(null) },
                )
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(enabled = connected || call.microphone, onClick = {
                        if (call.microphone) model.microphone(false)
                        else if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) model.microphone(true)
                        else { microphoneRequestRoom = room.id; microphoneRequestSession = model.call.sessionGeneration; micPermission.launch(Manifest.permission.RECORD_AUDIO) }
                    }) { Text(if (call.microphone) "关闭麦克风" else "开启麦克风") }
                    Button(enabled = connected || call.camera, onClick = {
                        if (call.camera) model.call.camera(false)
                        else if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) model.call.camera(true)
                        else { cameraRequestRoom = room.id; cameraRequestSession = model.call.sessionGeneration; cameraPermission.launch(Manifest.permission.CAMERA) }
                    }) { Text(if (call.camera) "关闭摄像头" else "开启摄像头") }
                }
                if (call.camera) TextButton(onClick = model.call::switchCamera) { Text("切换前后摄像头") }
            }
            item {
                VideoTile(model.call, "self", "我${if (call.microphone) " · 麦克风已开" else " · 已静音"}", call.camera)
            }
            items(room.members.filter { it.uid != state.identity?.uid }, key = { "peer:${it.uid}" }) { member ->
                val peer = call.peers[member.uid]
                val status = when {
                    member.status == "pending" -> "等待接受邀请"
                    peer == null && !connected -> "加入通话后可查看通话状态"
                    peer == null -> "未观察到通话状态"
                    peer.audio -> "麦克风已开"
                    else -> "已静音"
                }
                VideoTile(model.call, member.uid, "${member.name} · $status", peer?.video == true,
                    if (peer == null) "暂无视频状态" else "摄像头关闭")
            }
            if (host) item {
                OutlinedTextField(value = inviteUid, onValueChange = { inviteUid = it.take(128) }, label = { Text("同学 UID") }, modifier = Modifier.fillMaxWidth())
                Button(onClick = { model.invite(inviteUid) }, enabled = !state.busy && inviteUid.isNotBlank()) { Text("邀请同学") }
            }
            if (room.scene_count > 1) item {
                Text("共享课件页码：${room.scene_index + 1} / ${room.scene_count}（完整课件请在学习空间查看）")
                if (host) Row {
                    TextButton(onClick = { model.page(room.scene_index - 1) }, enabled = !state.busy && room.scene_index > 0) { Text("上一页") }
                    TextButton(onClick = { model.page(room.scene_index + 1) }, enabled = !state.busy && room.scene_index + 1 < room.scene_count) { Text("下一页") }
                }
            }
            items(state.messages, key = { "message:${it.id}" }) { message ->
                Text("${message.name}：${message.content}")
            }
            item {
                Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    OutlinedTextField(value = draft, onValueChange = { draft = it.take(2000) }, label = { Text("课堂文字消息") }, modifier = Modifier.weight(1f))
                    SpeechInputButton(
                        onText = { text -> speechNotice = null; draft = (draft + text).take(2000) },
                        onMessage = { message -> speechNotice = message },
                        enabled = !state.busy && state.pendingMessage == null,
                    )
                }
                speechNotice?.let { Text(it, color = Color(0xFF8A8A8A), style = MaterialTheme.typography.bodySmall) }
                Button(onClick = { model.send(draft) }, enabled = !state.busy && draft.isNotBlank() && state.pendingMessage == null) { Text("发送") }
                state.pendingMessage?.let { pending ->
                    Text("上一条消息发送结果不确定，重试会使用原消息 ID：${pending.draft}")
                    TextButton(onClick = model::retryMessage, enabled = !state.busy) { Text("重试上一条消息") }
                    TextButton(onClick = { confirmDiscardMessage = true }, enabled = !state.busy) { Text("放弃重试") }
                }
                TextButton(onClick = model::returnToList, enabled = !state.busy) { Text("断开通话并返回课堂列表") }
                TextButton(onClick = { confirmLeave = true }, enabled = !state.busy) { Text(if (host) "结束共同课堂" else "退出共同课堂") }
            }
        }
    }
    if (confirmLeave) AlertDialog(
        onDismissRequest = { confirmLeave = false },
        title = { Text(if (state.room?.host_uid == state.identity?.uid) "结束所有同学的课堂？" else "退出课堂？") },
        text = { Text("退出后需要重新接受邀请才能加入；发起人结束后，所有同学都会离开。") },
        confirmButton = { TextButton(onClick = { confirmLeave = false; model.leave() }) { Text("确认") } },
        dismissButton = { TextButton(onClick = { confirmLeave = false }) { Text("取消") } },
    )
    if (confirmDiscardMessage) AlertDialog(
        onDismissRequest = { confirmDiscardMessage = false },
        title = { Text("放弃重试这条消息？") },
        text = { Text("服务器可能已经收到这条消息。放弃后再次发送相同内容可能产生重复。") },
        confirmButton = { TextButton(onClick = { confirmDiscardMessage = false; model.discardPendingMessage() }) { Text("放弃重试") } },
        dismissButton = { TextButton(onClick = { confirmDiscardMessage = false }) { Text("取消") } },
    )
}

@Composable
private fun TeacherNudgeCard(nudge: LearningTeacherNudge, onDismiss: () -> Unit) {
    Surface(
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.tertiaryContainer,
        tonalElevation = 4.dp,
    ) {
        Row(Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Box(
                Modifier.size(36.dp).background(MaterialTheme.colorScheme.tertiary.copy(alpha = .25f), CircleShape),
                contentAlignment = Alignment.Center,
            ) { Text("师", fontWeight = FontWeight.Bold) }
            Column(Modifier.weight(1f)) {
                Text(
                    if (nudge.kind == "TEACHER") "小伴老师提醒" else "老师提醒",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(nudge.content, style = MaterialTheme.typography.bodyMedium)
                TextButton(onClick = onDismiss, contentPadding = PaddingValues(0.dp)) { Text("知道了") }
            }
        }
    }
}

@Composable
private fun ClassroomSupervisionCard(
    host: Boolean,
    attentionEnabled: Boolean,
    attentionState: String,
    supervision: LearningSupervision?,
    onToggle: () -> Unit,
    onNudge: (String) -> Unit,
    onBroadcast: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("课堂专注监督", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(
                "端侧只上报“专注/可能分心/明显分心/离开”这类粗粒度状态，不上传画面、人脸或音频。",
                style = MaterialTheme.typography.bodySmall,
            )
            if (attentionEnabled) {
                Text("我的状态：${attentionLabel(attentionState)}，${if (attentionState == "UNKNOWN") "等待本机观察" else "约 15 秒更新一次"}")
                OutlinedButton(onClick = onToggle) { Text("关闭专注观察") }
            } else {
                Text("我的状态：状态未知（仅同步在线）")
                Button(onClick = onToggle) { Text("开启课堂专注观察") }
                Text("进入课堂会同步在线状态；开启后才用摄像头做本机识别，画面不会上传。", style = MaterialTheme.typography.bodySmall)
            }
            if (host) {
                supervision?.teacher_summary?.let { Text(it, fontWeight = FontWeight.Medium) }
                supervision?.stats?.let { stats ->
                    Text(
                        "在线 ${stats.online}/${stats.total} · 专注 ${stats.focused} · 需提醒 ${stats.needs_attention}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                val others = supervision?.members.orEmpty().filterNot { it.is_host }
                if (others.isEmpty()) {
                    Text("等待同学进入课堂；未开启观察的同学会显示“状态未知”，但仍可看到在线。", style = MaterialTheme.typography.bodySmall)
                } else {
                    others.forEach { member ->
                        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                            Column(Modifier.weight(1f)) {
                                Text(member.name.ifBlank { member.uid }, fontWeight = FontWeight.Medium)
                                Text(
                                    "${attentionLabel(member.state)} · ${if (member.online) "在线" else "状态超时"}",
                                    style = MaterialTheme.typography.bodySmall,
                                )
                            }
                            TextButton(onClick = { onNudge(member.uid) }) { Text("提醒") }
                        }
                    }
                    TextButton(onClick = onBroadcast) { Text("提醒全班") }
                }
            } else {
                Text("发起人只能看到粗粒度状态；老师提醒只发送给被提醒的同学。", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

private fun attentionLabel(state: String): String = when (state) {
    "FOCUSED" -> "专注听课"
    "POSSIBLY_DISTRACTED" -> "可能分心"
    "DISTRACTED" -> "明显分心"
    "AWAY" -> "暂时离开"
    else -> "状态未知"
}

@Composable
private fun VideoTile(call: ClassroomCall, uid: String, label: String, video: Boolean, noVideoText: String = "摄像头关闭") {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(8.dp)) {
            Text(label)
            if (video) {
                AndroidView(
                    factory = { TextureView(it).also { view -> call.bindVideo(uid, view) } },
                    modifier = Modifier.fillMaxWidth().height(170.dp).background(Color.Black),
                    onRelease = { call.unbindVideo(uid, it) },
                    update = { call.bindVideo(uid, it) },
                )
            } else Text(noVideoText, modifier = Modifier.padding(vertical = 20.dp))
        }
    }
}

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
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.campusai.data.classroom.ClassroomCall
import com.example.campusai.data.classroom.ClassroomCallPhase

@Composable
fun LearningRoomScreen(onBack: () -> Unit, model: LearningRoomViewModel = viewModel()) {
    val state by model.state.collectAsStateWithLifecycle()
    val call by model.call.state.collectAsStateWithLifecycle()
    val owner = LocalLifecycleOwner.current
    val context = LocalContext.current
    var title by remember { mutableStateOf("") }
    var inviteUid by remember(state.room?.id) { mutableStateOf("") }
    var draft by remember(state.room?.id) { mutableStateOf("") }
    var confirmLeave by remember { mutableStateOf(false) }
    var microphoneRequestRoom by remember { mutableStateOf<String?>(null) }
    var cameraRequestRoom by remember { mutableStateOf<String?>(null) }
    var notificationRequestRoom by remember { mutableStateOf<String?>(null) }
    val connected = call.phase == ClassroomCallPhase.CONNECTED
    val notificationPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (notificationRequestRoom == state.room?.id && owner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) {
            if (!granted) model.notice("通知权限未开启，通话期间可在系统的活动应用中停止服务")
            model.connect()
        }
    }
    val micPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted && microphoneRequestRoom == state.room?.id && owner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED) && model.call.state.value.phase == ClassroomCallPhase.CONNECTED) model.microphone(true)
        else if (!granted) model.notice("未获得麦克风权限，仍可听课或使用摄像头")
    }
    val cameraPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted && cameraRequestRoom == state.room?.id && owner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED) && model.call.state.value.phase == ClassroomCallPhase.CONNECTED) model.call.camera(true)
        else if (!granted) model.notice("未获得摄像头权限，仍可参加语音讨论")
    }
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
    LaunchedEffect(state.sentVersion) { if (state.sentVersion > 0) draft = "" }

    LazyColumn(
        modifier = Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 120.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            TextButton(onClick = onBack) { Text("返回课程") }
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
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(enabled = connected, onClick = {
                        if (call.microphone) model.microphone(false)
                        else if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) model.microphone(true)
                        else { microphoneRequestRoom = room.id; micPermission.launch(Manifest.permission.RECORD_AUDIO) }
                    }) { Text(if (call.microphone) "关闭麦克风" else "开启麦克风") }
                    Button(enabled = connected, onClick = {
                        if (call.camera) model.call.camera(false)
                        else if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) model.call.camera(true)
                        else { cameraRequestRoom = room.id; cameraPermission.launch(Manifest.permission.CAMERA) }
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
                    peer == null -> "未连接通话"
                    peer.audio -> "麦克风已开"
                    else -> "已静音"
                }
                VideoTile(model.call, member.uid, "${member.name} · $status", peer?.video == true)
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
                OutlinedTextField(value = draft, onValueChange = { draft = it.take(2000) }, label = { Text("课堂文字消息") }, modifier = Modifier.fillMaxWidth())
                Button(onClick = { model.send(draft) }, enabled = !state.busy && draft.isNotBlank()) { Text("发送") }
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
}

@Composable
private fun VideoTile(call: ClassroomCall, uid: String, label: String, video: Boolean) {
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
            } else Text("摄像头关闭", modifier = Modifier.padding(vertical = 20.dp))
        }
    }
}

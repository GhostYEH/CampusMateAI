package com.example.campusai.ui.screens.courses

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.campusai.BuildConfig
import com.example.campusai.R
import com.example.campusai.data.remote.ClassroomUrlPolicy
import com.example.campusai.data.remote.InteractiveClassroomItemDto
import com.example.campusai.data.remote.InteractiveClassroomSessionDto
import com.example.campusai.data.remote.InteractiveClassroomStatusDto
import com.example.campusai.data.repository.AppRepository
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private val midnight = Color(0xFF172747)
private val paper = Color(0xFFFFECD0)

@Composable
fun ClassroomHubScreen(repository: AppRepository, onBack: () -> Unit, onOpenCourses: () -> Unit) {
    var topic by rememberSaveable { mutableStateOf("") }
    var sessionId by rememberSaveable { mutableStateOf<String?>(null) }
    var status by remember { mutableStateOf<InteractiveClassroomStatusDto?>(null) }
    var history by remember { mutableStateOf<List<InteractiveClassroomItemDto>>(emptyList()) }
    var progress by remember { mutableStateOf<InteractiveClassroomSessionDto?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var submitting by remember { mutableStateOf(false) }
    var viewerUrl by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val online by repository.backendOnline.collectAsStateWithLifecycle()

    LaunchedEffect(online) {
        status = repository.selfClassroomStatus()
        history = repository.selfClassroomHistory()
    }
    LaunchedEffect(sessionId) {
        val id = sessionId ?: return@LaunchedEffect
        repeat(180) {
            delay(5000)
            repository.selfClassroomJob(id)
                .onSuccess { job ->
                    progress = job
                    if (job.terminal) {
                        history = repository.selfClassroomHistory()
                        sessionId = null
                        return@LaunchedEffect
                    }
                }
                .onFailure { error = it.message ?: "课堂进度读取失败" }
        }
        error = "生成时间较长，可稍后回到教室查看历史课堂。"
    }
    fun trusted(url: String?): String? = ClassroomUrlPolicy.sanitize(
        url, listOf(status?.embedOrigin), allowEmulatorDebug = BuildConfig.DEBUG)

    Box(Modifier.fillMaxSize().background(midnight)) {
        Image(painterResource(R.drawable.campus_twilight_original), contentDescription = null,
            modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
        Box(Modifier.fillMaxSize().background(Brush.verticalGradient(
            listOf(Color(0xA9182444), Color(0x55182444), Color(0xED111E38)))))
        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding()
            .verticalScroll(rememberScrollState()).padding(horizontal = 20.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, contentDescription = "返回校园", tint = Color.White) }
                Text("互动课堂", color = Color.White, fontSize = 22.sp, fontWeight = FontWeight.Bold)
            }
            Spacer(Modifier.height(155.dp))
            Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(25.dp))
                .background(Color(0xF6FFF5E6)).padding(20.dp), verticalArrangement = Arrangement.spacedBy(13.dp)) {
                Text("今天想学什么？", color = midnight, fontSize = 23.sp, fontWeight = FontWeight.Bold)
                Text("给我一个主题，我会为你生成一节可互动的课。", color = Color(0xFF58647A), fontSize = 13.sp)
                if (status?.enabled == true && status?.capabilities?.get("tts") != true) {
                    Text("服务器语音暂不可用；进入课堂后可点右上角“朗读”使用手机语音。",
                        color = Color(0xFF815B4B), fontSize = 12.sp)
                }
                OutlinedTextField(value = topic, onValueChange = { topic = it.take(500) },
                    modifier = Modifier.fillMaxWidth(), minLines = 3, maxLines = 5,
                    placeholder = { Text("例如：从零学 Linux 文件权限，边讲边练") },
                    label = { Text("自主学习主题") })
                Button(onClick = {
                    if (topic.isBlank()) { error = "请先输入想学的内容"; return@Button }
                    submitting = true; error = null
                    scope.launch {
                        repository.generateSelfClassroom(topic)
                            .onSuccess { response ->
                                progress = response.session
                                sessionId = response.session.sessionId
                            }
                            .onFailure { error = it.message ?: "课堂生成失败" }
                        submitting = false
                    }
                }, enabled = !submitting && sessionId == null && status?.enabled == true && status?.browserEmbedAvailable == true,
                    modifier = Modifier.fillMaxWidth(), colors = ButtonDefaults.buttonColors(containerColor = midnight)) {
                    Text(if (submitting) "正在提交…" else "进入课堂")
                }
                if (status?.enabled != true || status?.browserEmbedAvailable != true) Text(
                    status?.reason ?: status?.browserEmbedReason ?: "课堂服务暂时不可用，请检查连接。",
                    color = Color(0xFF974D42), fontSize = 12.sp)
                progress?.let { job ->
                    Text(if (job.terminal) job.message ?: job.status else "正在生成 · ${job.progress}% · ${job.message.orEmpty()}",
                        color = midnight, fontSize = 13.sp)
                    trusted(job.url)?.let { safe ->
                        Text("打开已生成的课堂", color = Color(0xFF1C675B), fontWeight = FontWeight.Bold,
                            modifier = Modifier.clickable { viewerUrl = safe }.padding(vertical = 8.dp))
                    }
                }
                error?.let { Text(it, color = Color(0xFF974D42), fontSize = 12.sp) }
            }
            Spacer(Modifier.height(16.dp))
            Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp))
                .background(Color(0xE91B3151)).padding(20.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
                Text("用课程资料上课", color = paper, fontSize = 19.sp, fontWeight = FontWeight.Bold)
                Text("到图书馆打开一门课程，勾选资料后建立课堂。", color = Color.White, fontSize = 13.sp)
                Text("去图书馆  →", color = paper, fontWeight = FontWeight.Bold,
                    modifier = Modifier.clickable(onClick = onOpenCourses).padding(vertical = 8.dp))
            }
            if (history.isNotEmpty()) {
                Spacer(Modifier.height(20.dp))
                Text("最近的自主课堂", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                history.take(4).forEach { item ->
                    val safe = trusted(item.url)
                    val label = item.createdAt?.take(10) ?: "最近课堂"
                    Text(if (safe == null) "$label · 暂不可打开" else "$label · 继续上课  →",
                        color = paper, modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)
                            .clip(RoundedCornerShape(14.dp)).background(Color(0xCF1B3151))
                            .clickable(enabled = safe != null) { viewerUrl = safe }.padding(14.dp))
                }
            }
            Spacer(Modifier.height(28.dp))
        }
    }
    viewerUrl?.let { ClassroomViewer(it) { viewerUrl = null } }
}

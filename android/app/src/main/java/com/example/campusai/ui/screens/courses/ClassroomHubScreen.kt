package com.example.campusai.ui.screens.courses

import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.campusai.BuildConfig
import com.example.campusai.data.remote.ClassroomUrlPolicy
import com.example.campusai.data.remote.InteractiveClassroomSessionDto
import com.example.campusai.data.remote.InteractiveClassroomStatusDto
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.ClassroomHistoryEntry
import kotlinx.coroutines.delay
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream

private data class RecentClassroom(
    val entry: ClassroomHistoryEntry,
    val lastEnteredAt: String?,
    val totalSeconds: Long,
)

@Composable
fun ClassroomHubScreen(repository: AppRepository, onBack: () -> Unit,
    onOpenCourses: () -> Unit, onOpenHistory: () -> Unit) {
    var topic by rememberSaveable { mutableStateOf("") }
    var teachingStyle by rememberSaveable { mutableStateOf("循序讲解") }
    var selectedMaterialId by rememberSaveable { mutableStateOf<String?>(null) }
    var selectedMaterialName by rememberSaveable { mutableStateOf<String?>(null) }
    var uploading by remember { mutableStateOf(false) }
    var sessionId by rememberSaveable { mutableStateOf<String?>(null) }
    var status by remember { mutableStateOf<InteractiveClassroomStatusDto?>(null) }
    var statusLoading by remember { mutableStateOf(true) }
    var statusError by remember { mutableStateOf<String?>(null) }
    var statusRefresh by remember { mutableIntStateOf(0) }
    var history by remember { mutableStateOf<List<RecentClassroom>>(emptyList()) }
    var historyLoading by remember { mutableStateOf(true) }
    var historyRefresh by remember { mutableIntStateOf(0) }
    var progress by remember { mutableStateOf<InteractiveClassroomSessionDto?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var submitting by remember { mutableStateOf(false) }
    var viewerUrl by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val pickMaterial = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) scope.launch {
            uploading = true; error = null
            try {
                val (filename, bytes) = withContext(Dispatchers.IO) {
                    val resolver = context.contentResolver
                    val name = resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
                        ?.use { if (it.moveToFirst()) it.getString(0) else null } ?: "学习资料.txt"
                    val data = resolver.openInputStream(uri)?.use { input ->
                        val output = ByteArrayOutputStream()
                        val chunk = ByteArray(8192)
                        while (true) {
                            val read = input.read(chunk)
                            if (read < 0) break
                            output.write(chunk, 0, read)
                            if (output.size() > 2 * 1024 * 1024) throw IllegalArgumentException("单份资料不能超过 2 MB")
                        }
                        output.toByteArray()
                    } ?: throw IllegalArgumentException("无法读取所选文件")
                    name to data
                }
                repository.uploadSelfClassroomMaterial(filename, bytes)
                    .onSuccess { material ->
                        if (material.extractionStatus == "extracted" && material.textChars > 0) {
                            selectedMaterialId = material.id
                            selectedMaterialName = material.filename
                        } else error = "资料已上传，但正文尚未提取，暂不能用于课堂。"
                    }.onFailure { error = it.message ?: "上传失败" }
            } catch (failure: Exception) { error = failure.message ?: "无法读取文件" }
            uploading = false
        }
    }
    val online by repository.backendOnline.collectAsStateWithLifecycle()

    LaunchedEffect(online, historyRefresh, statusRefresh) {
        historyLoading = true
        statusLoading = true
        repository.selfClassroomStatusResult()
            .onSuccess { status = it; statusError = null }
            .onFailure { status = null; statusError = it.message ?: "课堂状态读取失败，请重试" }
        statusLoading = false
        repository.refreshCourses()
        val entryTimes = repository.classroomEntryTimes()
        val visits = repository.classroomStudyVisits().groupBy { it.classroomFingerprint }
        history = repository.allClassroomHistory().map { entry ->
            val fingerprint = entry.classroom.url?.let(repository::classroomVisitFingerprint)
            RecentClassroom(entry, fingerprint?.let(entryTimes::get),
                fingerprint?.let { visits[it].orEmpty().sumOf { visit -> visit.activeSeconds } } ?: 0L)
        }.sortedByDescending { it.lastEnteredAt ?: it.entry.classroom.createdAt.orEmpty() }
        historyLoading = false
    }
    LaunchedEffect(sessionId) {
        val id = sessionId ?: return@LaunchedEffect
        repeat(180) {
            delay(5000)
            repository.selfClassroomJob(id)
                .onSuccess { job ->
                    progress = job
                    if (job.terminal) {
                        historyRefresh++
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
    fun startClassroom() {
        if (topic.isBlank() && selectedMaterialId == null) {
            error = "请输入学习主题，或先上传一份资料"
            return
        }
        submitting = true
        error = null
        scope.launch {
            val objective = topic.trim().ifBlank { "围绕上传资料讲解重点并带我练习" }
            repository.generateSelfClassroom("请以${teachingStyle}的方式授课。学习主题：$objective",
                selectedMaterialId?.let { listOf(it) } ?: emptyList())
                .onSuccess { response ->
                    progress = response.session
                    sessionId = response.session.sessionId
                }
                .onFailure { error = it.message ?: "课堂生成失败" }
            submitting = false
        }
    }

    Box(Modifier.fillMaxSize()) {
        ClassroomStageBackdrop(Modifier.matchParentSize())
        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding()) {
            Column(Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp)) {
                Row(Modifier.fillMaxWidth().padding(top = 16.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onBack, modifier = Modifier.size(54.dp).clip(CircleShape)
                        .background(Color(0xB21A3440))
                        .border(1.dp, ClassroomWood.copy(alpha = .7f), CircleShape)) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "返回校园", tint = ClassroomChalk)
                    }
                    Spacer(Modifier.width(12.dp))
                    Column {
                        Text("互动课堂", color = ClassroomChalk, fontSize = 23.sp, fontWeight = FontWeight.Bold)
                        Text("选好主题，走进你的课堂", color = ClassroomChalk.copy(alpha = .8f), fontSize = 12.sp)
                    }
                }
                Spacer(Modifier.height(28.dp))
                LessonBlackboard(
                    topic = topic,
                    onTopicChange = { topic = it },
                    teachingStyle = teachingStyle,
                    onTeachingStyleChange = { teachingStyle = it },
                    materialName = selectedMaterialName,
                    uploading = uploading,
                    onPickMaterial = {
                        pickMaterial.launch(arrayOf("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain", "text/markdown"))
                    },
                    onRemoveMaterial = { selectedMaterialId = null; selectedMaterialName = null },
                )
                if (statusLoading || statusError != null || status?.enabled != true || status?.browserEmbedAvailable != true) {
                    Text(when {
                        statusLoading -> "正在检查课堂服务…"
                        statusError != null -> statusError!!
                        else -> status?.reason ?: status?.browserEmbedReason ?: "互动课堂服务暂不可用"
                    },
                        color = Color(0xFFFFBBA1), fontSize = 12.sp,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 12.dp))
                    if (!statusLoading) {
                        Text("重试 →", color = ClassroomAmber, fontSize = 12.sp,
                            modifier = Modifier.clickable {
                                scope.launch {
                                    if (!online) repository.refreshBackendStatus()
                                    statusRefresh++
                                }
                            }.padding(horizontal = 8.dp, vertical = 4.dp))
                    }
                }
                progress?.let { job ->
                    Text(if (job.terminal) job.message ?: job.status else "正在生成 · ${job.progress}% · ${job.message.orEmpty()}",
                        color = ClassroomChalk, fontSize = 13.sp,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 12.dp))
                    trusted(job.url)?.let { safe ->
                        Text("打开已生成的课堂  →", color = ClassroomAmber, fontWeight = FontWeight.Bold,
                            modifier = Modifier.clickable { viewerUrl = safe }.padding(horizontal = 8.dp, vertical = 8.dp))
                    }
                }
                error?.let { Text(it, color = Color(0xFFFFBBA1), fontSize = 12.sp,
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 8.dp)) }
                Spacer(Modifier.height(24.dp))
                Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(6.dp))
                    .background(Color(0xC82C4055)).clickable(onClick = onOpenCourses)
                    .padding(horizontal = 16.dp, vertical = 17.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("用课程资料上课", color = ClassroomChalk, fontSize = 17.sp, fontWeight = FontWeight.Bold)
                        Text("从课程中选择或上传资料，再建立课堂", color = Color(0xFFB9C7D0), fontSize = 11.sp)
                    }
                    Text("→", color = ClassroomAmber, fontSize = 23.sp)
                }
                Spacer(Modifier.height(29.dp))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically) {
                    Text("最近学习", color = ClassroomChalk, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                    Text("查看学习足迹  →", color = ClassroomAmber, fontSize = 12.sp,
                        modifier = Modifier.clickable(onClick = onOpenHistory).padding(6.dp))
                }
                if (historyLoading || history.isEmpty()) {
                    Text(if (historyLoading) "正在加载最近学习…" else "还没有课堂记录，从上面的主题开始一节课吧。",
                        color = Color(0xFFB9C7D0), fontSize = 13.sp,
                        modifier = Modifier.fillMaxWidth().padding(vertical = 18.dp))
                } else {
                    history.take(4).forEach { recent ->
                        val safe = trusted(recent.entry.classroom.url)
                        Column(Modifier.fillMaxWidth().clickable(enabled = safe != null) { viewerUrl = safe }
                            .padding(vertical = 12.dp)) {
                            Text("${recent.entry.courseName} · ${if (safe == null) "暂不可打开" else "继续上课  →"}",
                                color = ClassroomChalk, fontWeight = FontWeight.Bold)
                            Text("${if (recent.lastEnteredAt != null) "上次进入" else "创建于"} ${(recent.lastEnteredAt ?: recent.entry.classroom.createdAt).orEmpty().replace('T', ' ').take(16)}" +
                                if (recent.totalSeconds > 0) " · 已学 ${formatClassroomStudyDuration(recent.totalSeconds)}" else "",
                                color = Color(0xFFB9C7D0), fontSize = 12.sp)
                        }
                        Spacer(Modifier.fillMaxWidth().height(1.dp).background(Color(0x335B7C8C)))
                    }
                }
                Spacer(Modifier.height(30.dp))
            }
            if (sessionId == null) ClassroomStartDock(
                enabled = !statusLoading && !submitting && !uploading && status?.enabled == true && status?.browserEmbedAvailable == true,
                submitting = submitting,
                onStart = { startClassroom() },
            )
        }
    }
    viewerUrl?.let { ClassroomViewer(it, { viewerUrl = null; historyRefresh++ }, repository) }
}

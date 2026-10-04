package com.example.campusai.ui.screens.courses

import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream

private val midnight = Color(0xFF172747)
private val paper = Color(0xFFFFECD0)

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
    var history by remember { mutableStateOf<List<InteractiveClassroomItemDto>>(emptyList()) }
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

    Box(Modifier.fillMaxSize().background(Color(0xFFF8F2E8))) {
        Image(painterResource(R.drawable.campus_twilight_original), contentDescription = null,
            modifier = Modifier.fillMaxWidth().height(250.dp).align(Alignment.TopCenter),
            contentScale = ContentScale.Crop, alignment = Alignment.TopCenter)
        Box(Modifier.fillMaxWidth().height(250.dp).align(Alignment.TopCenter).background(
            Brush.verticalGradient(listOf(Color(0x66182444), Color.Transparent, Color(0xFFF8F2E8)))))
        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding()) {
            Row(Modifier.fillMaxWidth().padding(start = 20.dp, top = 12.dp, end = 20.dp),
                verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack, modifier = Modifier.size(58.dp).clip(CircleShape)
                    .background(Color(0xA8173344))) {
                    Icon(Icons.Default.ArrowBack, contentDescription = "返回校园", tint = Color.White)
                }
                Spacer(Modifier.width(12.dp))
                Column {
                    Text("互动课堂", color = Color.White, fontSize = 25.sp, fontWeight = FontWeight.Bold)
                    Text("选好主题，走进你的课堂", color = Color.White.copy(alpha = .9f), fontSize = 12.sp)
                }
            }
            Column(Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp)) {
            Spacer(Modifier.height(102.dp))
            Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(25.dp))
                .background(Color(0xFAFFF9F0)).padding(20.dp), verticalArrangement = Arrangement.spacedBy(13.dp)) {
                Text("从一个问题，走进一节课", color = midnight, fontSize = 23.sp, fontWeight = FontWeight.Bold)
                Text("想学什么就写下来，老师会带你一步步探索。", color = Color(0xFF58647A), fontSize = 13.sp)
                Text("选择老师的讲解方式", color = midnight, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    listOf("循序讲解", "启发提问", "例题练习").forEach { style ->
                        FilterChip(selected = teachingStyle == style,
                            onClick = { teachingStyle = style },
                            label = { Text(style, fontSize = 11.sp) })
                    }
                }
                Text("老师头像和声音由课堂生成服务决定；这里选择讲解方式。",
                    color = Color(0xFF58647A), fontSize = 11.sp)
                OutlinedTextField(value = topic, onValueChange = { topic = it.take(500) },
                    modifier = Modifier.fillMaxWidth(), minLines = 4, maxLines = 7,
                    placeholder = { Text("例如：从零学 Linux 文件权限，边讲边练") },
                    label = { Text("今天想学什么？") })
                Text("上传自己的学习资料", color = midnight, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                Text(selectedMaterialName?.let { "已选：$it" } ?: "支持 PDF、Word、TXT、Markdown，单份不超过 2 MB。",
                    color = Color(0xFF58647A), fontSize = 12.sp)
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(if (uploading) "正在读取…" else "选择文件  →", color = Color(0xFF1C675B),
                        modifier = Modifier.clickable(enabled = !uploading) {
                            pickMaterial.launch(arrayOf("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain", "text/markdown"))
                        }.padding(vertical = 8.dp))
                    if (selectedMaterialId != null) Text("移除", color = Color(0xFF974D42),
                        modifier = Modifier.clickable { selectedMaterialId = null; selectedMaterialName = null }.padding(8.dp))
                }
                Button(onClick = {
                    if (topic.isBlank() && selectedMaterialId == null) {
                        error = "请输入学习主题，或先上传一份资料"; return@Button
                    }
                    submitting = true; error = null
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
                }, enabled = !submitting && !uploading && sessionId == null && status?.enabled == true && status?.browserEmbedAvailable == true,
                    modifier = Modifier.fillMaxWidth(), colors = ButtonDefaults.buttonColors(containerColor = midnight)) {
                    Text(if (submitting) "正在准备…" else "生成我的课堂")
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
                .background(Color(0xFF1B3151)).padding(20.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
                Text("用课程资料上课", color = paper, fontSize = 19.sp, fontWeight = FontWeight.Bold)
                Text("已有资料？从课程中选择或上传文件，再勾选资料建立课堂。", color = Color.White, fontSize = 13.sp)
                Text("选择或上传课程资料  →", color = paper, fontWeight = FontWeight.Bold,
                    modifier = Modifier.clickable(onClick = onOpenCourses).padding(vertical = 8.dp))
            }
            Spacer(Modifier.height(20.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically) {
                Text("最近学习", color = midnight, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                Text("查看学习足迹  →", color = Color(0xFF295643), fontSize = 12.sp,
                    modifier = Modifier.clickable(onClick = onOpenHistory).padding(6.dp))
            }
            if (history.isEmpty()) {
                Text("还没有课堂记录，从上面的主题开始一节课吧。",
                    color = Color(0xFF58647A), fontSize = 13.sp,
                    modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp))
                        .background(Color(0xFFFFF9F0)).padding(16.dp))
            } else {
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
    }
    viewerUrl?.let { ClassroomViewer(it, { viewerUrl = null }, repository) }
}

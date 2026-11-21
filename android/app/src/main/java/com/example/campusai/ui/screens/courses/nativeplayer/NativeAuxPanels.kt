package com.example.campusai.ui.screens.courses.nativeplayer

import android.annotation.SuppressLint
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import coil.ImageLoader
import com.example.campusai.BuildConfig
import com.example.campusai.data.classroom.nativeplayer.NativePlaybackPlan
import com.example.campusai.data.classroom.nativeplayer.NativeSceneMode
import com.example.campusai.data.remote.ClassroomUrlPolicy
import com.example.campusai.ui.theme.Accent
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.DangerText
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.SuccessText
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary

@Composable
fun NativePanelDialog(
    title: String,
    onDismiss: () -> Unit,
    content: @Composable () -> Unit,
) {
    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false),
    ) {
        NativeClassroomTheme(paper = true) {
            Surface(
                modifier = Modifier.widthIn(max = 840.dp).fillMaxWidth(0.94f).fillMaxHeight(0.9f),
                shape = RoundedCornerShape(18.dp),
                color = Background,
            ) {
                Column(Modifier.fillMaxSize().padding(horizontal = 14.dp, vertical = 8.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(title, color = TextPrimary, fontSize = 22.sp, fontWeight = FontWeight.Bold,
                            modifier = Modifier.weight(1f).padding(start = 4.dp))
                        TextButton(onClick = onDismiss) { Text("关闭") }
                    }
                    Spacer(Modifier.height(7.dp))
                    Box(Modifier.weight(1f).fillMaxWidth()) { content() }
                }
            }
        }
    }
}

@Composable
fun NativeNarrationPanel(
    state: NativeNarrationUiState,
    onGenerate: () -> Unit,
    onPlay: () -> Unit,
    onSpeak: () -> Unit,
    onStop: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier
            .fillMaxSize()
            .background(Surface, RoundedCornerShape(14.dp))
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text("讲解与朗读", color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.Bold)
        Text(
            when {
                state.loading -> "正在读取本页讲解…"
                state.jobStatus == "queued" -> "讲解已排队，等待生成"
                state.jobStatus == "running" -> "讲解生成中 ${state.jobProgress}%"
                state.audioFile != null -> "讲解音频已就绪"
                state.available -> "本页讲解已生成"
                state.hasScript -> "本页有讲解稿，可生成音频"
                else -> "本页还没有讲解稿"
            },
            color = Muted,
            fontSize = 12.sp,
        )
        if (state.jobStatus == "queued" || state.jobStatus == "running") {
            Row(verticalAlignment = Alignment.CenterVertically) {
                CircularProgressIndicator(Modifier.size(16.dp), color = Primary, strokeWidth = 2.dp)
                Spacer(Modifier.width(8.dp))
                Text("生成进度 ${state.jobProgress}%", color = Primary, fontSize = 12.sp)
            }
        }
        state.error?.let {
            Text(it, color = DangerText, fontSize = 12.sp)
        }
        if (state.hasScript || state.available) {
            Button(
                onClick = onGenerate,
                enabled = !state.generating && !state.loading,
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (state.generating) CircularProgressIndicator(Modifier.size(16.dp), color = Color.White, strokeWidth = 2.dp)
                Text(if (state.audioFile == null) "生成讲解音频" else "重新生成讲解音频")
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = onPlay,
                enabled = state.audioFile != null || state.available || state.hasScript,
                modifier = Modifier.weight(1f),
            ) {
                Text(if (state.playing) "讲解播放中" else "播放讲解")
            }
            OutlinedButton(onClick = onSpeak, modifier = Modifier.weight(1f)) {
                Text(if (state.speaking) "朗读中" else "系统朗读本页")
            }
        }
        if (state.playing || state.speaking) {
            OutlinedButton(onClick = onStop, modifier = Modifier.fillMaxWidth()) { Text("停止声音") }
        }
        Text(
            "讲解音频使用服务端已接入的语音能力；系统朗读走 Android TTS，不额外上传本页内容。",
            color = Muted,
            fontSize = 11.sp,
            lineHeight = 16.sp,
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFF2F4EC), RoundedCornerShape(8.dp))
                .padding(10.dp),
        )
    }
}

@Composable
fun NativeClassmatesPanel(
    state: NativeClassmateUiState,
    sceneTitle: String,
    onLoad: () -> Unit,
    onSelect: (String) -> Unit,
    onSpeak: () -> Unit,
    onAsk: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var question by remember { mutableStateOf("") }
    LaunchedEffect(Unit) { onLoad() }
    BoxWithConstraints(modifier.fillMaxSize()) {
        val compact = maxHeight < 420.dp
        Column(
            Modifier
                .fillMaxSize()
                .background(Surface, RoundedCornerShape(14.dp))
                .then(if (compact) Modifier.verticalScroll(rememberScrollState()) else Modifier)
                .padding(16.dp),
        ) {
            Text("AI 同学", color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            Text("当前页：$sceneTitle", color = Muted, fontSize = 11.sp)
            Spacer(Modifier.height(8.dp))
            if (state.loading) {
                CircularProgressIndicator(Modifier.size(18.dp), color = Primary, strokeWidth = 2.dp)
            }
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(state.roster, key = { it.id }) { item ->
                    val selected = state.selectedAgentId == item.id
                    Column(
                        Modifier
                            .width(118.dp)
                            .clip(RoundedCornerShape(10.dp))
                            .background(if (selected) PrimarySoft else Color(0xFFF2F4EC))
                            .border(1.dp, if (selected) Primary else Line, RoundedCornerShape(10.dp))
                            .clickable { onSelect(item.id) }
                            .padding(10.dp),
                    ) {
                        Text(item.name, color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                        Text(item.persona.ifBlank { item.role }, color = Muted, fontSize = 10.sp, maxLines = 2)
                    }
                }
            }
            Spacer(Modifier.height(10.dp))
            LazyColumn(
                (if (compact) Modifier.heightIn(min = 96.dp, max = 176.dp) else Modifier.weight(1f))
                    .fillMaxWidth()
                    .background(Color(0xFFF7F8F2), RoundedCornerShape(10.dp))
                    .padding(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(state.messages) { message ->
                    val name = state.roster.firstOrNull { it.id == message.agentId }?.name ?: "同学"
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .background(Color(0xFFFFFEF8), RoundedCornerShape(8.dp))
                            .padding(8.dp),
                    ) {
                        Text(name, color = Primary, fontSize = 10.sp, fontWeight = FontWeight.SemiBold)
                        Text(message.text, color = TextPrimary, fontSize = 12.sp, lineHeight = 18.sp)
                    }
                }
                if (state.messages.isEmpty() && !state.busy) {
                    item {
                        Text("可以让同学补充这一页，或点某位同学提问。", color = Muted, fontSize = 11.sp)
                    }
                }
            }
            if (state.busy) {
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 6.dp)) {
                    CircularProgressIndicator(Modifier.size(14.dp), color = Primary, strokeWidth = 2.dp)
                    Spacer(Modifier.width(8.dp))
                    Text("同学正在准备…", color = Muted, fontSize = 11.sp)
                }
            }
            state.error?.let { Text(it, color = DangerText, fontSize = 11.sp) }
            Spacer(Modifier.height(6.dp))
            OutlinedButton(onClick = onSpeak, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) {
                Text("请同学补充这一页")
            }
            Spacer(Modifier.height(6.dp))
            OutlinedTextField(
                value = question,
                onValueChange = { question = it },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
                placeholder = { Text("点名提问，例如：这一步为什么成立？") },
            )
            Spacer(Modifier.height(6.dp))
            Button(
                onClick = {
                    val text = question.trim()
                    if (text.isNotEmpty()) {
                        onAsk(text)
                        question = ""
                    }
                },
                enabled = !state.busy && state.selectedAgentId != null,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("点名提问")
            }
        }
    }
}

@Composable
fun NativeDirectoryPanel(
    plan: NativePlaybackPlan,
    document: com.example.campusai.data.classroom.nativeplayer.NativeStageDocument?,
    index: Int,
    visitedSceneIds: Set<String>,
    imageLoader: ImageLoader,
    assetKeyPrefix: String,
    mediaBase: String?,
    onSelect: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier
            .fillMaxSize()
            .background(Surface, RoundedCornerShape(14.dp))
            .padding(12.dp),
    ) {
        Text("第 ${index + 1} / ${plan.scenes.size} 页", color = Muted, fontSize = 13.sp)
        Spacer(Modifier.height(10.dp))
        LazyColumn(
            state = rememberLazyListState(index),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            itemsIndexed(plan.scenes, key = { _, item -> item.id }) { sceneIndex, scene ->
                val current = sceneIndex == index
                Row(
                    Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(10.dp))
                        .background(if (current) PrimarySoft else Surface)
                        .border(1.dp, if (current) Primary else Line, RoundedCornerShape(10.dp))
                        .clickable { onSelect(sceneIndex) }
                        .padding(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(
                        Modifier
                            .width(112.dp)
                            .height(63.dp)
                            .clip(RoundedCornerShape(6.dp))
                            .background(Background),
                    ) {
                        val slide = document?.slideByScene?.get(scene.id)
                        if (slide != null) {
                            NativeSlideCanvas(
                                slide = slide,
                                imageLoader = imageLoader,
                                assetKeyPrefix = "$assetKeyPrefix:thumb-${scene.id}",
                                mediaBase = mediaBase,
                                modifier = Modifier.width(112.dp).height(63.dp),
                                isPreview = true,
                            )
                        } else {
                            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                                Text(
                                    (sceneIndex + 1).toString().padStart(2, '0'),
                                    color = Accent, fontSize = 20.sp, fontWeight = FontWeight.Bold,
                                )
                            }
                        }
                    }
                    Spacer(Modifier.width(10.dp))
                    Column(Modifier.weight(1f)) {
                        Text(scene.title, color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.SemiBold,
                            maxLines = 2, overflow = TextOverflow.Ellipsis)
                        val status = when {
                            current -> "当前页"
                            scene.isSandbox -> "网页"
                            scene.id in visitedSceneIds -> "已访问"
                            else -> null
                        }
                        Text(
                            listOfNotNull(sceneTypeText(scene.type), status).joinToString(" · "),
                            color = if (current) Primary else Muted, fontSize = 12.sp,
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun NativeEndSummaryDialog(
    summary: NativeEndSummary,
    onContinue: () -> Unit,
    onFinish: () -> Unit,
) {
    NativeClassroomTheme(paper = true) {
        Dialog(onDismissRequest = onContinue) {
            Surface(shape = RoundedCornerShape(18.dp), color = Surface) {
                Column(Modifier.verticalScroll(rememberScrollState()).padding(18.dp),
                    verticalArrangement = Arrangement.spacedBy(11.dp)) {
                    Text(
                        if (summary.completed) "本章完成" else "保存学习进度",
                        color = TextPrimary,
                        fontSize = 22.sp,
                        fontWeight = FontWeight.Bold,
                    )
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        SummaryMetric("学习时长", formatDuration(summary.activeSeconds), Modifier.weight(1f))
                        SummaryMetric("访问页", "${summary.pagesVisited}/${summary.totalPages}", Modifier.weight(1f))
                        SummaryMetric("本次奖励", "+${summary.sessionXp} XP", Modifier.weight(1f))
                    }
                    if (summary.autoTotal > 0) {
                        Text("客观题答对 ${summary.autoCorrect}/${summary.autoTotal} 题", color = Muted, fontSize = 13.sp)
                    }
                    if (summary.achievements.isNotEmpty()) {
                        Text(
                            "解锁：${summary.achievements.joinToString("、") { achievementLabel(it) }}",
                            color = Accent,
                            fontSize = 12.sp,
                        )
                    }
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = onContinue, modifier = Modifier.weight(1f)) { Text("继续学习") }
                        Button(onClick = onFinish, modifier = Modifier.weight(1f)) {
                            Text(if (summary.completed) "结束并返回" else "保存并退出")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SummaryMetric(label: String, value: String, modifier: Modifier) {
    Column(
        modifier.background(Background, RoundedCornerShape(9.dp)).padding(horizontal = 6.dp, vertical = 10.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(label, color = Muted, fontSize = 10.sp, textAlign = TextAlign.Center)
        Text(value, color = Primary, fontSize = 13.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
    }
}

@Composable
fun NativeUnavailablePanel(
    reason: String?,
    hasFallback: Boolean,
    onRetry: () -> Unit,
    onOpenFallback: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier
            .fillMaxSize()
            .background(Surface, RoundedCornerShape(14.dp))
            .border(1.dp, Line, RoundedCornerShape(14.dp))
            .padding(20.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(Icons.Default.MenuBook, contentDescription = null, tint = Primary, modifier = Modifier.size(30.dp))
        Spacer(Modifier.height(10.dp))
        Text("这一页当前不能原生播放", color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
        Spacer(Modifier.height(6.dp))
        Text(reason ?: "服务端没有下发可播放的正文。", color = Muted, fontSize = 13.sp, lineHeight = 19.sp, textAlign = TextAlign.Center)
        Spacer(Modifier.height(12.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = onRetry) { Text("重新读取") }
            if (hasFallback) {
                Button(onClick = onOpenFallback) { Text("打开兼容课堂") }
            }
        }
    }
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun NativeSandboxScene(
    mode: NativeSceneMode,
    payload: String,
    trustedOrigin: String?,
    onBlocked: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val allowed = mode == NativeSceneMode.SANDBOX_HTML || (
        trustedOrigin != null &&
            ClassroomUrlPolicy.isTrusted(payload, listOf(trustedOrigin), allowEmulatorDebug = BuildConfig.DEBUG)
        )
    if (!allowed) {
        NativeUnavailablePanel(
            reason = "该互动需要受限网页运行时，但当前入口没有可信课堂地址。",
            hasFallback = false,
            onRetry = {},
            onOpenFallback = {},
            modifier = modifier,
        )
        return
    }
    val webView = remember { WebView(context) }
    DisposableEffect(Unit) {
        onDispose {
            runCatching {
                webView.stopLoading()
                webView.destroy()
            }
        }
    }
    AndroidView(
        modifier = modifier
            .fillMaxSize()
            .clip(RoundedCornerShape(14.dp)),
        factory = {
            webView.apply {
                settings.javaScriptEnabled = true
                settings.domStorageEnabled = true
                settings.allowFileAccess = false
                settings.allowContentAccess = false
                settings.mediaPlaybackRequiresUserGesture = false
                webViewClient = object : WebViewClient() {
                    override fun shouldOverrideUrlLoading(view: WebView?, url: String?): Boolean {
                        val targetOrigin = ClassroomUrlPolicy.originOf(url)
                        val baseOrigin = ClassroomUrlPolicy.originOf(trustedOrigin)
                        if (targetOrigin == null || (baseOrigin != null && targetOrigin != baseOrigin)) {
                            onBlocked("互动内容尝试跳转到未授权地址，已阻止。")
                            return true
                        }
                        return false
                    }

                    override fun onReceivedError(
                        view: WebView?,
                        errorCode: Int,
                        description: String?,
                        failingUrl: String?,
                    ) {
                        onBlocked(description ?: "互动页面加载失败")
                    }
                }
                if (mode == NativeSceneMode.SANDBOX_HTML) {
                    loadDataWithBaseURL(
                        trustedOrigin ?: "https://magicclass.local/",
                        payload,
                        "text/html",
                        "utf-8",
                        null,
                    )
                } else {
                    loadUrl(payload)
                }
            }
        },
    )
}

@Composable
fun NativeFallbackBanner(
    reason: String?,
    hasFallback: Boolean,
    onOpenFallback: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier
            .fillMaxWidth()
            .background(Surface, RoundedCornerShape(10.dp))
            .border(1.dp, Line, RoundedCornerShape(10.dp))
            .padding(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text("这一页使用兼容课堂播放", color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
            Text(reason ?: "当前场景依赖网页运行时。", color = Muted, fontSize = 10.sp)
        }
        if (hasFallback) {
            TextButton(onClick = onOpenFallback) { Text("打开") }
        }
    }
}

private fun sceneTypeText(type: String): String = when (type) {
    "slide" -> "讲义"
    "quiz" -> "测验"
    "pbl" -> "项目任务"
    "interactive", "simulation" -> "互动"
    else -> "其他课件"
}

private fun formatDuration(seconds: Long): String {
    val minutes = seconds / 60
    val rest = seconds % 60
    return if (minutes > 0) "${minutes} 分 ${rest} 秒" else "${rest} 秒"
}

private fun achievementLabel(id: String): String = when (id) {
    "first_scene" -> "开课了"
    "half_route" -> "过半"
    "finish_route" -> "走完这一章"
    "combo_3" -> "三连对"
    "combo_5" -> "五连对"
    "perfect_quiz" -> "满分答卷"
    else -> id
}

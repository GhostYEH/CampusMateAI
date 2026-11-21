package com.example.campusai.ui.screens.tasks

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.example.campusai.data.chaoxing.ChaoxingLesson
import com.example.campusai.data.chaoxing.ChaoxingLessonOption
import com.example.campusai.data.chaoxing.ChaoxingLessonQuestion
import com.example.campusai.data.chaoxing.ChaoxingLessonScene
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomRef
import com.example.campusai.data.model.Task
import com.example.campusai.data.remote.ChaoxingAssignmentContentDto
import com.example.campusai.data.remote.ChaoxingReviewResponseDto
import com.example.campusai.data.remote.MagicClassGenerationJobDto
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.screens.courses.nativeplayer.NativeClassroomPlayer
import com.example.campusai.ui.theme.Muted
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * 作业详情里的复习入口。只消费服务端快照与受管课堂 job，不在客户端抓学习通，
 * 也不在本地推断“全部正确”；部分批改会被明确标注。
 */
@Composable
fun ChaoxingAssignmentReviewSection(task: Task, repository: AppRepository) {
    if (task.source != "chaoxing") return
    val scope = rememberCoroutineScope()
    var content by remember(task.id) { mutableStateOf<ChaoxingAssignmentContentDto?>(null) }
    var loading by remember(task.id) { mutableStateOf(true) }
    var busyScope by remember(task.id) { mutableStateOf<String?>(null) }
    var review by remember(task.id) { mutableStateOf<ChaoxingReviewResponseDto?>(null) }
    var lesson by remember(task.id) { mutableStateOf<ChaoxingLesson?>(null) }
    var lessonLoading by remember(task.id) { mutableStateOf(false) }
    var error by remember(task.id) { mutableStateOf<String?>(null) }
    var showLesson by remember(task.id) { mutableStateOf(false) }
    var showWrongList by remember(task.id) { mutableStateOf(false) }
    var nativeRef by rememberSaveable(task.id) { mutableStateOf<NativeClassroomRef?>(null) }
    var showNative by rememberSaveable(task.id) { mutableStateOf(false) }

    suspend fun loadContent() {
        loading = true
        repository.chaoxingAssignmentContent(task.id)
            .onSuccess { content = it; error = null }
            .onFailure { error = it.message ?: "作业题目读取失败" }
        loading = false
    }

    suspend fun loadLesson(source: ChaoxingReviewResponseDto) {
        lessonLoading = true
        var stageId = source.stageId
        if (stageId == null) {
            for (attempt in 0..2) {
                stageId = repository.magicClassStages(source.courseId, source.workspaceId)
                    .getOrNull()
                    ?.maxByOrNull { it.updatedAt ?: it.createdAt ?: "" }
                    ?.id
                if (stageId != null) break
                if (attempt < 2) delay(1000)
            }
        }
        val resolvedStageId = stageId
        if (resolvedStageId == null) {
            error = "课堂已生成，但还没有找到可阅读的舞台"
            lessonLoading = false
            return
        }
        repository.magicClassStage(source.courseId, source.workspaceId, resolvedStageId)
            .onSuccess { stage ->
                val parsed = ChaoxingLesson.fromDocument(stage.document)
                if (parsed == null) error = "课堂内容为空或格式无法识别"
                else {
                    lesson = parsed
                    nativeRef = NativeClassroomRef(
                        courseId = source.courseId,
                        workspaceId = source.workspaceId,
                        stageId = resolvedStageId,
                        title = stage.title.orEmpty().ifBlank { parsed.title },
                        workspaceName = source.workspaceId,
                    )
                    showLesson = false
                    error = null
                }
            }
            .onFailure { error = it.message ?: "课堂内容读取失败" }
        lessonLoading = false
    }

    LaunchedEffect(task.id, task.due, task.done) { loadContent() }

    LaunchedEffect(review?.job?.id, review?.job?.status) {
        var current = review ?: return@LaunchedEffect
        if (current.job.status !in setOf("queued", "running")) {
            if (current.job.status == "completed") loadLesson(current)
            return@LaunchedEffect
        }
        while (true) {
            delay(2000)
            val job = repository.magicClassGenerationJob(current.courseId, current.job.id)
                .getOrElse {
                    error = it.message ?: "课堂进度查询失败"
                    return@LaunchedEffect
                }
            current = current.copy(job = job)
            review = current
            if (job.status !in setOf("queued", "running")) break
        }
        if (current.job.status == "completed") loadLesson(current)
        else if (current.job.status != "cancelled") {
            error = "课堂生成失败，可以重新提交"
        }
    }

    fun generate(scopeValue: String) {
        if (busyScope != null) return
        busyScope = scopeValue
        error = null
        scope.launch {
            repository.generateChaoxingAssignmentReview(task.id, scopeValue)
                .onSuccess { review = it }
                .onFailure { error = it.message ?: "课堂生成请求被拒绝" }
            busyScope = null
        }
    }

    fun retry(source: ChaoxingReviewResponseDto) {
        if (busyScope != null) return
        busyScope = "retry"
        error = null
        scope.launch {
            repository.retryMagicClassGenerationJob(source.courseId, source.job.id)
                .onSuccess { review = source.copy(job = it) }
                .onFailure { error = it.message ?: "课堂重试失败" }
            busyScope = null
        }
    }

    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
        Divider(color = JournalBlue.copy(alpha = .45f))
        Spacer(Modifier.height(12.dp))
        Text("作业复习", color = JournalNight, fontSize = 17.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(4.dp))
        Text(
            "全部题目复习保留原题重做与变式；错题复习只出变式，不再出现原题。",
            color = Muted,
            fontSize = 12.sp,
            lineHeight = 18.sp,
        )
        Spacer(Modifier.height(8.dp))
        when {
            loading -> Row(verticalAlignment = Alignment.CenterVertically) {
                CircularProgressIndicator(Modifier.width(16.dp).height(16.dp), color = JournalBlue, strokeWidth = 2.dp)
                Spacer(Modifier.width(8.dp))
                Text("正在读取作业题目…", color = Muted, fontSize = 12.sp)
            }
            content == null -> Text(
                error ?: "暂时无法读取作业题目，请返回课程同步后重试。",
                color = Color(0xFF974D42),
                fontSize = 12.sp,
            )
            content?.available != true -> Text(
                "还没有题目快照。请先到课程页同步学习通作业，再回来复习。",
                color = Muted,
                fontSize = 12.sp,
            )
            else -> {
                val snapshot = content!!
                Text("已同步 ${snapshot.questions.size} 道题。", color = Muted, fontSize = 12.sp)
                if (snapshot.resultsComplete) {
                    Text(
                        if (snapshot.wrongCount > 0)
                            "已批改：错题 ${snapshot.wrongCount} 道，可以只生成错题变式讲解。"
                        else "已批改：本次作业全部正确，没有需要单独整理的错题。",
                        color = Muted,
                        fontSize = 12.sp,
                    )
                } else if (snapshot.resultsAvailable) {
                    Text(
                        if (snapshot.wrongCount > 0)
                            "已取得部分批改结果：已批改 ${snapshot.gradedCount}/${snapshot.questions.size} 道，发现错题 ${snapshot.wrongCount} 道；其余题目尚未批改。"
                        else "已取得部分批改结果：已批改 ${snapshot.gradedCount}/${snapshot.questions.size} 道，暂未发现错题；其余题目尚未批改。",
                        color = Muted,
                        fontSize = 12.sp,
                    )
                } else {
                    Text(
                        "尚未取得逐题批改结果，暂不能单独生成错题课；可以先按全部题目复习。",
                        color = Muted,
                        fontSize = 12.sp,
                    )
                }
                val wrongQuestions = snapshot.questions.filter { it.isCorrect == false }
                if (wrongQuestions.isNotEmpty()) {
                    TextButton(
                        onClick = { showWrongList = !showWrongList },
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp),
                    ) {
                        Text(
                            if (showWrongList) "收起错题清单" else "查看错题清单（${wrongQuestions.size}）",
                            color = JournalBlue,
                            fontSize = 12.sp,
                        )
                    }
                    if (showWrongList) {
                        Column(
                            Modifier
                                .fillMaxWidth()
                                .background(Color.White.copy(alpha = .55f), RoundedCornerShape(9.dp))
                                .padding(horizontal = 10.dp, vertical = 6.dp),
                            verticalArrangement = Arrangement.spacedBy(5.dp),
                        ) {
                            wrongQuestions.forEach { question ->
                                Text(
                                    "第 ${question.number} 题 · ${question.stem}",
                                    color = JournalNight,
                                    fontSize = 12.sp,
                                    lineHeight = 18.sp,
                                )
                            }
                        }
                    }
                }
                Spacer(Modifier.height(8.dp))
                if (!snapshot.canGenerate) {
                    Text("作业截止后开放复习；截止时间未知时请先同步学习通。", color = Muted, fontSize = 12.sp)
                }
                if (!snapshot.current) {
                    Text("题目快照与当前提交状态不一致，建议先同步作业。", color = JournalClay, fontSize = 12.sp)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = { generate("all") },
                        enabled = snapshot.canGenerate && busyScope == null,
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(10.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = JournalBlue),
                    ) {
                        Text(if (busyScope == "all") "正在创建…" else "全部题目复习", fontSize = 12.sp)
                    }
                    if (snapshot.canGenerateWrong) {
                        OutlinedButton(
                            onClick = { generate("wrong") },
                            enabled = busyScope == null,
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(10.dp),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = JournalClay),
                            border = BorderStroke(1.dp, JournalClay.copy(alpha = .6f)),
                        ) {
                            Text(if (busyScope == "wrong") "正在生成…" else "错题讲解", fontSize = 12.sp)
                        }
                    }
                }
            }
        }

        val currentReview = review
        if (currentReview != null) {
            Spacer(Modifier.height(8.dp))
            when (currentReview.job.status) {
                "queued", "running" -> {
                    LinearProgressIndicator(
                        progress = { currentReview.job.progress.coerceIn(0, 100) / 100f },
                        modifier = Modifier.fillMaxWidth(),
                        color = JournalBlue,
                    )
                    Text(
                        "课堂生成中：${currentReview.job.progress}% 。可以保持此页面等待，或稍后重新生成。",
                        color = Muted,
                        fontSize = 12.sp,
                    )
                }
                "completed" -> {
                    Text(
                        if (currentReview.scope == "wrong") "错题变式课堂已生成。" else "作业讲解与练习已生成。",
                        color = JournalBlue,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                    if (lessonLoading) {
                        Text("正在读取课堂内容…", color = Muted, fontSize = 12.sp)
                    } else if (nativeRef != null) {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(
                                onClick = { showNative = true },
                                modifier = Modifier.weight(1f),
                                shape = RoundedCornerShape(10.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = JournalBlue),
                            ) {
                                Text("进入原生课堂", fontSize = 12.sp)
                            }
                            if (lesson != null) {
                                OutlinedButton(
                                    onClick = { showLesson = true },
                                    modifier = Modifier.weight(1f),
                                    shape = RoundedCornerShape(10.dp),
                                    colors = ButtonDefaults.outlinedButtonColors(contentColor = JournalBlue),
                                ) {
                                    Text("按题目复习", fontSize = 12.sp)
                                }
                            }
                        }
                    } else if (lesson != null) {
                        OutlinedButton(
                            onClick = { showLesson = true },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(10.dp),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = JournalBlue),
                        ) {
                            Text("按题目复习", fontSize = 12.sp)
                        }
                    }
                }
                else -> {
                    Text("课堂生成未完成，可以重试这次任务。", color = Color(0xFF974D42), fontSize = 12.sp)
                    TextButton(
                        onClick = { retry(currentReview) },
                        enabled = busyScope == null,
                    ) {
                        Text(if (busyScope == "retry") "正在重试…" else "重试生成", color = JournalBlue, fontSize = 12.sp)
                    }
                }
            }
        }
        error?.takeIf { content != null }?.let {
            Spacer(Modifier.height(4.dp))
            Text(it, color = Color(0xFF974D42), fontSize = 12.sp)
        }
        Spacer(Modifier.height(12.dp))
    }

    if (showNative && nativeRef != null) {
        Dialog(
            onDismissRequest = { showNative = false },
            properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false),
        ) {
            Surface(Modifier.fillMaxSize(), color = Color(0xFFF1F3EA)) {
                NativeClassroomPlayer(
                    ref = nativeRef!!,
                    repository = repository,
                    onClose = { showNative = false },
                    onOpenFallback = {
                        showNative = false
                        showLesson = true
                    },
                )
            }
        }
    }

    if (showLesson && lesson != null) {
        ChaoxingLessonDialog(lesson = lesson!!, onClose = { showLesson = false })
    }
}

@Composable
private fun ChaoxingLessonDialog(lesson: ChaoxingLesson, onClose: () -> Unit) {
    Dialog(
        onDismissRequest = onClose,
        properties = DialogProperties(usePlatformDefaultWidth = false),
    ) {
        Surface(modifier = Modifier.fillMaxSize().background(JournalPaper)) {
            Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding()) {
                Row(
                    Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(lesson.title, color = JournalNight, fontSize = 21.sp, fontWeight = FontWeight.Bold)
                        Text("${lesson.quizCount} 道练习 · 先做题，再展开参考解析", color = Muted, fontSize = 12.sp)
                    }
                    IconButton(onClick = onClose) {
                        Icon(Icons.Default.Close, contentDescription = "关闭课堂", tint = JournalNight)
                    }
                }
                Divider(color = JournalBlue.copy(alpha = .4f))
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    item {
                        Text(
                            "参考解析由 AI 根据作业快照生成，不是教师官方答案；简答题不自动判分。",
                            color = Muted,
                            fontSize = 12.sp,
                            lineHeight = 18.sp,
                            modifier = Modifier.padding(top = 12.dp),
                        )
                    }
                    items(lesson.scenes, key = { it.id }) { scene ->
                        ChaoxingLessonSceneCard(scene)
                    }
                    item { Spacer(Modifier.height(24.dp)) }
                }
            }
        }
    }
}

@Composable
private fun ChaoxingLessonSceneCard(scene: ChaoxingLessonScene) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        color = Color.White.copy(alpha = .72f),
        border = BorderStroke(1.dp, JournalBlue.copy(alpha = .28f)),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(scene.title, color = JournalNight, fontSize = 16.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                Text(
                    if (scene.kind == "quiz") "练习" else "讲解",
                    color = if (scene.kind == "quiz") JournalClay else JournalBlue,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            scene.body?.takeIf { it.isNotBlank() }?.let {
                Text(it, color = JournalNight, fontSize = 13.sp, lineHeight = 20.sp)
            }
            scene.blocks.forEach { block ->
                block.heading?.let {
                    Text(it, color = JournalClay, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                }
                block.bullets.forEach { bullet ->
                    Text("· $bullet", color = JournalNight, fontSize = 13.sp, lineHeight = 20.sp)
                }
            }
            scene.questions.forEach { question ->
                ChaoxingQuestionCard(question)
            }
        }
    }
}

@Composable
private fun ChaoxingQuestionCard(question: ChaoxingLessonQuestion) {
    var selected by remember(question.id) { mutableStateOf(emptySet<String>()) }
    var submitted by remember(question.id) { mutableStateOf(false) }
    var visibleHints by remember(question.id) { mutableIntStateOf(0) }
    var shortAnswer by remember(question.id) { mutableStateOf("") }
    val correctLabels = question.options.filter { it.value in question.answer }.map { it.label }

    Column(verticalArrangement = Arrangement.spacedBy(7.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(question.roleLabel, color = JournalClay, fontSize = 10.sp, fontWeight = FontWeight.Bold)
            question.sourceNumber?.let { Text("对应原题 $it", color = Muted, fontSize = 10.sp) }
            if (question.isMultiple) Text("多选", color = Muted, fontSize = 10.sp)
        }
        Text(question.prompt, color = JournalNight, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, lineHeight = 21.sp)

        if (question.isChoice) {
            question.options.forEach { option ->
                val isSelected = option.value in selected
                val isCorrect = option.value in question.answer
                val background = when {
                    submitted && isCorrect -> Color(0xFFE1F0E5)
                    submitted && isSelected && !isCorrect -> Color(0xFFF6DAD8)
                    isSelected -> JournalBlue.copy(alpha = .12f)
                    else -> Color.White.copy(alpha = .55f)
                }
                Row(
                    Modifier
                        .fillMaxWidth()
                        .background(background, RoundedCornerShape(9.dp))
                        .border(
                            if (isSelected) 1.dp else 1.dp,
                            if (isSelected) JournalBlue else JournalBlue.copy(alpha = .22f),
                            RoundedCornerShape(9.dp),
                        )
                        .clickable(enabled = !submitted) {
                            selected = if (question.isMultiple) {
                                if (isSelected) selected - option.value else selected + option.value
                            } else setOf(option.value)
                        }
                        .padding(horizontal = 10.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(option.label, color = JournalNight, fontSize = 13.sp, modifier = Modifier.weight(1f))
                    if (submitted && isCorrect) Text("正确", color = Color(0xFF3D7A52), fontSize = 10.sp)
                }
            }
        } else {
            OutlinedTextField(
                value = shortAnswer,
                onValueChange = { shortAnswer = it },
                modifier = Modifier.fillMaxWidth(),
                enabled = !submitted,
                minLines = 2,
                placeholder = { Text("先自己写出思路或答案，再核对参考解析", fontSize = 12.sp) },
                shape = RoundedCornerShape(9.dp),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text),
            )
        }

        if (question.hints.isNotEmpty() && !submitted) {
            TextButton(
                onClick = { visibleHints = (visibleHints + 1).coerceAtMost(question.hints.size) },
                enabled = visibleHints < question.hints.size,
            ) {
                Icon(
                    if (visibleHints < question.hints.size) Icons.Default.ExpandMore else Icons.Default.ExpandLess,
                    contentDescription = null,
                    tint = JournalBlue,
                )
                Spacer(Modifier.width(6.dp))
                Text(
                    if (visibleHints == 0) "查看提示" else "再展开一条提示",
                    color = JournalNight,
                    fontSize = 12.sp,
                )
            }
            repeat(visibleHints) { index ->
                Text("提示 ${index + 1}：${question.hints[index]}", color = Muted, fontSize = 12.sp, lineHeight = 18.sp)
            }
        }

        if (!submitted) {
            Button(
                onClick = { submitted = true },
                enabled = if (question.isChoice) selected.isNotEmpty() else shortAnswer.isNotBlank(),
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(9.dp),
                colors = ButtonDefaults.buttonColors(containerColor = JournalBlue),
            ) {
                Text(if (question.isChoice) "提交并查看解析" else "查看参考解析", fontSize = 12.sp)
            }
        } else {
            if (question.isChoice) {
                val correct = selected == question.answer.toSet()
                Text(
                    if (correct) "回答正确" else "回答不正确；正确选项：${correctLabels.joinToString("、").ifBlank { "见解析" }}",
                    color = if (correct) Color(0xFF3D7A52) else Color(0xFF974D42),
                    fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            Text(question.analysis, color = JournalNight, fontSize = 13.sp, lineHeight = 20.sp)
        }
    }
}

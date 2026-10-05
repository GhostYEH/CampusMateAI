package com.example.campusai.ui.screens.tasks

import com.example.campusai.ui.components.GlassButton as Button
import com.example.campusai.ui.components.GlassIconButton as IconButton
import com.example.campusai.ui.components.GlassOutlinedButton as OutlinedButton
import com.example.campusai.ui.components.GlassTextButton as TextButton

import androidx.lifecycle.compose.collectAsStateWithLifecycle

import androidx.compose.animation.*
import androidx.compose.animation.core.tween
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.Task
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay

private val TaskOrange = Color(0xFFE08A4E)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TaskDetailScreen(
    taskId: String,
    repository: AppRepository,
    onBack: () -> Unit,
    onTaskDeleted: () -> Unit,
    onOpenCourse: (String) -> Unit = {},
) {
    val tasks by repository.tasks.collectAsStateWithLifecycle()
    val task = remember(tasks, taskId) { tasks.find { it.id == taskId } }
    val courseSynced = task?.source in setOf("chaoxing", "chaoxing_notice", "course_notice")
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()

    if (task == null) {
        Box(Modifier.fillMaxSize().background(Background), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Icon(Icons.Default.Warning, null, tint = Muted, modifier = Modifier.size(48.dp))
                Text("任务不存在或已被删除", color = Muted, fontSize = 15.sp)
                TextButton(onClick = onBack) { Text("返回待办列表") }
            }
        }
        return
    }

    var deleting by remember { mutableStateOf(false) }
    var confirmationError by remember { mutableStateOf<String?>(null) }
    var isEditing by remember { mutableStateOf(false) }
    var editTitle by remember { mutableStateOf(task.title) }
    var editDue by remember { mutableStateOf(task.due) }
    var editCourse by remember { mutableStateOf(task.course) }
    var editDescription by remember { mutableStateOf(task.description) }
    var showSource by remember { mutableStateOf(false) }
    var stampVisible by remember { mutableStateOf(false) }
    val context = LocalContext.current

    val hasChanges = isEditing && (
        editTitle != task.title ||
        editDue != task.due ||
        editCourse != task.course ||
        editDescription != task.description
    )

    fun handleBack() {
        if (isEditing && hasChanges) {
            scope.launch {
                repository.updateTask(task.id, editTitle, editDue, editCourse, editDescription)
            }
        }
        onBack()
    }
    BackHandler(onBack = ::handleBack)

    Box(Modifier.fillMaxSize()) {
        JournalBackdrop(Modifier.fillMaxSize())
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(top = 8.dp)) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("任务档案", color = Color(0xFFF6E9D4), fontSize = 12.sp, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
                Spacer(Modifier.weight(1f))
                if (isEditing) TextButton(onClick = {
                    editTitle = task.title; editDue = task.due; editCourse = task.course
                    editDescription = task.description; isEditing = false
                }) { Text("取消", color = Color(0xFFF6E9D4)) }
                if (!courseSynced) IconButton(onClick = { deleting = true }) {
                    Icon(Icons.Default.DeleteOutline, "删除", tint = Color(0xFFF6E9D4))
                }
            }

            // ── Status badge ──
            Row(
                Modifier
                    .padding(horizontal = 16.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(if (task.done) Success.copy(alpha = .1f) else TaskOrange.copy(alpha = .1f))
                    .border(
                        1.dp,
                        if (task.done) Success.copy(alpha = .3f) else TaskOrange.copy(alpha = .3f),
                        RoundedCornerShape(12.dp),
                    )
                    .padding(horizontal = 14.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(
                    if (task.done) Icons.Default.CheckCircle else Icons.Default.PendingActions,
                    null,
                    tint = if (task.done) Success else TaskOrange,
                    modifier = Modifier.size(18.dp),
                )
                Text(
                    if (task.done && task.submittedAt != null) "平台已提交"
                    else if (task.done) "已完成"
                    else if (task.source in setOf("chaoxing_notice", "course_notice")) "待确认"
                    else "待完成",
                    fontSize = 13.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = if (task.done) Success else TaskOrange,
                )
                Spacer(Modifier.weight(1f))
                if (!isEditing && !courseSynced) {
                    IconButton(onClick = { isEditing = true }, modifier = Modifier.size(32.dp)) {
                        Icon(Icons.Default.Edit, "编辑", tint = Muted, modifier = Modifier.size(18.dp))
                    }
                }
            }

            Spacer(Modifier.height(12.dp))

            // ── Title ──
            if (isEditing) {
                OutlinedTextField(
                    value = editTitle,
                    onValueChange = { editTitle = it },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 20.dp)
                        .enterAnimation(enabled = !reduceMotion),
                    label = { Text("任务名称") },
                    singleLine = true,
                    shape = RoundedCornerShape(14.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Primary,
                        unfocusedBorderColor = Line,
                    ),
                )
            } else {
                Text(
                    task.title,
                    modifier = Modifier
                        .padding(horizontal = 16.dp)
                        .enterAnimation(enabled = !reduceMotion, delayMs = 40),
                    fontSize = 22.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFFFFF4E3),
                    textDecoration = if (task.done) TextDecoration.LineThrough else null,
                )
            }

            Spacer(Modifier.height(15.dp))

            // ── Info cards ──
            if (isEditing) {
                // Edit mode fields
                Column(
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp)
                        .enterAnimation(enabled = !reduceMotion, delayMs = 80),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    OutlinedButton(onClick = { pickTaskDeadline(editDue.takeIf { it != "待设置" }, { editDue = it }, context) }, modifier = Modifier.fillMaxWidth()) {
                        Icon(Icons.Default.Schedule, null, tint = TaskOrange)
                        Spacer(Modifier.width(8.dp))
                        Text("截止时间：${displayTaskDeadline(editDue.takeIf { it != "待设置" })}")
                    }
                    OutlinedTextField(
                        value = editCourse,
                        onValueChange = { editCourse = it },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("分类") },
                        placeholder = { Text("例如：课程作业 / 个人待办 / 学习安排") },
                        singleLine = true,
                        shape = RoundedCornerShape(14.dp),
                        leadingIcon = { Icon(Icons.Default.Category, null, tint = Primary) },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = Primary,
                            unfocusedBorderColor = Line,
                        ),
                    )
                }
            } else {
                JournalSheet(Modifier.fillMaxWidth().padding(horizontal = 16.dp)
                    .enterAnimation(enabled = !reduceMotion, delayMs = 80)) {
                    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text(task.course, color = JournalInk, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                        task.startAt?.let { startsAt ->
                            DetailLine("开放时间", startsAt.replace('T', ' ').take(16))
                        }
                        DetailLine("截止时间", task.due.replace('T', ' ').take(16))
                    }
                }
            }

            Spacer(Modifier.height(15.dp))

            // ── Description ──
            val descContent = if (isEditing) editDescription else task.description
            if (isEditing || task.description.isNotBlank()) {
                Column(
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp)
                        .enterAnimation(enabled = !reduceMotion, delayMs = 120),
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Icon(Icons.Default.Description, null, tint = Muted, modifier = Modifier.size(20.dp))
                        Text("任务说明", fontSize = 15.sp, fontWeight = FontWeight.SemiBold, color = Color(0xFFF6E9D4))
                    }
                    Spacer(Modifier.height(10.dp))

                    if (isEditing) {
                        OutlinedTextField(
                            value = editDescription,
                            onValueChange = { editDescription = it },
                            modifier = Modifier.fillMaxWidth().heightIn(min = 140.dp),
                            placeholder = { Text("添加详细说明、步骤、备注等...", color = Muted) },
                            shape = RoundedCornerShape(14.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = Primary,
                                unfocusedBorderColor = Line,
                            ),
                        )
                    } else {
                        JournalSheet(Modifier.fillMaxWidth()) {
                            Text(task.description, modifier = Modifier.padding(16.dp), color = JournalInk, fontSize = 14.sp, lineHeight = 22.sp)
                        }
                    }
                }
            }

            if (!isEditing && !task.sourceText.isNullOrBlank()) {
                Spacer(Modifier.height(10.dp))
                TextButton(onClick = { showSource = !showSource }, modifier = Modifier.padding(horizontal = 16.dp)) {
                    Icon(Icons.Default.Description, null, tint = Color(0xFFE6C89B), modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(if (showSource) "收起原始消息" else "查看原始消息", color = Color(0xFFF4E6CF))
                }
                if (showSource) JournalSheet(Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
                    Text(task.sourceText.orEmpty(), Modifier.padding(16.dp), color = JournalInk, fontSize = 12.sp, lineHeight = 20.sp)
                }
            }

            Spacer(Modifier.height(18.dp))

            // ── Action buttons ──
            Column(
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp)
                    .enterAnimation(enabled = !reduceMotion, delayMs = 160),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                if (isEditing) {
                    // Save button in edit mode
                    Button(
                        onClick = {
                            scope.launch {
                                repository.updateTask(task.id, editTitle, editDue, editCourse, editDescription)
                                isEditing = false
                            }
                        },
                        enabled = editTitle.isNotBlank() && hasChanges,
                        modifier = Modifier.fillMaxWidth().height(50.dp),
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Primary, disabledContainerColor = Primary.copy(alpha = .4f)),
                    ) {
                        Icon(Icons.Default.Save, null, modifier = Modifier.size(20.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("保存修改", fontWeight = FontWeight.Bold, fontSize = 15.sp)
                    }
                } else if (courseSynced) {
                    Text(when {
                        task.source == "chaoxing" -> "提交状态由课程同步更新"
                        task.done -> "已由你确认提交"
                        else -> "提交状态待确认，请到课程内核对"
                    }, color = Muted, fontSize = 13.sp)
                    task.courseId?.let { courseId ->
                        Button(onClick = { onOpenCourse(courseId) }, modifier = Modifier.fillMaxWidth().height(50.dp)) {
                            Text("打开原课程作业", fontWeight = FontWeight.Bold)
                        }
                    }
                    if (!task.done && task.source != "chaoxing") {
                        OutlinedButton(onClick = {
                            scope.launch {
                                val result = if (task.source == "course_notice")
                                    repository.confirmCourseNoticeSubmitted(task.id)
                                else repository.completeTaskStrict(task.id)
                                confirmationError = result.exceptionOrNull()?.message
                                if (result.isSuccess && !reduceMotion) {
                                    stampVisible = true
                                    delay(560)
                                    stampVisible = false
                                }
                            }
                        }, modifier = Modifier.fillMaxWidth().height(50.dp)) {
                            Text("我已在课程中提交", fontWeight = FontWeight.Bold)
                        }
                    }
                    confirmationError?.let { Text(it, color = Color(0xFF974D42), fontSize = 13.sp) }
                } else {
                    if (task.done) OutlinedButton(onClick = { scope.launch { repository.toggleTask(task.id) } },
                        modifier = Modifier.fillMaxWidth().height(50.dp), shape = RoundedCornerShape(14.dp)) {
                        Icon(Icons.Default.Undo, null, tint = JournalAmber, modifier = Modifier.size(20.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("标记为未完成", color = Color(0xFFF4E6CF), fontWeight = FontWeight.Bold)
                    } else androidx.compose.material3.Button(onClick = {
                        scope.launch {
                            if (!reduceMotion) { stampVisible = true; delay(560) }
                            repository.toggleTask(task.id)
                            stampVisible = false
                        }
                    }, modifier = Modifier.fillMaxWidth().height(50.dp), shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = JournalInk)) {
                        Icon(Icons.Default.CheckCircle, null, modifier = Modifier.size(20.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("盖章完成", fontWeight = FontWeight.Bold, fontSize = 15.sp)
                    }
                }
                if (stampVisible) Text("已完成", color = Color(0xFFE8D4B4), fontSize = 19.sp,
                    fontWeight = FontWeight.Black, modifier = Modifier.align(Alignment.End)
                        .border(2.dp, Color(0xFFE8D4B4), RoundedCornerShape(5.dp))
                        .padding(horizontal = 12.dp, vertical = 5.dp))

                // Delete button at bottom
                if (!courseSynced) TextButton(
                    onClick = { deleting = true },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Default.DeleteOutline, null, tint = Muted, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("删除此任务", color = Muted, fontSize = 13.sp)
                }
            }

            // Bottom spacing for dock
            Spacer(Modifier.height(WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + 28.dp))
        }
    }

    // ── Delete confirmation dialog ──
    if (deleting) {
        AlertDialog(
            onDismissRequest = { deleting = false },
            icon = { Icon(Icons.Default.DeleteOutline, null, tint = Danger) },
            title = { Text("删除这项待办？") },
            text = { Text(task.title, color = Muted) },
            confirmButton = {
                TextButton(onClick = {
                    scope.launch {
                        repository.deleteTask(task.id)
                        deleting = false
                        onTaskDeleted()
                    }
                }) { Text("删除", color = Danger) }
            },
            dismissButton = { TextButton(onClick = { deleting = false }) { Text("取消") } },
            containerColor = Surface,
        )
    }
}

@Composable
private fun DetailLine(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = JournalMuted, fontSize = 12.sp)
        Text(value, color = JournalInk, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun InfoCard(
    icon: @Composable () -> Unit,
    label: String,
    value: String,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier
            .clip(RoundedCornerShape(16.dp))
            .background(Surface)
            .border(1.dp, Line, RoundedCornerShape(16.dp))
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        icon()
        Text(label, color = Muted, fontSize = 11.sp)
        Text(value, color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
    }
}

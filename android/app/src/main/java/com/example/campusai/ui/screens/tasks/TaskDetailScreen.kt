package com.example.campusai.ui.screens.tasks

import androidx.compose.animation.*
import androidx.compose.animation.core.tween
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

private val TaskOrange = Color(0xFFE08A4E)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TaskDetailScreen(
    taskId: Long,
    repository: AppRepository,
    onBack: () -> Unit,
    onTaskDeleted: () -> Unit,
) {
    val task = repository.getTaskById(taskId)
    val reduceMotion by repository.reduceMotion.collectAsState()
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
    var isEditing by remember { mutableStateOf(false) }
    var editTitle by remember { mutableStateOf(task.title) }
    var editDue by remember { mutableStateOf(task.due) }
    var editCourse by remember { mutableStateOf(task.course) }
    var editDescription by remember { mutableStateOf(task.description) }

    val hasChanges by remember(isEditing) {
        derivedStateOf {
            isEditing && (
                editTitle != task.title ||
                editDue != task.due ||
                editCourse != task.course ||
                editDescription != task.description
            )
        }
    }

    Box(Modifier.fillMaxSize().background(Background)) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
            // ── Top bar ──
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(start = 4.dp, top = 8.dp, end = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = {
                    if (isEditing && hasChanges) {
                        scope.launch {
                            repository.updateTask(task.id, editTitle, editDue, editCourse, editDescription)
                        }
                    }
                    onBack()
                }) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回", tint = TextPrimary)
                }
                Spacer(Modifier.weight(1f))
                if (isEditing) {
                    TextButton(onClick = {
                        editTitle = task.title
                        editDue = task.due
                        editCourse = task.course
                        editDescription = task.description
                        isEditing = false
                    }) {
                        Text("取消", color = Muted, fontSize = 14.sp)
                    }
                }
                IconButton(onClick = { deleting = true }) {
                    Icon(Icons.Default.DeleteOutline, "删除", tint = Muted)
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
                    if (task.done) "已完成" else "待完成",
                    fontSize = 13.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = if (task.done) Success else TaskOrange,
                )
                Spacer(Modifier.weight(1f))
                if (!isEditing) {
                    IconButton(onClick = { isEditing = true }, modifier = Modifier.size(32.dp)) {
                        Icon(Icons.Default.Edit, "编辑", tint = Muted, modifier = Modifier.size(18.dp))
                    }
                }
            }

            Spacer(Modifier.height(20.dp))

            // ── Title ──
            if (isEditing) {
                OutlinedTextField(
                    value = editTitle,
                    onValueChange = { editTitle = it },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp)
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
                    color = TextPrimary,
                    textDecoration = if (task.done) TextDecoration.LineThrough else null,
                )
            }

            Spacer(Modifier.height(22.dp))

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
                    OutlinedTextField(
                        value = editDue,
                        onValueChange = { editDue = it },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("截止时间") },
                        placeholder = { Text("例如：今天 23:59") },
                        singleLine = true,
                        shape = RoundedCornerShape(14.dp),
                        leadingIcon = { Icon(Icons.Default.Schedule, null, tint = TaskOrange) },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = Primary,
                            unfocusedBorderColor = Line,
                        ),
                    )
                    OutlinedTextField(
                        value = editCourse,
                        onValueChange = { editCourse = it },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("分类") },
                        placeholder = { Text("例如：课程作业 / 活动报名 / 个人待办") },
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
                // View mode info cards
                Row(
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp)
                        .enterAnimation(enabled = !reduceMotion, delayMs = 80),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    InfoCard(
                        icon = { Icon(Icons.Default.Schedule, null, tint = TaskOrange, modifier = Modifier.size(22.dp)) },
                        label = "截止时间",
                        value = task.due,
                        modifier = Modifier.weight(1f),
                    )
                    InfoCard(
                        icon = { Icon(Icons.Default.Folder, null, tint = Primary, modifier = Modifier.size(22.dp)) },
                        label = "分类",
                        value = task.course,
                        modifier = Modifier.weight(1f),
                    )
                }
            }

            Spacer(Modifier.height(22.dp))

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
                        Text("任务详情", fontSize = 15.sp, fontWeight = FontWeight.SemiBold, color = TextPrimary)
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
                        Box(
                            Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(16.dp))
                                .background(Surface)
                                .border(1.dp, Line, RoundedCornerShape(16.dp))
                                .padding(16.dp),
                        ) {
                            Text(task.description, color = TextPrimary, fontSize = 14.sp, lineHeight = 22.sp)
                        }
                    }
                }
            }

            Spacer(Modifier.height(24.dp))

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
                } else {
                    // Done/Undone toggle in view mode
                    OutlinedButton(
                        onClick = {
                            scope.launch { repository.toggleTask(task.id) }
                        },
                        modifier = Modifier.fillMaxWidth().height(50.dp),
                        shape = RoundedCornerShape(14.dp),
                        border = ButtonDefaults.outlinedButtonBorder.copy(
                            brush = androidx.compose.ui.graphics.SolidColor(
                                if (task.done) TaskOrange else Success
                            ),
                        ),
                    ) {
                        Icon(
                            if (task.done) Icons.Default.Undo else Icons.Default.CheckCircle,
                            null,
                            tint = if (task.done) TaskOrange else Success,
                            modifier = Modifier.size(20.dp),
                        )
                        Spacer(Modifier.width(8.dp))
                        Text(
                            if (task.done) "标记为未完成" else "标记为已完成",
                            fontWeight = FontWeight.Bold,
                            fontSize = 15.sp,
                            color = if (task.done) TaskOrange else Success,
                        )
                    }
                }

                // Delete button at bottom
                TextButton(
                    onClick = { deleting = true },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Default.DeleteOutline, null, tint = Muted, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("删除此任务", color = Muted, fontSize = 13.sp)
                }
            }

            // Bottom spacing for dock
            Spacer(Modifier.height(80.dp))
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

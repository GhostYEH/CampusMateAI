package com.example.campusai.ui.screens.tasks

import com.example.campusai.ui.components.GlassIconButton as IconButton

import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.example.campusai.data.remote.TaskImportAnalyzeResponse
import com.example.campusai.data.remote.TaskImportCommitRequest
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.GlassButton
import com.example.campusai.ui.components.GlassTextButton
import com.example.campusai.ui.glass.CampusGlassRole
import com.example.campusai.ui.glass.campusGlass
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch

@Composable
fun TaskImportDialog(
    repository: AppRepository,
    onDismiss: () -> Unit,
    onImported: (createdCount: Int, skippedExistingCount: Int) -> Unit,
) {
    var sourceName by remember { mutableStateOf("学习材料") }
    var content by remember { mutableStateOf("") }
    var result by remember { mutableStateOf<TaskImportAnalyzeResponse?>(null) }
    val drafts = remember { mutableStateListOf<TaskImportDraftState>() }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val selectedCount = drafts.count { it.selected && it.title.isNotBlank() }

    Dialog(onDismissRequest = { if (!busy) onDismiss() }, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        BoxWithConstraints(
            Modifier.fillMaxSize().imePadding().padding(16.dp),
            contentAlignment = Alignment.Center,
        ) {
            val compact = maxWidth < 600.dp
            val shortWindow = maxHeight < 560.dp
            Column(
                Modifier.widthIn(max = 760.dp).fillMaxWidth()
                    .fillMaxHeight(if (shortWindow) .98f else .9f)
                    .campusGlass(RoundedCornerShape(28.dp), CampusGlassRole.PANEL)
                    .padding(if (compact) 18.dp else 26.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
                    Column(Modifier.weight(1f)) {
                        Text("AI TASK IMPORT", color = Primary, fontSize = 10.sp, fontWeight = FontWeight.ExtraBold, letterSpacing = 1.4.sp)
                        Text(if (result == null) "导入学习材料" else "确认识别结果", color = TextPrimary, fontSize = 24.sp, fontWeight = FontWeight.ExtraBold)
                        Text(if (result == null) "粘贴课程计划、作业要求或清单" else "已有任务会保留原进度", color = Muted, fontSize = 12.sp)
                    }
                    IconButton(onClick = onDismiss, enabled = !busy) { Icon(Icons.Default.Close, "关闭", tint = Muted) }
                }

                if (result == null) {
                    Column(
                        Modifier.weight(1f).verticalScroll(rememberScrollState()),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        OutlinedTextField(sourceName, { sourceName = it.take(256) }, Modifier.fillMaxWidth(), label = { Text("材料名称") }, singleLine = true, shape = RoundedCornerShape(16.dp))
                        OutlinedTextField(content, { content = it.take(20_000) }, Modifier.fillMaxWidth().heightIn(min = if (shortWindow) 120.dp else 220.dp), label = { Text("计划内容") }, placeholder = { Text("粘贴 Markdown 清单或课程通知…") }, shape = RoundedCornerShape(16.dp))
                    }
                } else {
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.AutoAwesome, null, tint = Primary, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(7.dp)); Text("识别到 ${drafts.size} 项", color = Primary, fontWeight = FontWeight.Bold)
                            Spacer(Modifier.weight(1f)); Text(result?.split_reason.orEmpty(), color = Muted, fontSize = 10.sp)
                        }
                        if (drafts.isEmpty()) {
                            Column(
                                Modifier.fillMaxSize(),
                                horizontalAlignment = Alignment.CenterHorizontally,
                                verticalArrangement = Arrangement.Center,
                            ) {
                                Icon(Icons.Default.AutoAwesome, null, tint = Primary, modifier = Modifier.size(30.dp))
                                Spacer(Modifier.height(8.dp))
                                Text("没有识别到可导入的待办", color = TextPrimary, fontWeight = FontWeight.Bold)
                                Spacer(Modifier.height(4.dp))
                                Text("请点击“返回修改”补充或调整材料内容后再试", color = Muted, fontSize = 12.sp)
                            }
                        } else {
                            LazyColumn(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(9.dp)) {
                                itemsIndexed(drafts) { index, draft ->
                                    Row(
                                        Modifier.fillMaxWidth().campusGlass(RoundedCornerShape(18.dp), CampusGlassRole.DENSE).padding(11.dp),
                                        verticalAlignment = Alignment.Top,
                                    ) {
                                        Checkbox(draft.selected, { drafts[index] = draft.copy(selected = it) }, enabled = draft.existingTaskId == null)
                                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                            OutlinedTextField(draft.title, { drafts[index] = updateImportDraftTitle(draft, it.take(256)) }, Modifier.fillMaxWidth(), singleLine = true, label = { Text("任务") })
                                            OutlinedTextField(draft.description, { drafts[index] = draft.copy(description = it.take(4_000)) }, Modifier.fillMaxWidth(), label = { Text("备注（选填）") }, maxLines = 2)
                                            if (draft.existingTaskId != null) Row(verticalAlignment = Alignment.CenterVertically) {
                                                Icon(Icons.Default.CheckCircle, null, tint = Success, modifier = Modifier.size(14.dp)); Spacer(Modifier.width(4.dp))
                                                Text("已有${if (draft.existingStatus == "completed") "已完成" else "待办"}任务，保留原进度", color = Success, fontSize = 10.sp)
                                            }
                                            draft.warnings.forEach { warning ->
                                                Text(warning, color = AlertInfoText, fontSize = 10.sp)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                error?.let { Text(it, color = Danger, fontSize = 11.sp) }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    GlassTextButton(onClick = { if (result == null) onDismiss() else { result = null; drafts.clear() } }, enabled = !busy) { Text(if (result == null) "取消" else "返回修改") }
                    Spacer(Modifier.width(8.dp))
                    GlassButton(
                        onClick = {
                            scope.launch {
                                busy = true; error = null
                                try {
                                    if (result == null) {
                                        val analyzed = repository.analyzeTaskImport(content.trim(), sourceName.trim())
                                        result = analyzed
                                        drafts.addAll(analyzed.tasks.map {
                                            TaskImportDraftState(
                                                title = it.title,
                                                description = it.description.orEmpty(),
                                                deadline = it.deadline,
                                                sourceName = it.source_name,
                                                sourceText = it.source_text,
                                                priority = it.priority,
                                                materials = it.materials,
                                                submissionMethod = it.submission_method,
                                                location = it.location,
                                                importance = it.importance,
                                                needsConfirmation = it.needs_confirmation,
                                                warnings = it.warnings,
                                                selected = it.selected,
                                                existingTaskId = it.existing_task_id,
                                                existingStatus = it.existing_status,
                                            )
                                        })
                                    } else {
                                        val tasks = drafts
                                            .filter { it.selected && it.title.isNotBlank() }
                                            .map(TaskImportDraftState::toImportCreateRequest)
                                        val committed = repository.commitTaskImport(TaskImportCommitRequest(tasks))
                                        onImported(committed.created.size, committed.skipped_existing.size)
                                    }
                                } catch (throwable: Throwable) { error = throwable.message ?: "操作失败，请重试" }
                                finally { busy = false }
                            }
                        },
                        enabled = !busy && if (result == null) content.isNotBlank() else selectedCount > 0,
                    ) { Text(if (busy) "处理中…" else if (result == null) "分析并拆分" else "保存 $selectedCount 项") }
                }
            }
        }
    }
}

package com.example.campusai.ui.screens.teacher

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material.icons.filled.Save
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.campusai.data.repository.LocalTeacherRepository
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch

@Composable
fun TeacherPublishScreen(repository: LocalTeacherRepository) {
    val drafts by repository.drafts.collectAsState()
    val scope = rememberCoroutineScope()
    var kind by rememberSaveable { mutableStateOf("通知草稿") }
    var title by rememberSaveable { mutableStateOf("") }
    var content by rememberSaveable { mutableStateOf("") }
    var message by remember { mutableStateOf<String?>(null) }

    LazyColumn(
        modifier = Modifier.fillMaxSize().background(Background),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text("发布中心", style = MaterialTheme.typography.headlineMedium)
            Text("先保存为可编辑草稿；接入后端后再由教师确认发布。", color = Muted)
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("通知草稿", "作业草稿").forEach { label ->
                    FilterChip(selected = kind == label, onClick = { kind = label }, label = { Text(label) })
                }
            }
        }
        item {
            OutlinedTextField(value = title, onValueChange = { title = it }, modifier = Modifier.fillMaxWidth(), label = { Text("标题") }, singleLine = true)
            Spacer(Modifier.height(10.dp))
            OutlinedTextField(value = content, onValueChange = { content = it }, modifier = Modifier.fillMaxWidth().heightIn(min = 140.dp), label = { Text(if (kind == "作业草稿") "作业要求" else "通知正文") })
            Spacer(Modifier.height(10.dp))
            Button(
                onClick = {
                    if (title.isBlank() || content.isBlank()) message = "请补充标题和正文"
                    else scope.launch { repository.save(kind, title, content); title = ""; content = ""; message = "草稿已保存到本机" }
                },
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
            ) { Icon(Icons.Default.Save, null); Spacer(Modifier.width(8.dp)); Text("保存草稿") }
            message?.let { Text(it, color = if (it.contains("已")) SuccessText else Danger) }
        }
        item { Text("我的草稿", style = MaterialTheme.typography.titleMedium) }
        if (drafts.isEmpty()) item { Text("还没有草稿", color = Muted) }
        items(drafts, key = { it.id }) { draft ->
            Card(colors = CardDefaults.cardColors(containerColor = Surface), modifier = Modifier.fillMaxWidth()) {
                Row(Modifier.padding(14.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Column(Modifier.weight(1f)) {
                        Text(draft.title, style = MaterialTheme.typography.titleSmall)
                        Text("${draft.kind} · ${draft.content}", color = Muted, maxLines = 3)
                    }
                    IconButton(onClick = { scope.launch { repository.delete(draft.id) } }) { Icon(Icons.Default.DeleteOutline, "删除", tint = Danger) }
                }
            }
        }
    }
}

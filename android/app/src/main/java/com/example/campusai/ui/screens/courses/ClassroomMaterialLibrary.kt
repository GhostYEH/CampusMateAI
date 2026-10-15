package com.example.campusai.ui.screens.courses

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Checkbox
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.example.campusai.data.remote.InteractiveClassroomMaterialDto

@Composable
internal fun ClassroomMaterialLibrary(
    courseName: String,
    materials: List<InteractiveClassroomMaterialDto>,
    selected: Set<String>,
    onToggle: (String, Boolean) -> Unit,
    uploadBusy: Boolean,
    uploadMessage: String?,
    onPickFile: (Uri) -> Unit,
    onDone: () -> Unit,
) {
    var query by remember { mutableStateOf("") }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) onPickFile(uri)
    }
    val visible = remember(query, materials) { materials.filter { it.title.contains(query.trim(), ignoreCase = true) } }
    BackHandler(onBack = onDone)
    Dialog(onDismissRequest = onDone, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        Column(Modifier.fillMaxSize().background(Color(0xFFF4EFDF)).statusBarsPadding().navigationBarsPadding()) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onDone) { Icon(Icons.Default.ArrowBack, contentDescription = "返回课堂设置", tint = Color(0xFF214C3E)) }
                Column(Modifier.weight(1f)) {
                    Text("挑选课堂资料", color = Color(0xFF173B32), fontSize = 22.sp, fontWeight = FontWeight.Bold)
                    Text(courseName, color = Color(0xFF61746A), fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                Text("完成", modifier = Modifier.clip(RoundedCornerShape(14.dp)).clickable(onClick = onDone).padding(12.dp), color = Color(0xFF214C3E), fontWeight = FontWeight.Bold)
            }
            Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 9.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("已选 ${selected.size} / ${materials.size} 项", color = Color(0xFF214C3E), fontSize = 18.sp, fontWeight = FontWeight.Bold)
                Text("勾选想用于本节课的内容，也可以不指定，让课堂自动挑选。",
                    color = Color(0xFF61746A), fontSize = 12.sp)
            }
            Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp)
                .border(1.dp, Color(0xFFB9A780), RoundedCornerShape(6.dp))
                .clickable(enabled = !uploadBusy) {
                    picker.launch(arrayOf("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain", "text/markdown"))
                }.padding(horizontal = 14.dp, vertical = 13.dp),
                verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Add, contentDescription = null, tint = Color(0xFF214C3E), modifier = Modifier.size(20.dp))
                Column(Modifier.padding(start = 9.dp)) {
                    Text(if (uploadBusy) "正在添加资料…" else "添加自己的资料",
                        color = Color(0xFF214C3E), fontWeight = FontWeight.Bold, fontSize = 13.sp)
                    Text("PDF / Word / 文本 · 单份 2 MB 内", color = Color(0xFF61746A), fontSize = 10.sp)
                }
            }
            uploadMessage?.let { Text(it, color = Color(0xFF214C3E), fontSize = 12.sp,
                modifier = Modifier.padding(horizontal = 20.dp)) }
            OutlinedTextField(query, { query = it }, Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp),
                label = { Text("搜索资料") }, singleLine = true, shape = RoundedCornerShape(16.dp))
            LazyColumn(modifier = Modifier.weight(1f), contentPadding = PaddingValues(start = 20.dp, end = 20.dp, bottom = 28.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                if (visible.isEmpty()) item { Text("没有找到资料", color = Color(0xFF61746A), modifier = Modifier.padding(16.dp)) }
                items(visible, key = { it.id }) { material ->
                    val checked = material.id in selected
                    val video = material.kind == "video" || material.title.endsWith(".mp4", ignoreCase = true)
                    val kindLabel = when {
                        video -> "视频"
                        material.kind == "assignment" -> "作业"
                        material.kind == "chapter" -> "章节"
                        else -> "资料"
                    }
                    Row(Modifier.fillMaxWidth()
                        .background(if (checked) Color(0xFFE6E5CF) else Color(0xFFFFFBF1))
                        .clickable { onToggle(material.id, !checked) }.padding(horizontal = 12.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        Icon(if (video) Icons.Default.PlayArrow else Icons.Default.Description,
                            contentDescription = null, tint = Color(0xFF325C4D))
                        Column(Modifier.weight(1f).padding(horizontal = 12.dp)) {
                            Text(material.title, fontSize = 13.sp, color = Color(0xFF183A32),
                                maxLines = 2, overflow = TextOverflow.Ellipsis)
                            Text(kindLabel, fontSize = 10.sp, color = Color(0xFF61746A))
                        }
                        Checkbox(checked = checked, onCheckedChange = { onToggle(material.id, it) })
                    }
                }
            }
        }
    }
}

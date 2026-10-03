package com.example.campusai.ui.screens.courses

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Description
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
    onDone: () -> Unit,
) {
    var query by remember { mutableStateOf("") }
    val visible = remember(query, materials) { materials.filter { it.title.contains(query.trim(), ignoreCase = true) } }
    BackHandler(onBack = onDone)
    Dialog(onDismissRequest = onDone, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        Column(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0xFFF2F0E4), Color(0xFFE6EDE3)))).statusBarsPadding().navigationBarsPadding()) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onDone) { Icon(Icons.Default.ArrowBack, contentDescription = "返回课堂设置", tint = Color(0xFF214C3E)) }
                Column(Modifier.weight(1f)) {
                    Text("课程资料库", color = Color(0xFF173B32), fontSize = 22.sp, fontWeight = FontWeight.Bold)
                    Text(courseName, color = Color(0xFF61746A), fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                Text("完成", modifier = Modifier.clip(RoundedCornerShape(14.dp)).clickable(onClick = onDone).padding(12.dp), color = Color(0xFF214C3E), fontWeight = FontWeight.Bold)
            }
            Box(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp).clip(RoundedCornerShape(18.dp))
                .background(Brush.horizontalGradient(listOf(Color(0xFF173E34), Color(0xFF59734D), Color(0xFF8A7650)))).padding(18.dp)) {
                Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Text("已选 ${selected.size} / ${materials.size} 项", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                    Text("当前只读取文件名，尚未读取文件正文", color = Color.White.copy(alpha = .82f), fontSize = 12.sp)
                }
            }
            OutlinedTextField(query, { query = it }, Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp),
                label = { Text("搜索资料") }, singleLine = true, shape = RoundedCornerShape(16.dp))
            LazyColumn(modifier = Modifier.weight(1f), contentPadding = PaddingValues(start = 20.dp, end = 20.dp, bottom = 28.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                if (visible.isEmpty()) item { Text("没有找到资料", color = Color(0xFF61746A), modifier = Modifier.padding(16.dp)) }
                items(visible, key = { it.id }) { material ->
                    val checked = material.id in selected
                    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp))
                        .background(Brush.horizontalGradient(listOf(Color(0xFFFBF8EB), Color(0xFFE4EEE9))))
                        .then(Modifier.clickable { onToggle(material.id, !checked) }).padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Description, contentDescription = null, tint = Color(0xFF325C4D))
                        Text(material.title, modifier = Modifier.weight(1f).padding(horizontal = 12.dp), fontSize = 13.sp,
                            color = Color(0xFF183A32), maxLines = 2, overflow = TextOverflow.Ellipsis)
                        Checkbox(checked = checked, onCheckedChange = { onToggle(material.id, it) })
                    }
                }
            }
        }
    }
}

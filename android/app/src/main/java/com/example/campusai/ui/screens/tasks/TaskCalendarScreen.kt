package com.example.campusai.ui.screens.tasks

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.theme.*

@Composable
fun TaskCalendarScreen(repository: AppRepository, onBack: () -> Unit, onOpenTask: (String) -> Unit) {
    val tasks by repository.tasks.collectAsState()
    LazyColumn(Modifier.fillMaxSize().background(Color(0xFFF4F5FF)), contentPadding = PaddingValues(16.dp, 22.dp, 16.dp, BottomDockReservedHeight + 20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Surface(shape = RoundedCornerShape(24.dp), color = Surface) { Column(Modifier.padding(18.dp)) { Row(verticalAlignment = Alignment.CenterVertically) { Icon(Icons.Default.CalendarMonth, null, tint = Primary); Spacer(Modifier.width(8.dp)); Text("任务时间线", fontWeight = FontWeight.Bold, fontSize = 18.sp) }; Spacer(Modifier.height(8.dp)); Text("可在任务详情中编辑截止时间；此页不会生成演示任务。", color = Muted, fontSize = 12.sp) } } }
        if (tasks.isEmpty()) item { Text("暂无后端任务记录", Modifier.fillMaxWidth().padding(36.dp), color = Muted) }
        items(tasks, key = { it.id }) { task -> Surface(onClick = { onOpenTask(task.id) }, color = Surface, shape = RoundedCornerShape(18.dp)) { Row(Modifier.padding(15.dp), verticalAlignment = Alignment.CenterVertically) { Column(Modifier.weight(1f)) { Text(task.title, fontWeight = FontWeight.SemiBold, color = TextPrimary); Text(task.due, color = Muted, fontSize = 12.sp) }; AssistChip(onClick = { onOpenTask(task.id) }, label = { Text(if (task.done) "已完成" else "查看") }) } } }
    }
}

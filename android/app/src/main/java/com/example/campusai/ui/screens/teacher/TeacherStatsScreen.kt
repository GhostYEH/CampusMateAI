package com.example.campusai.ui.screens.teacher

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.campusai.data.repository.LocalTeacherRepository
import com.example.campusai.ui.theme.*

@Composable
fun TeacherStatsScreen(repository: LocalTeacherRepository) {
    val drafts by repository.drafts.collectAsState()
    val announcements = drafts.count { it.kind == "通知草稿" }
    val assignments = drafts.count { it.kind == "作业草稿" }
    Column(Modifier.fillMaxSize().background(Background).padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Text("教学统计", style = MaterialTheme.typography.headlineMedium)
        Text("统计只展示本机已保存的教师草稿；真实提交数据需后端接口返回。", color = Muted)
        Stat("通知草稿", announcements.toString())
        Stat("作业草稿", assignments.toString())
        Stat("待发布内容", drafts.size.toString())
    }
}

@Composable
private fun Stat(label: String, value: String) {
    Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Surface)) {
        Row(Modifier.padding(18.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(label); Text(value, color = Primary, style = MaterialTheme.typography.titleLarge)
        }
    }
}

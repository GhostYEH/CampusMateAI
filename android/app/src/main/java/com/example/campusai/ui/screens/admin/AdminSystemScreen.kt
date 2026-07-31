package com.example.campusai.ui.screens.admin

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.ModeBadge
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch

@Composable
fun AdminSystemScreen(repository: AppRepository) {
    val mock by repository.mockMode.collectAsState()
    val scope = rememberCoroutineScope()
    var status by remember { mutableStateOf<AppRepository.BackendStatus?>(null) }
    var loading by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { loading = true; status = repository.refreshBackendStatus(); loading = false }
    val current = status
    Column(Modifier.fillMaxSize().background(Background).padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Column { Text("系统状态", style = MaterialTheme.typography.headlineMedium); Text("来自健康检查接口，不使用固定正常值", color = Muted) }
            ModeBadge(mock)
        }
        Button(onClick = { scope.launch { loading = true; status = repository.refreshBackendStatus(); loading = false } }, enabled = !loading) {
            Icon(Icons.Default.Refresh, null); Spacer(Modifier.width(8.dp)); Text(if (loading) "检查中…" else "手动刷新")
        }
        StatusCard("后端连接", when { loading -> "检查中"; current?.online == true -> "在线"; else -> "未连接" }, current?.error)
        StatusCard("运行模式", current?.mode ?: if (mock) "Mock 演示模式" else "未检查", null)
        StatusCard("知识库", current?.knowledgeDocuments?.let { "${it} 份文档" } ?: "暂无数据", if (current?.indexReady == false) "索引未就绪" else null)
        Text("普通学生和教师账号不会显示此页面；发布版请关闭 Mock 模式后再验证真实服务。", color = Muted, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun StatusCard(title: String, value: String, detail: String?) {
    Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Surface)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(title, color = Muted); Text(value, style = MaterialTheme.typography.titleLarge)
            detail?.let { Text(it, color = Danger) }
        }
    }
}

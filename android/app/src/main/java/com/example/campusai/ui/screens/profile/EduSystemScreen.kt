package com.example.campusai.ui.screens.profile

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.campusai.data.remote.ApiClient
import com.example.campusai.data.remote.EduSystemDto
import com.example.campusai.data.remote.EduDetectResult
import com.example.campusai.data.remote.EduBindingDto

object EduStateText {
    fun text(state: String): String = when (state) {
        "idle" -> "未连接"
        "connecting" -> "连接中…"
        "auth_required" -> "需要登录验证"
        "waiting_user_login" -> "等待用户登录"
        "need_captcha" -> "学校要求完成人机验证"
        "need_slider" -> "需要完成滑块验证"
        "need_sms" -> "需要短信验证码"
        "need_mfa" -> "需要多因素认证"
        "need_user_action" -> "需要用户操作"
        "authenticated" -> "已认证"
        "syncing" -> "同步中…"
        "connected" -> "已连接"
        "session_expired" -> "登录状态已过期，请重新验证"
        "auth_failed" -> "认证失败"
        "network_error" -> "网络错误"
        "system_unavailable" -> "教务系统暂不可用"
        "unsupported" -> "该教务系统暂未完成适配"
        "error" -> "连接出错"
        "active" -> "已连接"
        "unbound" -> "未绑定"
        else -> state
    }
}

@Composable
fun EduSystemScreen(
    universityId: String?,
    universityName: String?,
    onBack: () -> Unit,
) {
    var systems by remember { mutableStateOf<List<EduSystemDto>>(emptyList()) }
    var detect by remember { mutableStateOf<EduDetectResult?>(null) }
    var binding by remember { mutableStateOf<EduBindingDto?>(null) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf("") }

    LaunchedEffect(universityId) {
        if (universityId.isNullOrEmpty()) {
            loading = false
            return@LaunchedEffect
        }
        loading = true
        error = ""
        try {
            val api = ApiClient.api
            val systemsResp = api.listEduSystems(universityId)
            if (systemsResp.isSuccessful) {
                systems = systemsResp.body() ?: emptyList()
            }
            val detectResp = api.eduDetect(universityId)
            if (detectResp.isSuccessful) {
                detect = detectResp.body()
            }
            val bindingResp = api.getEduBinding()
            if (bindingResp.isSuccessful) {
                binding = bindingResp.body()
            }
        } catch (e: Exception) {
            error = e.message ?: "加载失败"
        } finally {
            loading = false
        }
    }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("教务系统", style = MaterialTheme.typography.headlineSmall)
            TextButton(onClick = onBack) { Text("返回") }
        }
        if (universityName != null) {
            Text(universityName, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        }
        Spacer(modifier = Modifier.height(8.dp))
        if (loading) {
            CircularProgressIndicator()
        } else if (error.isNotEmpty()) {
            Text(error, color = MaterialTheme.colorScheme.error)
        } else if (systems.isEmpty()) {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("暂未收录该校教务系统", fontWeight = FontWeight.Bold)
                    Text("你仍可继续使用手动课程表和其他 CampusMate 功能。", style = MaterialTheme.typography.bodySmall)
                }
            }
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(systems) { system -> EduSystemCard(system, binding) }
            }

        }
    }
}

@Composable
private fun EduSystemCard(system: EduSystemDto, binding: EduBindingDto?) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                system.name ?: when (system.system_key) {
                    "undergraduate-main" -> "本科教务系统"
                    "graduate-main" -> "研究生系统"
                    "legacy-undergraduate" -> "旧教务系统"
                    "sso" -> "统一身份认证"
                    else -> system.system_key
                },
                fontWeight = FontWeight.Bold,
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text("厂商：${system.provider}", style = MaterialTheme.typography.bodySmall)
            Text("状态：${system.status}", style = MaterialTheme.typography.bodySmall)
            Text("登录方式：${system.login_execution_mode}", style = MaterialTheme.typography.bodySmall)
            if (system.is_mock) {
                Text("⚠ Mock 数据", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
            }
            Spacer(modifier = Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for (feature in system.supported_features) {
                    Text("✓ $feature", style = MaterialTheme.typography.bodySmall)
                }
            }
            Spacer(modifier = Modifier.height(8.dp))

            if (binding != null && binding.connection_status == "active") {
                Text(EduStateText.text(binding.connection_status), color = MaterialTheme.colorScheme.primary)
            } else {
                Button(onClick = { /* TODO: navigate to connection flow */ }) {
                    Text("连接教务系统")
                }
            }
        }
    }
}
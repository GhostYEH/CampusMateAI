package com.example.campusai.ui.screens.profile

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.campusai.CampusAIApplication

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
    onBack: () -> Unit,
    onNavigateToLogin: (loginUrl: String, connectionId: String, allowedOrigins: List<String>) -> Unit,
    onOpenSchedule: () -> Unit = {},
    viewModel: EduViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsState()
    val binding by viewModel.binding.collectAsState()
    val universityId by viewModel.universityId.collectAsState()

    var portalUrl by remember { mutableStateOf("") }
    var sensitiveState by remember { mutableStateOf(EduLoginSensitiveState()) }
    var showDisconnectDialog by remember { mutableStateOf(false) }

    fun clearSensitiveState(event: EduLoginSensitiveEvent) {
        sensitiveState = reduceEduLoginSensitiveState(sensitiveState, event)
    }

    LaunchedEffect(Unit) { viewModel.loadInitial() }
    LaunchedEffect(state) {
        when (val current = state) {
            is EduUiState.WaitingUserLogin -> {
                clearSensitiveState(EduLoginSensitiveEvent.WEB_HANDOFF)
                onNavigateToLogin(current.loginUrl, current.connection.id, current.connection.allowed_origins)
            }
            is EduUiState.Connected, is EduUiState.Syncing, is EduUiState.Synced -> {
                clearSensitiveState(EduLoginSensitiveEvent.DIRECT_CONNECTED)
            }
            else -> Unit
        }
    }
    LaunchedEffect(binding?.connection_status) {
        if (binding?.connection_status in setOf("active", "connected")) {
            clearSensitiveState(EduLoginSensitiveEvent.DIRECT_CONNECTED)
        }
    }
    DisposableEffect(Unit) {
        onDispose {
            sensitiveState = reduceEduLoginSensitiveState(sensitiveState, EduLoginSensitiveEvent.DISPOSE)
        }
    }

    if (showDisconnectDialog) {
        AlertDialog(
            onDismissRequest = { showDisconnectDialog = false },
            title = { Text("断开教务系统") },
            text = { Text("断开后将停止自动同步，但已经同步的数据不会立即删除。") },
            confirmButton = {
                TextButton(onClick = {
                    showDisconnectDialog = false
                    clearSensitiveState(EduLoginSensitiveEvent.DISCONNECT)
                    viewModel.disconnect()
                }) { Text("确认断开") }
            },
            dismissButton = { TextButton(onClick = { showDisconnectDialog = false }) { Text("取消") } },
        )
    }

    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp).verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        if (universityId.isNullOrBlank()) {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("请先选择你的大学", fontWeight = FontWeight.Bold)
                    Text("教务系统连接需要先在个人中心选择所在大学。", style = MaterialTheme.typography.bodySmall)
                }
            }
            return@Column
        }

        val isConnected = binding?.connection_status == "active"

        if (isConnected) {
            ConnectedCard(
                binding = binding!!,
                state = state,
                onSync = { viewModel.manualSync() },
                onReconnect = {
                    clearSensitiveState(EduLoginSensitiveEvent.CONNECTION_REPLACED)
                    viewModel.reset()
                    portalUrl = ""
                },
                onDisconnect = { showDisconnectDialog = true },
                onOpenSchedule = onOpenSchedule,
            )
        } else {
            when (val s = state) {
                EduUiState.Idle, is EduUiState.Error -> {
                    if (state is EduUiState.Error) {
                        Text((state as EduUiState.Error).message, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                    }
                    PortalInputCard(
                        portalUrl = portalUrl,
                        onUrlChange = { portalUrl = it },
                        busy = false,
                        onDetect = {
                            val url = portalUrl.trim()
                            if (url.isNotEmpty()) {
                                clearSensitiveState(EduLoginSensitiveEvent.CONNECTION_REPLACED)
                                viewModel.probeAndCreateConnection(url)
                            }
                        },
                    )
                }
                EduUiState.Loading -> {
                    PortalInputCard(portalUrl = portalUrl, onUrlChange = { portalUrl = it }, busy = true, onDetect = {})
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.CenterHorizontally))
                }
                is EduUiState.ProbeReady -> {
                    ProbeResultCard(s.probe)
                    Text("该教务系统登录方式暂不支持自动分流，请尝试重新输入或联系管理员。", style = MaterialTheme.typography.bodySmall)
                }
                is EduUiState.NeedCredentials -> {
                    ProbeResultCard(
                        com.example.campusai.data.remote.EduProbeResult(
                            portal_url = "",
                            provider = s.connection.provider,
                            suggested_login_mode = "backend_http",
                            reachable = true,
                        )
                    )
                    CredentialFormCard(
                        username = sensitiveState.username,
                        password = sensitiveState.password,
                        onUsernameChange = { sensitiveState = sensitiveState.copy(username = it) },
                        onPasswordChange = { sensitiveState = sensitiveState.copy(password = it) },
                        busy = false,
                        onSubmit = { viewModel.submitCredentials(sensitiveState.username, sensitiveState.password) },
                    )
                }
                is EduUiState.WaitingUserLogin -> {
                    ProbeResultCard(
                        com.example.campusai.data.remote.EduProbeResult(
                            portal_url = s.loginUrl,
                            provider = s.connection.provider,
                            suggested_login_mode = "client_webview",
                            reachable = true,
                        )
                    )
                    Text("该教务系统需要在客户端浏览器中由您本人完成登录。", style = MaterialTheme.typography.bodySmall)
                    Text("正在打开学校登录页面…", style = MaterialTheme.typography.bodySmall)
                }
                is EduUiState.Verifying -> {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.CenterHorizontally))
                    Text(s.message, modifier = Modifier.align(Alignment.CenterHorizontally), style = MaterialTheme.typography.bodySmall)
                }
                is EduUiState.Connected -> {
                    Text("教务系统连接成功", color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                }
                is EduUiState.Syncing -> {
                    Text(s.message, fontWeight = FontWeight.Bold)
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                }
                is EduUiState.Synced -> {
                    val schedOk = s.scheduleResult?.status == "success"
                    val gradeOk = s.gradeResult?.status == "success"
                    Text(
                        "课表同步${if (schedOk) "成功（已导入 ${s.scheduleResult?.items_count ?: 0} 门）" else "失败"}，成绩同步${if (gradeOk) "成功" else "失败"}",
                        color = if (schedOk && gradeOk) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                        fontWeight = FontWeight.Bold,
                    )
                    s.scheduleResult?.error_message?.let { Text("课表: $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
                    s.gradeResult?.error_message?.let { Text("成绩: $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        if (schedOk) {
                            Button(onClick = onOpenSchedule, modifier = Modifier.weight(1f)) { Text("查看课表") }
                        }
                        OutlinedButton(
                            onClick = {
                                clearSensitiveState(EduLoginSensitiveEvent.CANCEL)
                                onBack()
                            },
                            modifier = Modifier.weight(1f),
                        ) { Text("完成") }
                    }
                }
            }
        }
    }
}

@Composable
private fun PortalInputCard(
    portalUrl: String,
    onUrlChange: (String) -> Unit,
    busy: Boolean,
    onDetect: () -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("连接教务系统", fontWeight = FontWeight.Bold)
            Text("输入高校教务系统网址，CampusMate 将自动识别系统类型。", style = MaterialTheme.typography.bodySmall)
            OutlinedTextField(
                value = portalUrl,
                onValueChange = onUrlChange,
                label = { Text("教务系统地址") },
                placeholder = { Text("https://jwxt.yourschool.edu.cn/") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                enabled = !busy,
            )
            Button(
                onClick = onDetect,
                modifier = Modifier.fillMaxWidth(),
                enabled = !busy && portalUrl.isNotBlank(),
            ) { Text(if (busy) "检测中…" else "检测教务系统") }
        }
    }
}

@Composable
private fun ProbeResultCard(probe: com.example.campusai.data.remote.EduProbeResult) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("已识别", fontWeight = FontWeight.Bold)
            if (probe.title != null) Text("页面：${probe.title}", style = MaterialTheme.typography.bodySmall)
            Text("系统厂商：${probe.provider}", style = MaterialTheme.typography.bodySmall)
            Text("登录方式：${when (probe.suggested_login_mode) { "client_webview" -> "客户端浏览器登录"; "backend_http" -> "账号密码登录"; else -> probe.suggested_login_mode }}", style = MaterialTheme.typography.bodySmall)
            if (!probe.reachable) Text("⚠ 无法访问该地址", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
        }
    }
}

@Composable
private fun CredentialFormCard(
    username: String,
    password: String,
    onUsernameChange: (String) -> Unit,
    onPasswordChange: (String) -> Unit,
    busy: Boolean,
    onSubmit: () -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("账号密码登录", fontWeight = FontWeight.Bold)
            OutlinedTextField(
                value = username, onValueChange = onUsernameChange,
                label = { Text("学号") }, singleLine = true,
                modifier = Modifier.fillMaxWidth(), enabled = !busy,
            )
            OutlinedTextField(
                value = password, onValueChange = onPasswordChange,
                label = { Text("密码") }, singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                modifier = Modifier.fillMaxWidth(), enabled = !busy,
            )
            Button(
                onClick = onSubmit, modifier = Modifier.fillMaxWidth(),
                enabled = !busy && username.isNotBlank() && password.isNotBlank(),
            ) { Text(if (busy) "验证中…" else "登录") }
            Text("密码仅用于本次登录校验，不会明文保存。", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun ConnectedCard(
    binding: com.example.campusai.data.remote.EduBindingDto,
    state: EduUiState,
    onSync: () -> Unit,
    onReconnect: () -> Unit,
    onDisconnect: () -> Unit,
    onOpenSchedule: () -> Unit = {},
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(binding.provider, fontWeight = FontWeight.Bold)
            Text("状态：${EduStateText.text(binding.connection_status)}", style = MaterialTheme.typography.bodySmall)
            binding.external_student_id?.let { Text("学号：$it", style = MaterialTheme.typography.bodySmall) }
            binding.last_synced_at?.let { Text("最后同步：$it", style = MaterialTheme.typography.bodySmall) }
            binding.last_error?.let { Text("错误：$it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
            Spacer(modifier = Modifier.height(8.dp))
            if (state is EduUiState.Syncing) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                Text(state.message, style = MaterialTheme.typography.bodySmall)
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = onSync, enabled = state !is EduUiState.Syncing) { Text("立即同步") }
                    OutlinedButton(onClick = onReconnect) { Text("重新登录") }
                    OutlinedButton(onClick = onDisconnect) { Text("断开") }
                }
                OutlinedButton(onClick = onOpenSchedule, modifier = Modifier.fillMaxWidth()) { Text("查看课表") }
            }
        }
    }
}

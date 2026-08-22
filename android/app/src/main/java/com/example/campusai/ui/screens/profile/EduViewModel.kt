package com.example.campusai.ui.screens.profile

import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.campusai.CampusAIApplication
import com.example.campusai.data.remote.EduBindingDto
import com.example.campusai.data.remote.EduConnectionDto
import com.example.campusai.data.remote.EduGradeItemsResponse
import com.example.campusai.data.remote.EduProbeResult
import com.example.campusai.data.remote.EduScheduleItemsResponse
import com.example.campusai.data.remote.EduSyncResult
import com.example.campusai.data.repository.EduRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** 教务连接流程 UI 状态。 */
sealed interface EduUiState {
    data object Idle : EduUiState
    data object Loading : EduUiState
    data class ProbeReady(val probe: EduProbeResult, val connection: EduConnectionDto) : EduUiState
    data class WaitingUserLogin(val connection: EduConnectionDto, val loginUrl: String) : EduUiState
    data class NeedCredentials(val connection: EduConnectionDto) : EduUiState
    data class Verifying(val message: String) : EduUiState
    data class Connected(val connection: EduConnectionDto) : EduUiState
    data class Syncing(val message: String, val scheduleDone: Boolean, val gradeDone: Boolean) : EduUiState
    data class Synced(val scheduleResult: EduSyncResult?, val gradeResult: EduSyncResult?) : EduUiState
    data class Error(val message: String) : EduUiState
}

/** EduViewModel — 教务系统连接流程状态机。 */
class EduViewModel(application: android.app.Application) : AndroidViewModel(application) {

    private val repo = EduRepository()

    private val _state = MutableStateFlow<EduUiState>(EduUiState.Idle)
    val state: StateFlow<EduUiState> = _state.asStateFlow()

    private val _binding = MutableStateFlow<EduBindingDto?>(null)
    val binding: StateFlow<EduBindingDto?> = _binding.asStateFlow()

    private val _universityId = MutableStateFlow<String?>(null)
    val universityId: StateFlow<String?> = _universityId.asStateFlow()

    private val _scheduleItems = MutableStateFlow<EduScheduleItemsResponse?>(null)
    val scheduleItems: StateFlow<EduScheduleItemsResponse?> = _scheduleItems.asStateFlow()

    private val _gradeItems = MutableStateFlow<EduGradeItemsResponse?>(null)
    val gradeItems: StateFlow<EduGradeItemsResponse?> = _gradeItems.asStateFlow()

    private var currentConnectionId: String? = null

    fun reset() {
        _state.value = EduUiState.Idle
    }

    /** 设置当前连接 ID（从 EduLoginScreen 进入时使用）。 */
    fun setConnectionId(connectionId: String) {
        currentConnectionId = connectionId
    }

    /** 加载当前绑定状态与大学 ID。 */
    fun loadInitial() {
        viewModelScope.launch {
            _state.value = EduUiState.Loading
            repo.getUniversityId().onSuccess { _universityId.value = it }
            repo.getBinding().onSuccess { _binding.value = it }
            _state.value = EduUiState.Idle
        }
    }

    /** Step 1: 探测 URL + 创建 connection。 */
    fun probeAndCreateConnection(portalUrl: String) {
        if (_state.value is EduUiState.Loading) return
        viewModelScope.launch {
            _state.value = EduUiState.Loading
            val uid = _universityId.value ?: repo.getUniversityId().getOrNull()
            if (uid.isNullOrBlank()) {
                _state.value = EduUiState.Error("请先在个人中心选择你的大学")
                return@launch
            }
            _universityId.value = uid
            val connResult = repo.createConnectionFromUrl(portalUrl, uid)
            connResult.onSuccess { conn ->
                currentConnectionId = conn.id
                val probe = EduProbeResult(
                    portal_url = portalUrl,
                    provider = conn.provider,
                    suggested_login_mode = conn.login_execution_mode,
                    reachable = true,
                )
                when (conn.login_execution_mode) {
                    "client_webview" -> {
                        _state.value = EduUiState.WaitingUserLogin(conn, portalUrl)
                        startPolling(conn.id)
                    }
                    "backend_http" -> _state.value = EduUiState.NeedCredentials(conn)
                    else -> _state.value = EduUiState.ProbeReady(probe, conn)
                }
            }.onFailure { _state.value = EduUiState.Error(it.message ?: "创建连接失败") }
        }
    }

    /** Step 2a: server_credentials 路径 — 提交账号密码。 */
    fun submitCredentials(username: String, password: String) {
        val connId = currentConnectionId ?: return
        if (_state.value is EduUiState.Verifying) return
        viewModelScope.launch {
            _state.value = EduUiState.Verifying("正在验证登录…")
            repo.continueWithCredentials(connId, username, password).onSuccess { conn ->
                if (conn.state == "connected") onConnected(conn)
                else if (conn.state == "auth_failed") _state.value = EduUiState.Error(conn.error_message ?: "账号或密码错误")
                else _state.value = EduUiState.Error(conn.error_message ?: "登录失败，状态: ${conn.state}")
            }.onFailure { _state.value = EduUiState.Error(it.message ?: "登录失败") }
        }
    }

    /** Step 2b: client_webview 路径 — 回传 cookies。 */
    fun submitCookies(cookies: Map<String, String>, currentUrl: String?, userAgent: String?) {
        val connId = currentConnectionId ?: return
        if (_state.value is EduUiState.Verifying) return
        viewModelScope.launch {
            _state.value = EduUiState.Verifying("正在验证登录状态…")
            repo.continueWithCookies(connId, cookies, currentUrl, userAgent).onSuccess { conn ->
                if (conn.state == "connected") onConnected(conn)
                else if (conn.state == "waiting_user_login") _state.value = EduUiState.Error("暂未检测到有效登录状态，请确认已进入教务系统首页")
                else if (conn.state == "auth_failed") _state.value = EduUiState.Error(conn.error_message ?: "Cookie 已失效")
                else _state.value = EduUiState.Error(conn.error_message ?: "验证失败，状态: ${conn.state}")
            }.onFailure { _state.value = EduUiState.Error(it.message ?: "回传 Cookie 失败") }
        }
    }

    private fun startPolling(connId: String) {
        viewModelScope.launch {
            repeat(60) {
                kotlinx.coroutines.delay(2000)
                if (_state.value !is EduUiState.WaitingUserLogin) return@repeat
                repo.pollConnection(connId).onSuccess { conn ->
                    if (conn.state == "connected") onConnected(conn)
                }
            }
        }
    }

    private fun onConnected(conn: EduConnectionDto) {
        _state.value = EduUiState.Connected(conn)
        viewModelScope.launch { repo.getBinding().onSuccess { _binding.value = it } }
        autoSync()
    }

    /** Step 3: 自动同步课表 + 成绩。 */
    fun autoSync() {
        viewModelScope.launch {
            _state.value = EduUiState.Syncing("正在同步课表…", false, false)
            val schedResult = repo.syncSchedule().getOrNull()
            _state.value = EduUiState.Syncing("正在同步成绩…", true, false)
            val gradeResult = repo.syncGrade().getOrNull()
            _state.value = EduUiState.Synced(schedResult, gradeResult)
            repo.getBinding().onSuccess { _binding.value = it }
        }
    }

    /** 手动同步（从已连接状态触发）。 */
    fun manualSync() {
        viewModelScope.launch {
            _state.value = EduUiState.Syncing("正在同步课表…", false, false)
            val schedResult = repo.syncSchedule().getOrNull()
            _state.value = EduUiState.Syncing("正在同步成绩…", true, false)
            val gradeResult = repo.syncGrade().getOrNull()
            _state.value = EduUiState.Synced(schedResult, gradeResult)
            repo.getBinding().onSuccess { _binding.value = it }
        }
    }

    /** 断开连接。 */
    fun disconnect() {
        viewModelScope.launch {
            _state.value = EduUiState.Loading
            repo.unbind().onSuccess {
                _binding.value = null
                _state.value = EduUiState.Idle
            }.onFailure { _state.value = EduUiState.Error(it.message ?: "断开失败") }
        }
    }

    fun loadScheduleItems(semester: String?) {
        viewModelScope.launch { repo.listScheduleItems(semester).onSuccess { _scheduleItems.value = it } }
    }

    fun loadGradeItems(semester: String?) {
        viewModelScope.launch { repo.listGradeItems(semester).onSuccess { _gradeItems.value = it } }
    }
}
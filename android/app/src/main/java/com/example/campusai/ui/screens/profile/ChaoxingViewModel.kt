package com.example.campusai.ui.screens.profile

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.workers.ChaoxingSyncScheduler
import com.example.campusai.workers.ChaoxingSyncStateStore
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch

data class ChaoxingUiState(
    val status: String = "checking", // "checking", "online", "offline", "expired"
    val lastSyncedAt: String? = null,
    val isSyncing: Boolean = false,
    val syncResult: String? = null,
    val isDisconnecting: Boolean = false,
    val isCheckingStatus: Boolean = true,
    val statusMessage: String? = null,
    val courses: Int = 0,
    val teachers: Int = 0,
    val pendingAssignments: Int = 0,
    val notices: Int = 0,
    val source: String? = null,
)

class ChaoxingViewModel(application: Application) : AndroidViewModel(application) {
    private val appRepository = AppRepository(application)
    private val syncScheduler = ChaoxingSyncScheduler(application)
    private val stateStore = ChaoxingSyncStateStore(application)

    private val _uiState = MutableStateFlow(ChaoxingUiState())
    val uiState: StateFlow<ChaoxingUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            stateStore.isConnected.collect { connected ->
                // Restore the last confirmed state immediately. The actual
                // remote check below is authoritative, but it must not make a
                // connected account look unbound while a slow check is running.
                if (_uiState.value.status == "checking") {
                    _uiState.value = _uiState.value.copy(status = if (connected) "online" else "offline")
                }
            }
        }
        checkStatus()
    }

    fun checkStatus() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isCheckingStatus = true, statusMessage = null)
            val res = appRepository.getChaoxingStatus()
            when (res?.status) {
                "online" -> {
                    _uiState.value = _uiState.value.copy(
                        status = "online",
                        lastSyncedAt = res.last_synced_at,
                        courses = res.courses,
                        teachers = res.teachers,
                        pendingAssignments = res.pending_assignments,
                        notices = res.notices,
                        source = res.source,
                        isCheckingStatus = false,
                    )
                    stateStore.setConnected(true)
                    stateStore.setReauthRequired(false)
                    syncScheduler.scheduleSyncWork()
                }
                "expired" -> {
                    _uiState.value = _uiState.value.copy(status = "expired", isCheckingStatus = false)
                    stateStore.setConnected(true)
                    stateStore.setReauthRequired(true)
                }
                "offline" -> {
                    // Only an explicit server response can clear a connection.
                    _uiState.value = _uiState.value.copy(
                        status = "offline",
                        lastSyncedAt = null,
                        isCheckingStatus = false,
                    )
                    stateStore.setConnected(false)
                    stateStore.setReauthRequired(false)
                    syncScheduler.cancelSyncWork()
                }
                else -> {
                    // unavailable/null is indeterminate, not an unbind event.
                    _uiState.value = _uiState.value.copy(
                        isCheckingStatus = false,
                        statusMessage = "暂时无法验证连接，已保留上次连接状态。",
                    )
                }
            }
        }
    }

    suspend fun login(username: String, password: String): Pair<Boolean, String> {
        val result = appRepository.loginChaoxing(username, password)
        if (result.first) {
            stateStore.setConnected(true)
            stateStore.setReauthRequired(false)
            syncScheduler.scheduleSyncWork()
            // Show a stable connected state before the verification request
            // finishes; this is especially important on slow networks.
            _uiState.value = _uiState.value.copy(status = "online", isCheckingStatus = true, statusMessage = null)
            checkStatus()
        }
        return result
    }

    fun syncNow(onRefreshNeeded: () -> Unit) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSyncing = true, syncResult = null)
            val result = appRepository.syncChaoxing()

            if (result.first) {
                _uiState.value = _uiState.value.copy(isSyncing = false, syncResult = "同步成功")
                stateStore.setReauthRequired(false)
                checkStatus()
                onRefreshNeeded()
                coroutineScope {
                    awaitAll(
                        async { appRepository.refreshCourses() },
                        async { appRepository.refreshTasks() },
                        async { appRepository.refreshNotices() },
                    )
                }
            } else if (result.second == "reauth_required" || result.second == "verification_required") {
                _uiState.value = _uiState.value.copy(
                    isSyncing = false,
                    syncResult = "登录已失效或需要验证，请重新登录",
                    status = "expired",
                    isCheckingStatus = false,
                )
                stateStore.setReauthRequired(true)
            } else {
                _uiState.value = _uiState.value.copy(isSyncing = false, syncResult = "同步失败: ${result.second}")
            }
        }
    }

    fun disconnect() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isDisconnecting = true)
            val disconnected = appRepository.disconnectChaoxing()
            if (disconnected) {
                stateStore.setConnected(false)
                stateStore.setReauthRequired(false)
                syncScheduler.cancelSyncWork()
                _uiState.value = _uiState.value.copy(
                    isDisconnecting = false,
                    status = "offline",
                    lastSyncedAt = null,
                    isCheckingStatus = false,
                    statusMessage = null,
                    syncResult = "已解除连接",
                )
            } else {
                _uiState.value = _uiState.value.copy(
                    isDisconnecting = false,
                    syncResult = "解除连接失败，请检查网络后重试",
                )
            }
        }
    }

    fun clearSyncResult() {
        _uiState.value = _uiState.value.copy(syncResult = null)
    }
}

package com.example.campusai.ui.screens.profile

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.workers.ChaoxingSyncScheduler
import com.example.campusai.workers.ChaoxingSyncStateStore
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ChaoxingUiState(
    val status: String = "offline", // "online", "offline", "expired"
    val lastSyncedAt: String? = null,
    val isSyncing: Boolean = false,
    val syncResult: String? = null,
    val isDisconnecting: Boolean = false,
)

class ChaoxingViewModel(application: Application) : AndroidViewModel(application) {
    private val appRepository = AppRepository(application)
    private val syncScheduler = ChaoxingSyncScheduler(application)
    private val stateStore = ChaoxingSyncStateStore(application)
    
    private val _uiState = MutableStateFlow(ChaoxingUiState())
    val uiState: StateFlow<ChaoxingUiState> = _uiState.asStateFlow()

    init {
        checkStatus()
    }

    fun checkStatus() {
        viewModelScope.launch {
            val res = appRepository.getChaoxingStatus()
            if (res != null) {
                _uiState.value = _uiState.value.copy(
                    status = res.status,
                    lastSyncedAt = res.last_synced_at
                )
                if (res.status == "online") {
                    stateStore.setConnected(true)
                    stateStore.setReauthRequired(false)
                    syncScheduler.scheduleSyncWork()
                } else if (res.status == "expired") {
                    stateStore.setConnected(true)
                    stateStore.setReauthRequired(true)
                }
            } else {
                _uiState.value = _uiState.value.copy(status = "offline")
                stateStore.setConnected(false)
                syncScheduler.cancelSyncWork()
            }
        }
    }

    suspend fun login(username: String, password: String): Pair<Boolean, String> {
        val result = appRepository.loginChaoxing(username, password)
        if (result.first) {
            stateStore.setConnected(true)
            stateStore.setReauthRequired(false)
            syncScheduler.scheduleSyncWork()
            checkStatus()
        }
        return result
    }
    
    fun syncNow(onRefreshNeeded: () -> Unit) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSyncing = true, syncResult = null)
            val result = appRepository.syncChaoxing()
            
            if (result.first) {
                _uiState.value = _uiState.value.copy(
                    isSyncing = false, 
                    syncResult = "同步成功"
                )
                stateStore.setReauthRequired(false)
                // update local state
                checkStatus()
                // notify UI to refresh Course, PersonalTask, Notice
                onRefreshNeeded()
                appRepository.refreshCourses()
                appRepository.refreshTasks()
                appRepository.refreshNotices()
            } else {
                if (result.second == "reauth_required" || result.second == "verification_required") {
                    _uiState.value = _uiState.value.copy(
                        isSyncing = false, 
                        syncResult = "登录已失效或需要验证，请重新登录",
                        status = "expired"
                    )
                    stateStore.setReauthRequired(true)
                } else {
                    _uiState.value = _uiState.value.copy(
                        isSyncing = false, 
                        syncResult = "同步失败: ${result.second}"
                    )
                }
            }
        }
    }

    fun disconnect() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isDisconnecting = true)
            appRepository.disconnectChaoxing()
            stateStore.setConnected(false)
            syncScheduler.cancelSyncWork()
            _uiState.value = _uiState.value.copy(
                isDisconnecting = false,
                status = "offline",
                lastSyncedAt = null,
                syncResult = "已解除连接"
            )
        }
    }
    
    fun clearSyncResult() {
        _uiState.value = _uiState.value.copy(syncResult = null)
    }
}

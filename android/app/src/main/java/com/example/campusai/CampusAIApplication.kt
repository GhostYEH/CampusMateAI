package com.example.campusai

import android.app.Application
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.ModuleRepositories
import com.example.campusai.data.repository.NotificationInboxRepository
import com.example.campusai.workers.ChaoxingSyncScheduler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class CampusAIApplication : Application() {
    private val applicationScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    override fun onCreate() {
        super.onCreate()
        applicationScope.launch {
            ChaoxingSyncScheduler(this@CampusAIApplication).scheduleSyncWork()
        }
    }

    val repository: AppRepository by lazy {
        AppRepository(this)
    }
    
    val moduleRepositories: ModuleRepositories by lazy {
        ModuleRepositories.create(this, repository)
    }

    val notificationInboxRepository: NotificationInboxRepository by lazy {
        NotificationInboxRepository(this)
    }
}

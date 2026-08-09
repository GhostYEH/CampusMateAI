package com.example.campusai

import android.app.Application
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.ModuleRepositories
import com.example.campusai.data.repository.NotificationInboxRepository

class CampusAIApplication : Application() {
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

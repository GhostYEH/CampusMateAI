package com.example.campusai

import android.app.Application
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.ModuleRepositories

class CampusAIApplication : Application() {
    val repository: AppRepository by lazy {
        AppRepository(this)
    }
    
    val moduleRepositories: ModuleRepositories by lazy {
        ModuleRepositories.create(this, repository)
    }
}

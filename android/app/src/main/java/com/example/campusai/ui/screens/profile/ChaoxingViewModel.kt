package com.example.campusai.ui.screens.profile

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import com.example.campusai.data.repository.AppRepository

class ChaoxingViewModel(application: Application) : AndroidViewModel(application) {
    private val appRepository = AppRepository(application)

    suspend fun login(username: String, password: String): Boolean {
        return appRepository.loginChaoxing(username, password)
    }
}

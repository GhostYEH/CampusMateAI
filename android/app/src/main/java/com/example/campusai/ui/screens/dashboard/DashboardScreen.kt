package com.example.campusai.ui.screens.dashboard

import androidx.compose.runtime.Composable
import com.example.campusai.data.repository.AppRepository

@Composable
fun DashboardScreen(
    repository: AppRepository,
    onNavigate: (String) -> Unit,
) {
    ClassicDashboardScreen(repository, onNavigate)
}

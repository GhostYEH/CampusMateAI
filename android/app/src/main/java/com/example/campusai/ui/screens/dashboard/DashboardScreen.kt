package com.example.campusai.ui.screens.dashboard

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.campusai.data.local.DashboardStyle
import com.example.campusai.data.repository.ApiFocusRepository
import com.example.campusai.data.repository.AppRepository

@Composable
fun DashboardScreen(
    repository: AppRepository,
    focusRepository: ApiFocusRepository,
    onNavigate: (String) -> Unit,
) {
    val style by repository.dashboardStyle.collectAsStateWithLifecycle()
    when (style) {
        DashboardStyle.CLASSIC -> ClassicDashboardScreen(repository, onNavigate)
        DashboardStyle.IMMERSIVE -> ImmersiveDashboardScreen(
            repository = repository,
            focusRepository = focusRepository,
            onNavigate = onNavigate,
        )
    }
}

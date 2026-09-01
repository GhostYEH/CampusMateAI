package com.example.campusai.ui.screens.dashboard

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.campusai.data.repository.ApiFocusRepository
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.ExamRepository
import com.example.campusai.features.gamification.DashboardStyle
import com.example.campusai.ui.screens.dashboard.gamified.GamifiedDashboardScreen
import com.example.campusai.ui.screens.dashboard.gamified.GamifiedDashboardViewModel

@Composable
fun DashboardScreen(
    repository: AppRepository,
    examRepository: ExamRepository,
    focusRepository: ApiFocusRepository,
    onNavigate: (String) -> Unit,
) {
    val style by repository.dashboardStyle.collectAsStateWithLifecycle()
    when (style) {
        DashboardStyle.CLASSIC -> ClassicDashboardScreen(repository, onNavigate)
        DashboardStyle.GAMIFIED -> {
            val dashboardViewModel: GamifiedDashboardViewModel = viewModel(
                factory = GamifiedDashboardViewModel.factory(repository, examRepository, focusRepository),
            )
            val state by dashboardViewModel.state.collectAsStateWithLifecycle()
            GamifiedDashboardScreen(state = state, onNavigate = onNavigate)
        }
    }
}

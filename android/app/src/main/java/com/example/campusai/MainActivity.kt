package com.example.campusai

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat
import androidx.navigation.compose.rememberNavController
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.navigation.AppNavHost
import com.example.campusai.ui.screens.login.LoginScreen
import com.example.campusai.ui.screens.shell.AppShell
import com.example.campusai.ui.theme.CampusAITheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val repository = AppRepository(application)

        setContent {
            val darkMode by repository.darkMode.collectAsState()
            val view = LocalView.current
            SideEffect {
                WindowCompat.getInsetsController(window, view).apply {
                    isAppearanceLightStatusBars = !darkMode
                    isAppearanceLightNavigationBars = !darkMode
                }
            }
            CampusAITheme(darkTheme = darkMode) {
                CampusAIApp(repository)
            }
        }
    }
}

@Composable
fun CampusAIApp(repository: AppRepository) {
    val session by repository.session.collectAsState()
    val navController = rememberNavController()

    if (session == null) {
        LoginScreen(
            repository = repository,
            onLoginSuccess = { }
        )
    } else {
        AppShell(
            navController = navController,
            repository = repository
        ) {
            AppNavHost(
                navController = navController,
                repository = repository
            )
        }
    }
}

package com.example.campusai

import android.graphics.Color as AndroidColor
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat
import androidx.navigation.compose.rememberNavController
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.ModuleRepositories
import com.example.campusai.ui.navigation.AppNavHost
import com.example.campusai.ui.screens.login.LoginScreen
import com.example.campusai.ui.screens.shell.AppShell
import com.example.campusai.ui.theme.CampusAITheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        // 在 super.onCreate 之前切换回正常主题，
        // 使启动画面主题的 windowBackground 仅在启动瞬间显示
        setTheme(R.style.Theme_Campusai)
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        // The bottom dock is intentionally floating. Keep the system navigation
        // area transparent so it cannot render a second opaque bar behind it.
        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.navigationBarColor = AndroidColor.TRANSPARENT
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            window.isNavigationBarContrastEnforced = false
        }

        val repository = AppRepository(application)
        val moduleRepositories = ModuleRepositories.create(application, repository)

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
                CampusAIApp(repository, moduleRepositories)
            }
        }
    }
}

@Composable
fun CampusAIApp(repository: AppRepository, modules: ModuleRepositories) {
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
                repository = repository,
                modules = modules,
            )
        }
    }
}

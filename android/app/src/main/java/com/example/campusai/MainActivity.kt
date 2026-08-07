package com.example.campusai

import android.content.Intent
import android.graphics.Color as AndroidColor
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalView
import androidx.core.app.NotificationManagerCompat
import androidx.core.view.WindowCompat
import androidx.navigation.compose.rememberNavController
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.ModuleRepositories
import com.example.campusai.ui.navigation.AppNavHost
import com.example.campusai.ui.screens.login.LoginScreen
import com.example.campusai.ui.screens.shell.AppShell
import com.example.campusai.ui.theme.CampusAITheme

import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.example.campusai.workers.ChaoxingSyncWorker
import java.util.concurrent.TimeUnit

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        // 在 super.onCreate 之前切换回正常主题，
        // 使启动画面主题的 windowBackground 仅在启动瞬间显示
        setTheme(R.style.Theme_Campusai)
        super.onCreate(savedInstanceState)

        val workRequest = PeriodicWorkRequestBuilder<ChaoxingSyncWorker>(1, TimeUnit.HOURS).build()
        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "chaoxing_sync",
            androidx.work.ExistingPeriodicWorkPolicy.KEEP,
            workRequest
        )

        enableEdgeToEdge()
        // The bottom dock is intentionally floating. Keep the system navigation
        // area transparent so it cannot render a second opaque bar behind it.
        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.navigationBarColor = AndroidColor.TRANSPARENT
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            window.isNavigationBarContrastEnforced = false
        }

        val repository = (application as CampusAIApplication).repository
        val moduleRepositories = (application as CampusAIApplication).moduleRepositories

        setContent {
            val darkMode by repository.darkMode.collectAsState()
            val reduceMotion by repository.reduceMotion.collectAsState()
            val view = LocalView.current
            SideEffect {
                WindowCompat.getInsetsController(window, view).apply {
                    isAppearanceLightStatusBars = !darkMode
                    isAppearanceLightNavigationBars = !darkMode
                }
            }
            CampusAITheme(darkTheme = darkMode, reduceMotion = reduceMotion) {
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
        // 应用启动时，自动同步一次学习通任务
        LaunchedEffect(session) {
            repository.syncChaoxing()
            repository.refreshTasks()
            
            // 检查是否有未上传的通知，如果有则重新调度 Worker
            val pendingNotices = repository.getPendingNotices().filter { it.status == "pending" }
            if (pendingNotices.isNotEmpty()) {
                repository.scheduleNoticeUploadWorker()
            }
        }

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

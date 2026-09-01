package com.example.campusai

import androidx.lifecycle.compose.collectAsStateWithLifecycle

import android.content.Intent
import android.graphics.Color as AndroidColor
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.app.NotificationManagerCompat
import androidx.core.view.WindowCompat
import androidx.navigation.compose.rememberNavController
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.ModuleRepositories
import com.example.campusai.ui.navigation.AppNavHost
import com.example.campusai.ui.screens.login.LoginScreen
import com.example.campusai.ui.screens.shell.AppShell
import com.example.campusai.ui.system.systemBarPolicy
import com.example.campusai.ui.theme.CampusAITheme
import com.example.campusai.ui.glass.CampusGlassScene

import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.first

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
        window.statusBarColor = AndroidColor.TRANSPARENT
        window.navigationBarColor = AndroidColor.TRANSPARENT
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            window.navigationBarDividerColor = AndroidColor.TRANSPARENT
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            window.isStatusBarContrastEnforced = false
            window.isNavigationBarContrastEnforced = false
        }

        val repository = (application as CampusAIApplication).repository
        val moduleRepositories = (application as CampusAIApplication).moduleRepositories
        val notificationInboxRepository = (application as CampusAIApplication).notificationInboxRepository

        setContent {
            val session by repository.session.collectAsStateWithLifecycle()
            val darkMode by repository.darkMode.collectAsStateWithLifecycle()
            val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
            val view = LocalView.current
            SideEffect {
                val policy = systemBarPolicy(
                    route = null,
                    darkTheme = darkMode,
                    authenticated = session != null,
                )
                WindowCompat.getInsetsController(window, view).apply {
                    isAppearanceLightStatusBars = policy.darkStatusBarIcons
                    isAppearanceLightNavigationBars = policy.darkNavigationBarIcons
                }
            }
            CampusAITheme(darkTheme = darkMode, reduceMotion = reduceMotion) {
                CampusGlassScene(darkMode = darkMode) {
                    CampusAIApp(repository, moduleRepositories, notificationInboxRepository)
                }
            }
        }
    }

}

@Composable
fun CampusAIApp(
    repository: AppRepository,
    modules: ModuleRepositories,
    notificationInboxRepository: com.example.campusai.data.repository.NotificationInboxRepository,
) {
    val session by repository.session.collectAsStateWithLifecycle()
    val navController = rememberNavController()
    val context = LocalContext.current

    if (session == null) {
        LoginScreen(
            repository = repository,
            onLoginSuccess = { }
        )
    } else {
        // 应用启动时，自动同步一次学习通任务
        LaunchedEffect(session) {
            val syncStateStore = com.example.campusai.workers.ChaoxingSyncStateStore(context)
            if (syncStateStore.isConnected.first()) {
                val syncResult = repository.syncChaoxing()
                if (syncResult.first) {
                    coroutineScope {
                        awaitAll(
                            async { repository.refreshCourses() },
                            async { repository.refreshTasks() },
                            async { repository.refreshNotices() },
                        )
                    }
                } else if (syncResult.second == "reauth_required" || syncResult.second == "verification_required") {
                    syncStateStore.setReauthRequired(true)
                }
            }
            
            // Room is the durable notification queue. A startup wake-up recovers
            // READY/RETRY rows left by process death or device reboot.
            if (notificationInboxRepository.hasPending()) {
                com.example.campusai.workers.NoticeWorkScheduler.scheduleUpload(context)
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
                notificationInboxRepository = notificationInboxRepository,
            )
        }
    }
}

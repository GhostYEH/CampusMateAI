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
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.Image
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.background
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.text.font.FontWeight
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
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
import com.example.campusai.ui.screens.tasks.isCurrentSemesterAssignment
import com.example.campusai.ui.system.systemBarPolicy
import com.example.campusai.ui.theme.CampusAITheme
import com.example.campusai.ui.theme.LocalReduceMotion
import com.example.campusai.ui.glass.CampusGlassScene

import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.first
import kotlin.math.roundToInt

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
            var showLaunchArtwork by rememberSaveable { mutableStateOf(true) }
            LaunchedEffect(Unit) {
                kotlinx.coroutines.delay(1200)
                showLaunchArtwork = false
            }
            val view = LocalView.current
            SideEffect {
                val policy = systemBarPolicy(
                    route = null,
                    darkTheme = darkMode,
                    authenticated = session != null,
                )
                WindowCompat.getInsetsController(window, view).apply {
                    isAppearanceLightStatusBars = !showLaunchArtwork && policy.darkStatusBarIcons
                    isAppearanceLightNavigationBars = !showLaunchArtwork && policy.darkNavigationBarIcons
                }
            }
            CampusAITheme(darkTheme = darkMode, reduceMotion = reduceMotion) {
                Box(Modifier.fillMaxSize()) {
                    CampusGlassScene(darkMode = darkMode) {
                        CampusAIApp(repository, moduleRepositories, notificationInboxRepository)
                    }
                    AnimatedVisibility(
                        visible = showLaunchArtwork,
                        enter = EnterTransition.None,
                        exit = if (reduceMotion) ExitTransition.None else fadeOut(tween(280)),
                    ) {
                        Image(
                            painter = painterResource(R.drawable.splash_twilight_v1),
                            contentDescription = null,
                            contentScale = ContentScale.Crop,
                            modifier = Modifier.fillMaxSize(),
                        )
                    }
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
    val reduceMotion = LocalReduceMotion.current
    val navController = rememberNavController()
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var appEntry by remember { mutableIntStateOf(1) }
    var showTaskReminder by remember { mutableStateOf(false) }
    var reminderDismissed by remember(appEntry) { mutableStateOf(false) }
    var reminderDragY by remember { mutableFloatStateOf(0f) }
    var reminderCount by remember { mutableIntStateOf(0) }
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_START) appEntry++
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    if (session == null) {
        LoginScreen(
            repository = repository,
            onLoginSuccess = { }
        )
    } else {
        LaunchedEffect(session?.accountId, appEntry) {
            repository.refreshCourses()
            repository.refreshTasks()
            reminderCount = repository.tasks.value.count {
                !it.done && it.isCurrentSemesterAssignment(repository.courses.value, java.time.Instant.now())
            }
            showTaskReminder = reminderCount > 0 && !reminderDismissed
        }
        LaunchedEffect(showTaskReminder, appEntry) {
            if (showTaskReminder) {
                kotlinx.coroutines.delay(6000)
                showTaskReminder = false
            }
        }
        // 应用启动时，自动同步一次学习通任务
        LaunchedEffect(session) {
            val syncStateStore = com.example.campusai.workers.ChaoxingSyncStateStore(context)
            if (syncStateStore.isConnected.first()) {
                val syncResult = repository.syncChaoxing()
                if (syncResult.first) {
                    repository.refreshCourses()
                    repository.refreshTasks()
                    repository.refreshNotices()
                    reminderCount = repository.tasks.value.count {
                        !it.done && it.isCurrentSemesterAssignment(repository.courses.value, java.time.Instant.now())
                    }
                    if (reminderCount > 0 && !reminderDismissed) showTaskReminder = true
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

        Box(Modifier.fillMaxSize()) {
            AppShell(navController = navController, repository = repository) {
                AppNavHost(
                    navController = navController,
                    repository = repository,
                    modules = modules,
                    notificationInboxRepository = notificationInboxRepository,
                )
            }
            AnimatedVisibility(
                visible = showTaskReminder,
                modifier = Modifier.align(Alignment.TopCenter).statusBarsPadding(),
                enter = if (reduceMotion) EnterTransition.None else slideInVertically(initialOffsetY = { -it }) + fadeIn(),
                exit = if (reduceMotion) ExitTransition.None else slideOutVertically(targetOffsetY = { -it }) + fadeOut(),
            ) {
                Surface(
                    onClick = {
                        reminderDismissed = true
                        showTaskReminder = false
                        navController.navigate("tasks") { launchSingleTop = true }
                    },
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)
                        .offset { IntOffset(0, reminderDragY.roundToInt()) }
                        .pointerInput(Unit) {
                            detectVerticalDragGestures(
                                onVerticalDrag = { change, dragAmount ->
                                    reminderDragY = (reminderDragY + dragAmount).coerceAtMost(0f)
                                    change.consume()
                                },
                                onDragEnd = {
                                    if (reminderDragY < -48.dp.toPx()) {
                                        reminderDismissed = true
                                        showTaskReminder = false
                                    }
                                    reminderDragY = 0f
                                },
                                onDragCancel = { reminderDragY = 0f },
                            )
                        },
                    shape = RoundedCornerShape(18.dp),
                    color = Color(0xFFF9F2E6),
                    shadowElevation = 10.dp,
                ) {
                    Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("课程待办提醒", color = Color(0xFF203B32), fontWeight = FontWeight.Bold)
                            Text("还有 $reminderCount 项本学期作业待处理 · 点击查看",
                                color = Color(0xFF4C655A), fontSize = 13.sp)
                        }
                        Text("查看", color = Color(0xFF295643), fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}

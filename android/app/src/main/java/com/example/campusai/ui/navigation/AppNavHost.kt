package com.example.campusai.ui.navigation

import androidx.compose.animation.*
import androidx.compose.animation.core.tween
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.graphics.TransformOrigin
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.ModuleRepositories
import com.example.campusai.data.repository.NotificationInboxRepository
import com.example.campusai.ui.screens.classrooms.ClassroomsScreen
import com.example.campusai.ui.screens.counselor.CounselorScreen
import com.example.campusai.ui.screens.courses.CoursesScreen
import com.example.campusai.ui.screens.dashboard.DashboardScreen
import com.example.campusai.ui.screens.exams.ExamDetailScreen
import com.example.campusai.ui.screens.exams.ExamEditScreen
import com.example.campusai.ui.screens.exams.ExamsScreen
import com.example.campusai.ui.screens.focus.FocusScreen

import com.example.campusai.ui.screens.lostfound.LostFoundDetailScreen
import com.example.campusai.ui.screens.lostfound.LostFoundPublishScreen
import com.example.campusai.ui.screens.lostfound.LostFoundScreen
import com.example.campusai.ui.screens.lostfound.MyLostFoundScreen
import com.example.campusai.ui.screens.notifications.CampusNewsDetailScreen
import com.example.campusai.ui.screens.notifications.CampusNewsScreen
import com.example.campusai.ui.screens.notifications.NotificationsScreen
import com.example.campusai.ui.screens.profile.AccountScreen
import com.example.campusai.ui.screens.profile.ChaoxingLoginScreen
import com.example.campusai.ui.screens.profile.ExpressionContributionScreen
import com.example.campusai.ui.screens.profile.NotificationSettingsScreen
import com.example.campusai.ui.screens.profile.PersonalHubScreen
import com.example.campusai.ui.screens.profile.ProfileScreen
import com.example.campusai.ui.screens.profile.SettingsScreen

import com.example.campusai.ui.screens.services.GenericServiceFormScreen
import com.example.campusai.ui.screens.services.LeaveRequestScreen
import com.example.campusai.ui.screens.services.MyRequestsScreen
import com.example.campusai.ui.screens.services.RepairRequestScreen
import com.example.campusai.ui.screens.services.ServiceRequestDetailScreen
import com.example.campusai.ui.screens.services.ServicesScreen
import com.example.campusai.ui.screens.tasks.TasksScreen
import com.example.campusai.ui.screens.tasks.TaskDetailScreen
import com.example.campusai.ui.screens.tasks.TaskCalendarScreen
import java.net.URLEncoder

@Composable
fun AppNavHost(
    navController: NavHostController,
    repository: AppRepository,
    modules: ModuleRepositories,
    notificationInboxRepository: NotificationInboxRepository,
) {
    fun go(route: String) = navController.navigate(route) { launchSingleTop = true }
    val reduceMotion by repository.reduceMotion.collectAsState()

    NavHost(
        navController = navController,
        startDestination = "home",
        enterTransition = {
            if (reduceMotion) {
                EnterTransition.None
            } else {
                fadeIn(tween(360, easing = androidx.compose.animation.core.FastOutSlowInEasing)) +
                    slideInHorizontally(
                        animationSpec = tween(360, easing = androidx.compose.animation.core.FastOutSlowInEasing),
                        initialOffsetX = { it / 10 },
                    ) +
                    scaleIn(
                        animationSpec = tween(360, easing = androidx.compose.animation.core.FastOutSlowInEasing),
                        initialScale = .985f,
                        transformOrigin = TransformOrigin(.5f, .08f),
                    )
            }
        },
        exitTransition = {
            if (reduceMotion) {
                ExitTransition.None
            } else {
                fadeOut(tween(260, easing = androidx.compose.animation.core.FastOutSlowInEasing)) +
                    slideOutHorizontally(
                        animationSpec = tween(260, easing = androidx.compose.animation.core.FastOutSlowInEasing),
                        targetOffsetX = { -it / 16 },
                    ) +
                    scaleOut(
                        animationSpec = tween(260, easing = androidx.compose.animation.core.FastOutSlowInEasing),
                        targetScale = .995f,
                        transformOrigin = TransformOrigin(.5f, .08f),
                    )
            }
        },
        popEnterTransition = {
            if (reduceMotion) {
                EnterTransition.None
            } else {
                fadeIn(tween(320, easing = androidx.compose.animation.core.FastOutSlowInEasing)) +
                    slideInHorizontally(
                        animationSpec = tween(320, easing = androidx.compose.animation.core.FastOutSlowInEasing),
                        initialOffsetX = { -it / 12 },
                    ) +
                    scaleIn(
                        animationSpec = tween(320, easing = androidx.compose.animation.core.FastOutSlowInEasing),
                        initialScale = .99f,
                        transformOrigin = TransformOrigin(.5f, .08f),
                    )
            }
        },
        popExitTransition = {
            if (reduceMotion) {
                ExitTransition.None
            } else {
                fadeOut(tween(230, easing = androidx.compose.animation.core.FastOutSlowInEasing)) +
                    slideOutHorizontally(
                        animationSpec = tween(230, easing = androidx.compose.animation.core.FastOutSlowInEasing),
                        targetOffsetX = { it / 14 },
                    )
            }
        },
    ) {
        composable("home") {
            DashboardScreen(repository) { route ->
                navController.navigate(route) {
                    popUpTo("home") { inclusive = false }
                    launchSingleTop = true
                }
            }
        }
        composable("tasks") {
            TasksScreen(repository) { route -> go(route) }
        }
        composable("task_calendar") {
            TaskCalendarScreen(
                repository = repository,
                onBack = { navController.popBackStack() },
                onOpenTask = { taskId -> go("task_detail/$taskId") },
            )
        }
        composable(
            route = "task_detail/{taskId}",
            arguments = listOf(navArgument("taskId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val taskId = backStackEntry.arguments?.getString("taskId").orEmpty()
            TaskDetailScreen(
                taskId = taskId,
                repository = repository,
                onBack = { navController.popBackStack() },
                onTaskDeleted = { navController.popBackStack() },
            )
        }
        composable("notifications") {
            NotificationsScreen(repository, notificationInboxRepository)
        }
        composable("campus-news") {
            CampusNewsScreen(
                repository = repository,
                onBack = { navController.popBackStack() },
                onOpenNews = { id -> go("campus-news-detail/$id") },
            )
        }
        composable(
            route = "counselor?prompt={prompt}",
            arguments = listOf(navArgument("prompt") {
                type = NavType.StringType
                nullable = true
                defaultValue = null
            }),
        ) { backStackEntry ->
            CounselorScreen(
                repository = repository,
                initialPrompt = backStackEntry.arguments?.getString("prompt"),
            )
        }
        // Historical study links now enter the one official Focus timer; no second timer exists.
        composable("study") {
            LaunchedEffect(Unit) {
                navController.navigate("focus") {
                    popUpTo("study") { inclusive = true }
                    launchSingleTop = true
                }
            }
        }
        composable("courses") { CoursesScreen(repository) }
        composable("profile") {
            ProfileScreen(repository) { route -> go(route) }
        }
        composable("settings") {
            SettingsScreen(
                repository = repository,
                onBack = { navController.popBackStack() },
                onOpenContribution = { navController.navigate("expression-contribution") },
                onOpenNotificationSettings = { navController.navigate("notification-settings") },
                onOpenChaoxingLogin = { navController.navigate("chaoxing") },
            )
        }
        composable("notification-settings") {
            NotificationSettingsScreen(repository)
        }
        composable("chaoxing") {
            com.example.campusai.ui.screens.profile.ChaoxingScreen(
                onBack = { navController.popBackStack() },
                onNavigateToLogin = { navController.navigate("chaoxing-login") }
            )
        }
        composable("chaoxing-login") {
            ChaoxingLoginScreen(onLoginSuccess = { navController.popBackStack() })
        }
        composable("expression-contribution") {
            ExpressionContributionScreen(repository) { navController.popBackStack() }
        }
        composable("account") { AccountScreen(repository) { navController.popBackStack() } }


        composable("files") {
            PersonalHubScreen(
                repository = repository,
                initialSection = "files",
                onBack = { navController.popBackStack() },
                onNavigate = { route -> go(route) },
            )
        }
        composable("activities") {
            PersonalHubScreen(
                repository = repository,
                initialSection = "activities",
                onBack = { navController.popBackStack() },
                onNavigate = { route -> go(route) },
            )
        }
        composable("favorites") {
            PersonalHubScreen(
                repository = repository,
                initialSection = "favorites",
                onBack = { navController.popBackStack() },
                onNavigate = { route -> go(route) },
            )
        }

        composable(
            route = "campus-news-detail/{newsId}",
            arguments = listOf(navArgument("newsId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val newsId = backStackEntry.arguments?.getString("newsId") ?: return@composable
            CampusNewsDetailScreen(
                newsId = newsId,
                repository = repository,
                onBack = { navController.popBackStack() },
            )
        }

        // ── 考试安排 ──
        composable("exams") {
            val reduceMotion by repository.reduceMotion.collectAsState()
            ExamsScreen(
                repository = modules.exams,
                reduceMotion = reduceMotion,
                onBack = { navController.popBackStack() },
                onOpenDetail = { id -> go("exam_detail/$id") },
                onOpenEdit = { id -> go("exam_edit/${id ?: 0L}") },
            )
        }
        composable(
            route = "exam_detail/{examId}",
            arguments = listOf(navArgument("examId") { type = NavType.LongType }),
        ) { backStackEntry ->
            val examId = backStackEntry.arguments?.getLong("examId") ?: 0L
            ExamDetailScreen(
                examId = examId,
                repository = modules.exams,
                onBack = { navController.popBackStack() },
                onEdit = { id -> go("exam_edit/$id") },
            )
        }
        composable(
            route = "exam_edit/{examId}",
            arguments = listOf(navArgument("examId") { type = NavType.LongType }),
        ) { backStackEntry ->
            ExamEditScreen(
                examId = backStackEntry.arguments?.getLong("examId") ?: 0L,
                repository = modules.exams,
                appRepository = repository,
                onBack = { navController.popBackStack() },
            )
        }

        // ── 空教室 ──
        composable("classrooms") {
            val reduceMotion by repository.reduceMotion.collectAsState()
            ClassroomsScreen(
                repository = modules.classrooms,
                reduceMotion = reduceMotion,
                onBack = { navController.popBackStack() },
            )
        }

        // ── 办事大厅 ──
        composable("services") {
            val reduceMotion by repository.reduceMotion.collectAsState()
            ServicesScreen(
                repository = modules.services,
                reduceMotion = reduceMotion,
                onBack = { navController.popBackStack() },
                onNavigate = { route -> go(route) },
            )
        }
        composable("service_leave") {
            LeaveRequestScreen(
                repository = modules.services,
                onBack = { navController.popBackStack() },
                onSubmitted = { id ->
                    navController.navigate("service_detail/$id") {
                        popUpTo("services") { inclusive = false }
                        launchSingleTop = true
                    }
                },
            )
        }
        composable("service_repair") {
            RepairRequestScreen(
                repository = modules.services,
                onBack = { navController.popBackStack() },
                onSubmitted = { id ->
                    navController.navigate("service_detail/$id") {
                        popUpTo("services") { inclusive = false }
                        launchSingleTop = true
                    }
                },
            )
        }
        composable(
            route = "service_form/{kind}",
            arguments = listOf(navArgument("kind") { type = NavType.StringType }),
        ) { backStackEntry ->
            GenericServiceFormScreen(
                kind = backStackEntry.arguments?.getString("kind") ?: "feedback",
                repository = modules.services,
                onBack = { navController.popBackStack() },
                onSubmitted = { id ->
                    navController.navigate("service_detail/$id") {
                        popUpTo("services") { inclusive = false }
                        launchSingleTop = true
                    }
                },
            )
        }
        composable("service_mine") {
            MyRequestsScreen(
                repository = modules.services,
                onBack = { navController.popBackStack() },
                onOpenDetail = { id -> go("service_detail/$id") },
            )
        }
        composable(
            route = "service_detail/{requestId}",
            arguments = listOf(navArgument("requestId") { type = NavType.LongType }),
        ) { backStackEntry ->
            ServiceRequestDetailScreen(
                requestId = backStackEntry.arguments?.getLong("requestId") ?: 0L,
                repository = modules.services,
                onBack = { navController.popBackStack() },
            )
        }

        // ── 专注自习 ──
        composable(
            route = "focus?taskId={taskId}",
            arguments = listOf(navArgument("taskId") {
                type = NavType.StringType
                nullable = true
                defaultValue = null
            }),
        ) { backStackEntry ->
            val reduceMotion by repository.reduceMotion.collectAsState()
            FocusScreen(
                repository = modules.focus,
                appRepository = repository,
                reduceMotion = reduceMotion,
                onBack = { navController.popBackStack() },
                relatedTaskId = backStackEntry.arguments?.getString("taskId"),
                onOpenCounselorPlan = { prompt ->
                    val encoded = URLEncoder.encode(prompt, Charsets.UTF_8.name())
                    go("counselor?prompt=$encoded")
                },
            )
        }

        // ── 失物招领 ──
        composable("lostfound") {
            LostFoundScreen(
                repository = modules.lostFound,
                onBack = { navController.popBackStack() },
                onOpenDetail = { id -> go("lostfound_detail/$id") },
                onOpenPublish = { go("lostfound_publish") },
                onOpenMine = { go("lostfound_mine") },
            )
        }
        composable("lostfound_publish") {
            LostFoundPublishScreen(
                repository = modules.lostFound,
                appRepository = repository,
                onBack = { navController.popBackStack() },
                onPublished = { id ->
                    navController.navigate("lostfound_detail/$id") {
                        popUpTo("lostfound") { inclusive = false }
                        launchSingleTop = true
                    }
                },
            )
        }
        composable(
            route = "lostfound_detail/{itemId}",
            arguments = listOf(navArgument("itemId") { type = NavType.LongType }),
        ) { backStackEntry ->
            LostFoundDetailScreen(
                itemId = backStackEntry.arguments?.getLong("itemId") ?: 0L,
                repository = modules.lostFound,
                onBack = { navController.popBackStack() },
            )
        }
        composable("lostfound_mine") {
            MyLostFoundScreen(
                repository = modules.lostFound,
                onBack = { navController.popBackStack() },
                onOpenDetail = { id -> go("lostfound_detail/$id") },
            )
        }
    }
}

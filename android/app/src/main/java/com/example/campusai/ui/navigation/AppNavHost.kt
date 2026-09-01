package com.example.campusai.ui.navigation

import android.net.Uri
import androidx.compose.animation.*
import androidx.compose.animation.core.tween
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.statusBars
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.Dp
import androidx.navigation.NamedNavArgument
import androidx.navigation.NavBackStackEntry
import androidx.navigation.NavGraphBuilder
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable as navigationComposable
import androidx.navigation.navArgument
import com.example.campusai.ui.components.StickySecondaryNavigation
import androidx.activity.compose.LocalOnBackPressedDispatcherOwner
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
import com.example.campusai.ui.screens.focus.FocusSessionScreen
import com.example.campusai.ui.screens.focus.FocusHistoryScreen
import com.example.campusai.ui.screens.focus.FocusSummaryScreen

import com.example.campusai.ui.screens.lostfound.LostFoundDetailScreen
import com.example.campusai.ui.screens.lostfound.LostFoundPublishScreen
import com.example.campusai.ui.screens.lostfound.LostFoundScreen
import com.example.campusai.ui.screens.lostfound.MyLostFoundScreen
import com.example.campusai.ui.screens.notifications.CampusNewsDetailScreen
import com.example.campusai.ui.screens.notifications.CampusNewsScreen
import com.example.campusai.ui.screens.notifications.NotificationsScreen
import com.example.campusai.ui.screens.profile.AccountScreen
import com.example.campusai.ui.screens.profile.ExpressionContributionScreen
import com.example.campusai.ui.screens.profile.NotificationSettingsScreen
import com.example.campusai.ui.screens.profile.PersonalHubScreen
import com.example.campusai.ui.screens.profile.ProfileScreen
import com.example.campusai.ui.screens.profile.QrScannerScreen
import com.example.campusai.ui.screens.profile.QrConfirmScreen
import com.example.campusai.ui.screens.profile.QrScanResultHolder
import com.example.campusai.ui.screens.profile.SettingsScreen
import com.example.campusai.ui.screens.profile.HelpFeedbackScreen

import com.example.campusai.ui.screens.services.GenericServiceFormScreen
import com.example.campusai.ui.screens.services.LeaveRequestScreen
import com.example.campusai.ui.screens.services.MyRequestsScreen
import com.example.campusai.ui.screens.services.RepairRequestScreen
import com.example.campusai.ui.screens.services.ServiceRequestDetailScreen
import com.example.campusai.ui.screens.services.ServicesScreen
import com.example.campusai.ui.screens.tasks.TasksScreen
import com.example.campusai.ui.screens.tasks.TaskDetailScreen
import com.example.campusai.ui.screens.tasks.TaskCalendarScreen
import com.example.campusai.ui.screens.v3.AcademicScreen
import com.example.campusai.ui.screens.community.CommunityScreen
import com.example.campusai.ui.screens.community.CommunityDetailScreen
import com.example.campusai.ui.screens.community.CommunityPublishScreen
import com.example.campusai.ui.screens.community.CommunityHotTopicsScreen
import com.example.campusai.ui.screens.v3.UniversityScreen
import com.example.campusai.ui.screens.profile.UniversityPickerScreen
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.CampusMotion
import java.net.URLEncoder

internal fun eduFlowViewModelOwner(navController: NavHostController): NavBackStackEntry =
    navController.getBackStackEntry("edu_system")

@Composable
private fun NavigationDestinationFrame(
    backStackEntry: NavBackStackEntry,
    statusBarHeight: Dp,
    onBack: () -> Unit,
    content: @Composable () -> Unit,
) {
    val route = backStackEntry.destination.route
    val destination = secondaryDestinationSpec(route)
    val title = when (route?.substringBefore('?')) {
        "exam_edit/{examId}" -> {
            if (backStackEntry.arguments?.getLong("examId") == 0L) "新增考试" else "编辑考试"
        }
        "service_form/{kind}" -> when (backStackEntry.arguments?.getString("kind")) {
            "certificate" -> "证明申请"
            "venue" -> "场地申请"
            "feedback" -> "意见反馈"
            else -> destination?.title
        }
        else -> destination?.title
    }
    val layout = navigationDestinationLayout(route, statusBarHeight)

    Box(Modifier.fillMaxSize().background(Background)) {
        Box(
            Modifier
                .fillMaxSize()
                .padding(top = layout.contentTopPadding),
        ) {
            content()
        }
        destination?.let {
            StickySecondaryNavigation(
                title = title ?: it.title,
                onBack = onBack,
                modifier = Modifier.align(Alignment.TopStart),
            )
        }
    }
}

@Composable
fun AppNavHost(
    navController: NavHostController,
    repository: AppRepository,
    modules: ModuleRepositories,
    notificationInboxRepository: NotificationInboxRepository,
) {
    fun go(route: String) = navController.navigate(route) { launchSingleTop = true }
    fun switchPersonalSection(fromRoute: String, toRoute: String) {
        navController.navigate(toRoute) {
            launchSingleTop = true
            popUpTo(fromRoute) { inclusive = true }
        }
    }
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    val statusBarHeight = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    val backDispatcher = LocalOnBackPressedDispatcherOwner.current?.onBackPressedDispatcher

    fun NavGraphBuilder.composable(
        route: String,
        arguments: List<NamedNavArgument> = emptyList(),
        content: @Composable AnimatedContentScope.(NavBackStackEntry) -> Unit,
    ) {
        navigationComposable(route = route, arguments = arguments) { backStackEntry ->
            val transitionScope = this
            NavigationDestinationFrame(
                backStackEntry = backStackEntry,
                statusBarHeight = statusBarHeight,
                onBack = {
                    backDispatcher?.onBackPressed() ?: navController.popBackStack()
                },
            ) {
                content(transitionScope, backStackEntry)
            }
        }
    }

    NavHost(
                navController = navController,
                startDestination = "home",
                modifier = Modifier.fillMaxSize(),
        enterTransition = {
            if (reduceMotion) {
                EnterTransition.None
            } else {
                val motion = forwardNavigationMotion(
                    initialRoute = initialState.destination.route,
                    targetRoute = targetState.destination.route,
                )
                slideInHorizontally(
                    animationSpec = tween(CampusMotion.routeEnterDuration, easing = CampusMotion.routeEasing),
                    initialOffsetX = { width -> width * motion.enterDirection },
                ) + fadeIn(
                    animationSpec = tween(CampusMotion.routeEnterDuration, easing = CampusMotion.routeEasing),
                ) + scaleIn(
                    initialScale = .985f,
                    animationSpec = tween(CampusMotion.routeEnterDuration, easing = CampusMotion.routeEasing),
                )
            }
        },
        exitTransition = {
            if (reduceMotion) {
                ExitTransition.None
            } else {
                val motion = forwardNavigationMotion(
                    initialRoute = initialState.destination.route,
                    targetRoute = targetState.destination.route,
                )
                slideOutHorizontally(
                    animationSpec = tween(CampusMotion.routeExitDuration, easing = CampusMotion.routeEasing),
                    targetOffsetX = { width -> width * motion.exitDirection },
                ) + fadeOut(
                    animationSpec = tween(CampusMotion.routeExitDuration, easing = CampusMotion.routeEasing),
                ) + scaleOut(
                    targetScale = .985f,
                    animationSpec = tween(CampusMotion.routeExitDuration, easing = CampusMotion.routeEasing),
                )
            }
        },
        popEnterTransition = {
            if (reduceMotion) {
                EnterTransition.None
            } else {
                slideInHorizontally(
                    animationSpec = tween(CampusMotion.routeEnterDuration, easing = CampusMotion.routeEasing),
                    initialOffsetX = { -it },
                ) + fadeIn(
                    animationSpec = tween(CampusMotion.routeEnterDuration, easing = CampusMotion.routeEasing),
                ) + scaleIn(
                    initialScale = .985f,
                    animationSpec = tween(CampusMotion.routeEnterDuration, easing = CampusMotion.routeEasing),
                )
            }
        },
        popExitTransition = {
            if (reduceMotion) {
                ExitTransition.None
            } else {
                slideOutHorizontally(
                    animationSpec = tween(CampusMotion.routeExitDuration, easing = CampusMotion.routeEasing),
                    targetOffsetX = { it },
                ) + fadeOut(
                    animationSpec = tween(CampusMotion.routeExitDuration, easing = CampusMotion.routeEasing),
                ) + scaleOut(
                    targetScale = .985f,
                    animationSpec = tween(CampusMotion.routeExitDuration, easing = CampusMotion.routeEasing),
                )
            }
        },
            ) {
        composable("home") {
            DashboardScreen(
                repository = repository,
                examRepository = modules.exams,
                focusRepository = modules.focus,
            ) { route ->
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
            NotificationsScreen(
                repository = repository,
                inboxRepository = notificationInboxRepository,
                onNavigateToWechat = { navController.navigate("notification-settings") },
                onNavigateToChaoxing = { navController.navigate("chaoxing") },
            )
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
        composable("qr_scanner") {
            QrScannerScreen(
                onBack = { navController.popBackStack() },
                onScanned = { sid, token, bName, oName, dLabel ->
                    QrScanResultHolder.set(sid, token, bName, oName, dLabel)
                    go("qr_confirm")
                },
            )
        }
        composable("qr_confirm") {
            val holder = QrScanResultHolder
            QrConfirmScreen(
                sessionId = holder.sessionId ?: "",
                scanToken = holder.scanToken ?: "",
                browserName = holder.browserName,
                osName = holder.osName,
                deviceLabel = holder.deviceLabel,
                onBack = {
                    holder.clear()
                    navController.popBackStack()
                },
                onSuccess = {
                    holder.clear()
                    navController.popBackStack("profile", inclusive = false)
                },
            )
        }
        composable("university") {
            UniversityScreen(
                repository = repository,
                onNavigate = { route -> go(route) },
            )
        }
        composable(
            route = "community?sort={sort}&query={query}",
            arguments = listOf(
                navArgument("sort") { type = NavType.StringType; nullable = true; defaultValue = "time" },
                navArgument("query") { type = NavType.StringType; nullable = true; defaultValue = "" },
            ),
        ) { backStackEntry ->
            val sort = backStackEntry.arguments?.getString("sort") ?: "time"
            val query = backStackEntry.arguments?.getString("query") ?: ""
            CommunityScreen(
                repository = modules.community,
                onOpenDetail = { id -> go("community_detail/$id") },
                onOpenPublish = { go("community_publish") },
                onOpenHotTopics = { go("community_hot") },
                initialSort = sort,
                initialQuery = query,
            )
        }
        composable("community_hot") {
            CommunityHotTopicsScreen(
                repository = modules.community,
                onOpenDetail = { id -> go("community_detail/$id") },
            )
        }
        composable("community_publish") {
            CommunityPublishScreen(
                repository = modules.community,
                onBack = { navController.popBackStack() },
                onPublished = { id ->
                    navController.navigate("community_detail/$id") {
                        popUpTo("community") { inclusive = false }
                        launchSingleTop = true
                    }
                },
            )
        }
        composable(
            route = "community_detail/{postId}",
            arguments = listOf(navArgument("postId") { type = NavType.StringType }),
        ) { backStackEntry ->
            CommunityDetailScreen(
                postId = backStackEntry.arguments?.getString("postId") ?: "",
                repository = modules.community,
                onBack = { navController.popBackStack() },
            )
        }
        composable("academic") { AcademicScreen() }
        composable("edu_system") {
            val eduViewModel = androidx.lifecycle.viewmodel.compose.viewModel<com.example.campusai.ui.screens.profile.EduViewModel>(
                viewModelStoreOwner = eduFlowViewModelOwner(navController),
            )
            com.example.campusai.ui.screens.profile.EduSystemScreen(
                onBack = { navController.popBackStack() },
                onNavigateToLogin = { loginUrl, connectionId, allowedOrigins ->
                    val encodedUrl = URLEncoder.encode(loginUrl, "UTF-8")
                    val encodedOrigins = URLEncoder.encode(allowedOrigins.joinToString(","), "UTF-8")
                    navController.navigate("edu_login/$connectionId?loginUrl=$encodedUrl&allowedOrigins=$encodedOrigins")
                },
                onOpenSchedule = { go("edu_schedule") },
                viewModel = eduViewModel,
            )
        }
        composable("edu_schedule") {
            com.example.campusai.ui.screens.profile.EduScheduleScreen()
        }
        composable(
            route = "edu_login/{connectionId}?loginUrl={loginUrl}&allowedOrigins={allowedOrigins}",
            arguments = listOf(
                navArgument("connectionId") { type = NavType.StringType },
                navArgument("loginUrl") { type = NavType.StringType },
                navArgument("allowedOrigins") { type = NavType.StringType; defaultValue = "" },
            ),
        ) { backStackEntry ->
            val connectionId = backStackEntry.arguments?.getString("connectionId") ?: ""
            val loginUrl = backStackEntry.arguments?.getString("loginUrl") ?: ""
            val allowedOrigins = java.net.URLDecoder.decode(backStackEntry.arguments?.getString("allowedOrigins") ?: "", "UTF-8").split(",").filter { it.isNotBlank() }
            val eduViewModel = androidx.lifecycle.viewmodel.compose.viewModel<com.example.campusai.ui.screens.profile.EduViewModel>(
                viewModelStoreOwner = eduFlowViewModelOwner(navController),
            )
            com.example.campusai.ui.screens.profile.EduLoginScreen(
                loginUrl = java.net.URLDecoder.decode(loginUrl, "UTF-8"),
                connectionId = connectionId,
                viewModel = eduViewModel,
                backendAllowedOrigins = allowedOrigins,
                onBack = { navController.popBackStack() },
            )
        }
        composable("settings") {
            SettingsScreen(
                repository = repository,
                onOpenContribution = { navController.navigate("expression-contribution") },

            )
        }
        composable("help-feedback") {
            HelpFeedbackScreen(
                repository = repository,
                onSubmitFeedback = { go("service_form/feedback") },
            )
        }
        composable("notification-settings") {
            NotificationSettingsScreen(
                repository = repository,
            )
        }
        composable("chaoxing") {
            com.example.campusai.ui.screens.profile.ChaoxingScreen()
        }
        composable("expression-contribution") {
            ExpressionContributionScreen(repository) { navController.popBackStack() }
        }
        composable("account") {
            val accountEntry = remember { navController.getBackStackEntry("account") }
            val pickedId by accountEntry.savedStateHandle
                .getStateFlow<String?>("pickedUniversityId", null).collectAsStateWithLifecycle()
            val pickedName by accountEntry.savedStateHandle
                .getStateFlow<String?>("pickedUniversityName", null).collectAsStateWithLifecycle()
            AccountScreen(
                repository = repository,
                onBack = { navController.popBackStack() },
                onPickUniversity = { go("university_picker") },
                pickedUniversityId = pickedId,
                pickedUniversityName = pickedName,
                onConsumePicked = {
                    accountEntry.savedStateHandle.remove<String>("pickedUniversityId")
                    accountEntry.savedStateHandle.remove<String>("pickedUniversityName")
                },
            )
        }
        composable("university_picker") {
            UniversityPickerScreen(
                repository = repository,
                currentUniversityId = repository.session.value?.universityId.orEmpty(),
                onSelected = { id, name ->
                    navController.getBackStackEntry("account").savedStateHandle["pickedUniversityId"] = id
                    navController.getBackStackEntry("account").savedStateHandle["pickedUniversityName"] = name
                    navController.popBackStack()
                },
                onBack = { navController.popBackStack() },
            )
        }


        composable("files") {
            PersonalHubScreen(
                repository = repository,
                initialSection = "files",
                onBack = { navController.popBackStack() },
                onSectionNavigate = { route -> switchPersonalSection("files", route) },
                onNavigate = { route -> go(route) },
            )
        }
        composable("favorites") {
            PersonalHubScreen(
                repository = repository,
                initialSection = "favorites",
                onBack = { navController.popBackStack() },
                onSectionNavigate = { route -> switchPersonalSection("favorites", route) },
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
            val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
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
            val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
            ClassroomsScreen(
                repository = modules.classrooms,
                reduceMotion = reduceMotion,
                onBack = { navController.popBackStack() },
            )
        }

        // ── 办事大厅 ──
        composable("services") {
            val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
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

        // ── 专注大厅 / 专注空间 / 本次专注总结 ──
        composable(
            route = "focus?taskId={taskId}",
            arguments = listOf(navArgument("taskId") {
                type = NavType.StringType
                nullable = true
                defaultValue = null
            }),
        ) { backStackEntry ->
            val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
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
                onOpenAssistant = { durationSeconds, taskName, sessionMode, taskId ->
                    val encodedTaskName = URLEncoder.encode(taskName, Charsets.UTF_8.name())
                    go("focus_session?durationSeconds=$durationSeconds&taskName=$encodedTaskName&sessionMode=${sessionMode.name}&taskId=${Uri.encode(taskId.orEmpty())}")
                },
                onOpenHistory = { go("focus_history") },
                planRepository = modules.focusPlans,
            )
        }
        composable("focus_history") {
            FocusHistoryScreen(repository = modules.focus, onBack = { navController.popBackStack() })
        }
        composable(
            route = "focus_session?durationSeconds={durationSeconds}&taskName={taskName}&sessionMode={sessionMode}&taskId={taskId}",
            arguments = listOf(
                navArgument("durationSeconds") { type = NavType.IntType; defaultValue = 0 },
                navArgument("taskName") { type = NavType.StringType; defaultValue = "本次专注" },
                navArgument("sessionMode") { type = NavType.StringType; defaultValue = "QUIET" },
                navArgument("taskId") { type = NavType.StringType; nullable = true; defaultValue = null },
            ),
        ) { backStackEntry ->
            FocusSessionScreen(
                appRepository = repository,
                focusRepository = modules.focus,
                plannedDurationSeconds = backStackEntry.arguments?.getInt("durationSeconds") ?: 0,
                taskName = backStackEntry.arguments?.getString("taskName") ?: "本次专注",
                planTaskId = backStackEntry.arguments?.getString("taskId")?.takeIf { it.isNotBlank() },
                planRepository = modules.focusPlans,
                sessionMode = com.example.campusai.data.model.FocusSessionMode.entries.firstOrNull {
                    it.name == backStackEntry.arguments?.getString("sessionMode")
                } ?: com.example.campusai.data.model.FocusSessionMode.QUIET,
                onSessionCompleted = { completion ->
                    // Uri.encode keeps spaces as %20.  URLEncoder uses '+', which Navigation
                    // treats as literal text and previously produced strings such as "+4+次".
                    val task = Uri.encode(completion.taskName)
                    val summary = Uri.encode(completion.aiSummary)
                    val observation = Uri.encode(completion.observationSummary)
                    val nextStep = Uri.encode(completion.nextStepTitle.orEmpty())
                    go("focus_summary?actualSeconds=${completion.actualSeconds}&taskName=$task&conversationCount=${completion.conversationCount}&aiSummary=$summary&observationSummary=$observation&taskId=${Uri.encode(completion.planTaskId.orEmpty())}&nextStepTitle=$nextStep&planComplete=${completion.planComplete}")
                },
            )
        }
        composable(
            route = "focus_summary?actualSeconds={actualSeconds}&taskName={taskName}&conversationCount={conversationCount}&aiSummary={aiSummary}&observationSummary={observationSummary}&taskId={taskId}&nextStepTitle={nextStepTitle}&planComplete={planComplete}",
            arguments = listOf(
                navArgument("actualSeconds") { type = NavType.IntType; defaultValue = 0 },
                navArgument("taskName") { type = NavType.StringType; defaultValue = "本次专注" },
                navArgument("conversationCount") { type = NavType.IntType; defaultValue = 0 },
                navArgument("aiSummary") { type = NavType.StringType; defaultValue = "你完成了这段专注。" },
                navArgument("observationSummary") { type = NavType.StringType; defaultValue = "你的学习状态整体稳定。" },
                navArgument("taskId") { type = NavType.StringType; nullable = true; defaultValue = null },
                navArgument("nextStepTitle") { type = NavType.StringType; nullable = true; defaultValue = null },
                navArgument("planComplete") { type = NavType.BoolType; defaultValue = false },
            ),
        ) { backStackEntry ->
            val returnToFocusHome = {
                navController.navigate("focus") {
                    // Remove the original home entry too.  It may otherwise restore its
                    // rememberSaveable dialogue/countdown state from the just-finished visit.
                    popUpTo("focus") { inclusive = true }
                    launchSingleTop = true
                }
            }
            val startNextStep = {
                val taskId = backStackEntry.arguments?.getString("taskId")?.takeIf { it.isNotBlank() }
                val planComplete = backStackEntry.arguments?.getBoolean("planComplete") ?: false
                if (taskId != null && !planComplete) {
                    navController.navigate("focus?taskId=${Uri.encode(taskId)}")
                } else {
                    returnToFocusHome()
                }
            }
            FocusSummaryScreen(
                actualSeconds = backStackEntry.arguments?.getInt("actualSeconds") ?: 0,
                taskName = backStackEntry.arguments?.getString("taskName") ?: "本次专注",
                conversationCount = backStackEntry.arguments?.getInt("conversationCount") ?: 0,
                aiSummary = backStackEntry.arguments?.getString("aiSummary") ?: "你完成了这段专注。",
                observationSummary = backStackEntry.arguments?.getString("observationSummary") ?: "你的学习状态整体稳定。",
                nextStepTitle = backStackEntry.arguments?.getString("nextStepTitle")?.takeIf { it.isNotBlank() },
                planComplete = backStackEntry.arguments?.getBoolean("planComplete") ?: false,
                onReturnHome = returnToFocusHome,
                onStartNext = startNextStep,
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

package com.example.campusai.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.screens.counselor.CounselorScreen
import com.example.campusai.ui.screens.courses.CoursesScreen
import com.example.campusai.ui.screens.dashboard.DashboardScreen
import com.example.campusai.ui.screens.generic.GenericScreen
import com.example.campusai.ui.screens.notifications.NotificationsScreen
import com.example.campusai.ui.screens.profile.ProfileScreen
import com.example.campusai.ui.screens.profile.AccountScreen
import com.example.campusai.ui.screens.profile.SettingsScreen
import com.example.campusai.ui.screens.profile.PersonalHubScreen
import com.example.campusai.ui.screens.study.StudyScreen
import com.example.campusai.ui.screens.tasks.TasksScreen
import com.example.campusai.ui.screens.users.UsersScreen

@Composable
fun AppNavHost(
    navController: NavHostController,
    repository: AppRepository
) {
    NavHost(
        navController = navController,
        startDestination = "home"
    ) {
        composable("home") {
            DashboardScreen(repository) { route ->
                navController.navigate(route) {
                    popUpTo("home") { inclusive = false }
                    launchSingleTop = true
                }
            }
        }
        composable("tasks") { TasksScreen(repository) }
        composable("notifications") { NotificationsScreen(repository) }
        composable("counselor") { CounselorScreen(repository) }
        composable("study") { StudyScreen(repository) }
        composable("courses") { CoursesScreen(repository) }
        composable("profile") {
            ProfileScreen(repository) { route -> navController.navigate(route) { launchSingleTop = true } }
        }
        composable("settings") { SettingsScreen(repository) { navController.popBackStack() } }
        composable("account") { AccountScreen(repository) { navController.popBackStack() } }
        composable("files") {
            PersonalHubScreen(
                repository = repository,
                initialSection = "files",
                onBack = { navController.popBackStack() },
                onNavigate = { route -> navController.navigate(route) { launchSingleTop = true } },
            )
        }
        composable("activities") {
            PersonalHubScreen(
                repository = repository,
                initialSection = "activities",
                onBack = { navController.popBackStack() },
                onNavigate = { route -> navController.navigate(route) { launchSingleTop = true } },
            )
        }
        composable("favorites") {
            PersonalHubScreen(
                repository = repository,
                initialSection = "favorites",
                onBack = { navController.popBackStack() },
                onNavigate = { route -> navController.navigate(route) { launchSingleTop = true } },
            )
        }
        composable("users") { UsersScreen(repository) }
        composable("publish") { GenericScreen(repository, "publish") }
        composable("stats") { GenericScreen(repository, "stats") }
        composable("system") { GenericScreen(repository, "system") }
    }
}

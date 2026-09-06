package com.example.campusai.ui.screens.dashboard

import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

data class DashboardFeatureCardSpec(
    val title: String,
    val subtitle: String,
    val route: String,
    val accentHex: String,
)

data class DashboardUtilityActionSpec(
    val label: String,
    val route: String,
)

fun dashboardFeatureCards(): List<DashboardFeatureCardSpec> = listOf(
    DashboardFeatureCardSpec("校园社区", "交流分享 · 连接同好", "community", "#FFA43A"),
    DashboardFeatureCardSpec("专注自习", "沉浸专注 · 效率提升", "focus", "#5B68F2"),
)

fun dashboardUtilityActions(): List<DashboardUtilityActionSpec> = listOf(
    DashboardUtilityActionSpec("通知", "notifications"),
    DashboardUtilityActionSpec("扫一扫", "qr_scanner"),
)

fun defaultOverviewMetricIds(): List<String> = listOf("courses", "tasks", "focus", "notifications")

fun dashboardCourseSectionRoute(): String = "courses"

fun dashboardUnreadNotificationRoute(): String = "tasks"

fun normalizeOverviewMetricIds(selected: List<String>, available: List<String>): List<String> {
    val valid = selected.filter { it in available }.distinct()
    return if (valid.isEmpty()) available.take(1) else valid
}

fun dashboardFocusDurationValue(todayMinutes: Int): String =
    "${todayMinutes.coerceAtLeast(0)} 分钟"

fun dashboardHeaderContentTopPadding(statusBarHeight: Dp): Dp =
    statusBarHeight.coerceAtLeast(0.dp) + 14.dp

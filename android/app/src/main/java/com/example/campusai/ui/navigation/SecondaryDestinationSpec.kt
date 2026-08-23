package com.example.campusai.ui.navigation

import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.example.campusai.ui.components.StickySecondaryNavigationContentHeight
import com.example.campusai.ui.system.routeOwnsStatusBarInset

internal data class SecondaryDestinationSpec(val title: String)

/**
 * Keeps the NavHost's bounds fixed while each destination reserves the space
 * required by its own system and secondary-navigation chrome.
 */
internal data class NavigationDestinationLayout(
    val navHostTopPadding: Dp = 0.dp,
    val contentTopPadding: Dp,
)

internal fun navigationDestinationLayout(
    route: String?,
    statusBarHeight: Dp,
): NavigationDestinationLayout {
    val normalizedRoute = route?.substringBefore('?')?.substringBefore('/')
    val contentTopPadding = when {
        secondaryDestinationSpec(route) != null ->
            statusBarHeight + StickySecondaryNavigationContentHeight
        routeOwnsStatusBarInset(route) || normalizedRoute in profileFlowRoutes -> 0.dp
        else -> statusBarHeight
    }
    return NavigationDestinationLayout(contentTopPadding = contentTopPadding)
}

internal fun secondaryDestinationSpec(route: String?): SecondaryDestinationSpec? {
    val normalizedRoute = route?.substringBefore('?') ?: return null
    if (normalizedRoute in rootRoutes) return null

    val title = staticDestinationTitles[normalizedRoute] ?: dynamicDestinationTitle(normalizedRoute)
    return title?.let(::SecondaryDestinationSpec)
}

private fun dynamicDestinationTitle(route: String): String? = when {
    route.startsWith("task_detail/") -> "待办详情"
    route.startsWith("campus-news-detail/") -> "通知详情"
    route.startsWith("exam_detail/") -> "考试详情"
    route.startsWith("exam_edit/") -> "编辑考试"
    route.startsWith("service_form/") -> "意见反馈"
    route.startsWith("edu_login/") -> "教务系统登录"
    route.startsWith("lostfound_detail/") -> "失物招领详情"
    route.startsWith("community_detail/") -> "帖子详情"
    else -> null
}


private val rootRoutes = setOf(
    "home",
    "courses",
    "tasks",
    "profile",
    "counselor",
)

private val profileFlowRoutes = setOf(
    "profile",
    "settings",
    "account",
    "files",
    "favorites",
    "help-feedback",
    "university",
    "academic",
)

private val staticDestinationTitles = mapOf(
    "notifications" to "通知与提醒",
    "task_calendar" to "待办日历",
    "settings" to "系统设置",
    "help-feedback" to "帮助与反馈",
    "notification-settings" to "微信通知监听",
    "chaoxing" to "学习通同步",
    "chaoxing-login" to "连接学习通",
    "expression-contribution" to "模型共建",
    "account" to "账号设置",
    "files" to "我的文件",
    "activities" to "我的活动",
    "favorites" to "我的收藏",
    "university" to "我的大学",
    "community" to "校园论坛",
    "community_hot" to "热门话题",
    "community_publish" to "发布帖子",
    "academic" to "教务系统",
    "edu_system" to "教务系统",
    "edu_schedule" to "教务课表",
    "exams" to "考试安排",
    "classrooms" to "空教室",
    "focus" to "专注自习",
    "lostfound_publish" to "发布失物招领",
    "lostfound_mine" to "我的发布",
)

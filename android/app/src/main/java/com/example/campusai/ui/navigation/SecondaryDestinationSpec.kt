package com.example.campusai.ui.navigation

internal data class SecondaryDestinationSpec(val title: String)

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
    route.startsWith("service_form/") -> "办理事项"
    route.startsWith("service_detail/") -> "申请详情"
    route.startsWith("lostfound_detail/") -> "失物招领详情"
    else -> null
}


private val rootRoutes = setOf(
    "home",
    "courses",
    "tasks",
    "profile",
    "counselor",
)

private val staticDestinationTitles = mapOf(
    "notifications" to "通知与提醒",
    "task_calendar" to "待办日历",
    "settings" to "系统设置",
    "notification-settings" to "微信通知监听",
    "chaoxing" to "学习通同步",
    "chaoxing-login" to "连接学习通",
    "expression-contribution" to "模型共建",
    "account" to "账号设置",
    "files" to "我的文件",
    "activities" to "我的活动",
    "favorites" to "我的收藏",
    "exams" to "考试安排",
    "classrooms" to "空教室",
    "services" to "办事大厅",
    "service_leave" to "请假申请",
    "service_repair" to "报修申请",
    "service_mine" to "我的申请",
    "focus" to "专注自习",
    "lostfound" to "失物招领",
    "lostfound_publish" to "发布失物招领",
    "lostfound_mine" to "我的发布",
)

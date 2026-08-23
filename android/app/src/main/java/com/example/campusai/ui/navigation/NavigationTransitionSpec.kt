package com.example.campusai.ui.navigation

internal data class HorizontalNavigationMotion(
    val enterDirection: Int,
    val exitDirection: Int,
)

internal fun forwardNavigationMotion(
    initialRoute: String?,
    targetRoute: String?,
): HorizontalNavigationMotion {
    val initialTab = mainTabIndex(initialRoute)
    val targetTab = mainTabIndex(targetRoute)
    val enterDirection = if (initialTab >= 0 && targetTab >= 0 && initialTab != targetTab) {
        if (targetTab > initialTab) 1 else -1
    } else {
        1
    }
    return HorizontalNavigationMotion(
        enterDirection = enterDirection,
        exitDirection = -enterDirection,
    )
}

private fun mainTabIndex(route: String?): Int = mainTabRoutes.indexOf(
    route?.substringBefore('?')?.substringBefore('/'),
)

private val mainTabRoutes = listOf("home", "courses", "tasks", "counselor", "profile")

package com.example.campusai.ui.system

data class SystemBarPolicy(
    val darkStatusBarIcons: Boolean,
    val darkNavigationBarIcons: Boolean,
)

private val lightThemeRoutesWithDarkStatusHeader = setOf(
    "profile",
)

private val routesWithAlwaysLightStatusSurface = emptySet<String>()

private val routesOwningStatusBarInset = setOf(
    "home",
    "profile",
    "focus_session",
)

fun systemBarPolicy(
    route: String?,
    darkTheme: Boolean,
    authenticated: Boolean,
): SystemBarPolicy {
    val baseRoute = route?.substringBefore('?')?.substringBefore('/')
    val statusSurfaceIsLight = !darkTheme || baseRoute in routesWithAlwaysLightStatusSurface
    val useDarkStatusIcons = authenticated &&
        statusSurfaceIsLight &&
        baseRoute !in lightThemeRoutesWithDarkStatusHeader
    val useDarkNavigationIcons = authenticated && !darkTheme
    return SystemBarPolicy(
        darkStatusBarIcons = useDarkStatusIcons,
        darkNavigationBarIcons = useDarkNavigationIcons,
    )
}

fun routeOwnsStatusBarInset(route: String?): Boolean {
    val baseRoute = route?.substringBefore('?')?.substringBefore('/')
    return baseRoute in routesOwningStatusBarInset
}

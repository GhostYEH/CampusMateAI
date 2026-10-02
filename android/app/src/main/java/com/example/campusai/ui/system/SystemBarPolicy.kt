package com.example.campusai.ui.system

data class SystemBarPolicy(
    val darkStatusBarIcons: Boolean,
    val darkNavigationBarIcons: Boolean,
)

private val routesWithDarkFullBleedScene = setOf(
    "home",
    "courses",
    "focus",
    "focus_session",
    "focus_summary",
    "focus_history",
)

private val lightThemeRoutesWithDarkStatusHeader = routesWithDarkFullBleedScene + "profile"

private val routesWithAlwaysLightStatusSurface = emptySet<String>()

private val routesOwningStatusBarInset = setOf(
    "home",
    "courses",
    "profile",
    "focus",
    "focus_summary",
    "focus_history",
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
    val useDarkNavigationIcons = authenticated && !darkTheme && baseRoute !in routesWithDarkFullBleedScene
    return SystemBarPolicy(
        darkStatusBarIcons = useDarkStatusIcons,
        darkNavigationBarIcons = useDarkNavigationIcons,
    )
}

fun routeOwnsStatusBarInset(route: String?): Boolean {
    val baseRoute = route?.substringBefore('?')?.substringBefore('/')
    return baseRoute in routesOwningStatusBarInset
}

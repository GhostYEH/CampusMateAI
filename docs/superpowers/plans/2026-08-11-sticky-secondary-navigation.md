# Sticky Secondary Navigation Implementation Plan

For agentic workers: use the superpowers:subagent-driven-development or superpowers:executing-plans skill to implement task by task.

Goal: Keep a consistent translucent circular back control and title visible on secondary Android destinations while their content scrolls.

Architecture: A pure route-specification object classifies root and secondary destinations and supplies fixed-bar titles. AppNavHost draws one shared Compose chrome outside scrolling destination content. Screens that currently own top bars or in-list back buttons are adjusted only to avoid duplication and reserve clear top space.

Tech Stack: Kotlin, Jetpack Compose Material 3, Navigation Compose, JUnit 4.

## Global Constraints

- Preserve existing uncommitted notification and Learning Tong changes.
- Do not rename navigation routes or change destination callbacks.
- Use existing design tokens and no new dependency.
- Back control is a 44 dp circular target with the content description 返回.
- Root destinations do not display secondary chrome.

---

### Task 1: Define secondary-route presentation rules

Files:
- Create: android/app/src/main/java/com/example/campusai/ui/navigation/SecondaryDestinationSpec.kt
- Create: android/app/src/test/java/com/example/campusai/ui/navigation/SecondaryDestinationSpecTest.kt

Interfaces:
- Produces: internal data class SecondaryDestinationSpec(val title: String).
- Produces: internal fun secondaryDestinationSpec(route: String?): SecondaryDestinationSpec?.

- [ ] Step 1: Write the failing test

@Test
fun secondary_route_receives_title() {
    assertEquals("系统设置", secondaryDestinationSpec("settings")?.title)
}

@Test
fun root_route_omits_secondary_chrome() {
    assertNull(secondaryDestinationSpec("home"))
}

@Test
fun argument_route_resolves_title() {
    assertEquals("通知详情", secondaryDestinationSpec("campus_news_detail/news-42")?.title)
}

- [ ] Step 2: Run the test to verify it fails

Run: ./gradlew :app:testDebugUnitTest --tests com.example.campusai.ui.navigation.SecondaryDestinationSpecTest

Expected: compilation failure because secondaryDestinationSpec does not exist.

- [ ] Step 3: Add minimal route specification

internal data class SecondaryDestinationSpec(val title: String)

internal fun secondaryDestinationSpec(route: String?): SecondaryDestinationSpec? = when {
    route == null || route in rootRoutes -> null
    route.startsWith("campus_news_detail/") -> SecondaryDestinationSpec("通知详情")
    route == "settings" -> SecondaryDestinationSpec("系统设置")
    else -> secondaryTitles[route]
}

Populate route titles for every non-root route registered by AppNavHost, including argument routes.

- [ ] Step 4: Run the focused test to verify it passes

Run: ./gradlew :app:testDebugUnitTest --tests com.example.campusai.ui.navigation.SecondaryDestinationSpecTest

Expected: PASS.

- [ ] Step 5: Commit

git add android/app/src/main/java/com/example/campusai/ui/navigation/SecondaryDestinationSpec.kt android/app/src/test/java/com/example/campusai/ui/navigation/SecondaryDestinationSpecTest.kt
git commit -m "feat: classify secondary navigation destinations"

### Task 2: Build shared frosted secondary-navigation chrome

Files:
- Modify: android/app/src/main/java/com/example/campusai/ui/components/CampusKit.kt
- Modify: android/app/src/main/java/com/example/campusai/ui/navigation/SecondaryDestinationSpec.kt
- Test: android/app/src/test/java/com/example/campusai/ui/navigation/SecondaryDestinationSpecTest.kt

Interfaces:
- Produces: @Composable fun StickySecondaryNavigation(title: String, onBack: () -> Unit, modifier: Modifier = Modifier).

- [ ] Step 1: Extend the failing test

@Test
fun declared_secondary_routes_have_nonblank_titles() {
    listOf("settings", "notification-settings", "service_leave").forEach { route ->
        assertFalse(secondaryDestinationSpec(route)?.title.isNullOrBlank())
    }
}

- [ ] Step 2: Run the focused test to verify it fails

Run: ./gradlew :app:testDebugUnitTest --tests com.example.campusai.ui.navigation.SecondaryDestinationSpecTest

Expected: FAIL until every listed route has a title.

- [ ] Step 3: Implement the composable

@Composable
fun StickySecondaryNavigation(title: String, onBack: () -> Unit, modifier: Modifier = Modifier) {
    Row(modifier.statusBarsPadding().padding(horizontal = 16.dp, vertical = 10.dp)) {
        Box(
            Modifier.size(44.dp)
                .clip(CircleShape)
                .background(Surface.copy(alpha = .78f))
                .border(1.dp, Color.White.copy(alpha = .42f), CircleShape)
                .campusClickable(role = Role.Button, onClick = onBack),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回", tint = TextPrimary)
        }
        Text(title, modifier = Modifier.align(Alignment.CenterVertically).padding(start = 12.dp))
    }
}

Use an existing-token shadow and dark-theme contrast fallback, with no animation or dependency.

- [ ] Step 4: Run the focused test to verify it passes

Run: ./gradlew :app:testDebugUnitTest --tests com.example.campusai.ui.navigation.SecondaryDestinationSpecTest

Expected: PASS.

- [ ] Step 5: Commit

git add android/app/src/main/java/com/example/campusai/ui/components/CampusKit.kt android/app/src/main/java/com/example/campusai/ui/navigation/SecondaryDestinationSpec.kt android/app/src/test/java/com/example/campusai/ui/navigation/SecondaryDestinationSpecTest.kt
git commit -m "feat: add sticky secondary navigation chrome"

### Task 3: Apply chrome centrally and remove duplicates

Files:
- Modify: android/app/src/main/java/com/example/campusai/ui/navigation/AppNavHost.kt
- Modify: android/app/src/main/java/com/example/campusai/ui/screens/profile/SettingsScreen.kt
- Modify: android/app/src/main/java/com/example/campusai/ui/screens/profile/AccountScreen.kt
- Modify: android/app/src/main/java/com/example/campusai/ui/screens/profile/ChaoxingLoginScreen.kt
- Modify: android/app/src/main/java/com/example/campusai/ui/screens/profile/ChaoxingScreen.kt
- Modify: android/app/src/main/java/com/example/campusai/ui/screens/profile/NotificationSettingsScreen.kt
- Modify: android/app/src/main/java/com/example/campusai/ui/screens/notifications/CampusNewsDetailScreen.kt

Interfaces:
- Consumes: secondaryDestinationSpec(currentRoute) and navController.popBackStack().
- Produces: one fixed back affordance above each secondary route scroll container.

- [ ] Step 1: Add a failing route-family test

@Test
fun all_secondary_route_families_resolve_a_title() {
    listOf(
        "settings", "account", "notification-settings", "chaoxing", "chaoxing-login",
        "campus_news_detail/id", "task_detail/1", "exam_detail/1", "service_detail/1",
        "lostfound_detail/1", "classroom_detail/1", "counselor", "focus"
    ).forEach { route -> assertFalse(secondaryDestinationSpec(route)?.title.isNullOrBlank()) }
}

- [ ] Step 2: Run the focused test to verify it fails

Run: ./gradlew :app:testDebugUnitTest --tests com.example.campusai.ui.navigation.SecondaryDestinationSpecTest

Expected: FAIL for at least one unlisted route family.

- [ ] Step 3: Render chrome from the navigation host

val currentRoute = navController.currentBackStackEntryAsState().value?.destination?.route
val secondary = secondaryDestinationSpec(currentRoute)
Box(Modifier.fillMaxSize()) {
    NavHost(/* existing destinations unchanged */)
    if (secondary != null) {
        StickySecondaryNavigation(
            title = secondary.title,
            onBack = { navController.popBackStack() },
            modifier = Modifier.align(Alignment.TopStart),
        )
    }
}

Use the route template from Navigation Compose and route-pattern support in the specification.

- [ ] Step 4: Remove only duplicate local back controls and reserve top space

Remove local TopAppBar navigation icons or embedded-header back controls only after host chrome is present. Preserve titles, content order, form logic, user changes, and bottom-dock padding. Give each listed scroll container enough top padding to remain clear of the fixed chrome.

- [ ] Step 5: Run the focused test to verify it passes

Run: ./gradlew :app:testDebugUnitTest --tests com.example.campusai.ui.navigation.SecondaryDestinationSpecTest

Expected: PASS with every secondary route family classified.

- [ ] Step 6: Commit

git add android/app/src/main/java/com/example/campusai/ui/navigation/AppNavHost.kt android/app/src/main/java/com/example/campusai/ui/screens/profile android/app/src/main/java/com/example/campusai/ui/screens/notifications/CampusNewsDetailScreen.kt android/app/src/main/java/com/example/campusai/ui/components/CampusKit.kt android/app/src/main/java/com/example/campusai/ui/navigation/SecondaryDestinationSpec.kt android/app/src/test/java/com/example/campusai/ui/navigation/SecondaryDestinationSpecTest.kt
git commit -m "feat: keep secondary navigation visible while scrolling"

### Task 4: Verify build and representative screens

Files: verify only the files changed in Tasks 1-3.

- [ ] Step 1: Run all Android unit tests

Run: ./gradlew :app:testDebugUnitTest

Expected: PASS with zero failures.

- [ ] Step 2: Assemble the Android debug app

Run: ./gradlew :app:assembleDebug

Expected: BUILD SUCCESSFUL.

- [ ] Step 3: Manually check representative screens

Check Settings, Campus News detail, and Learning Tong login. On each, the 返回 control stays below the status bar, remains tappable, and does not obscure the first interactive element. On a root tab, it is absent.


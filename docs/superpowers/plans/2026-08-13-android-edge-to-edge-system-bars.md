# Android Edge-to-Edge System Bars Implementation Plan

> **For agentic workers:** Execute inline in the existing user workspace. Do not create a worktree or Git commit because the user explicitly requested direct work in the current dirty project and prohibited commits.

**Goal:** Make every Android screen draw naturally behind transparent system bars, choose readable black or white system-bar icons from the active page/theme, and soften shared back buttons.

**Architecture:** Keep edge-to-edge window ownership in `MainActivity`, add a small route/theme policy in the Android UI layer, and apply it from `AppShell`. Existing screens retain responsibility for padding their actual controls with `statusBarsPadding()` or `navigationBarsPadding()`; only full-bleed hero routes opt out of the shell's top inset. Shared back-button visuals are adjusted centrally, with the custom lost-and-found back button matched locally.

**Tech Stack:** Kotlin, Jetpack Compose, AndroidX Activity/Core, Navigation Compose, JUnit.

## Global Constraints

- Modify Android only.
- Preserve all business logic, repositories, APIs, navigation destinations, and screen behavior.
- Do not upgrade Gradle, AGP, Kotlin, or Compose.
- Build with JDK 17.
- Do not commit or overwrite unrelated user changes.

### Task 1: Test and implement system-bar policy

**Files:**
- Create: `android/app/src/main/java/com/example/campusai/ui/system/SystemBarPolicy.kt`
- Create: `android/app/src/test/java/com/example/campusai/ui/system/SystemBarPolicyTest.kt`

- [ ] Add failing tests for dark theme, default light routes, and full-bleed routes.
- [ ] Run the focused test and confirm it fails because the policy does not exist.
- [ ] Implement the smallest pure Kotlin route/theme policy.
- [ ] Run the focused test and confirm it passes.

### Task 2: Apply transparent bars and page-safe insets

**Files:**
- Modify: `android/app/src/main/java/com/example/campusai/MainActivity.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/shell/AppShell.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/lostfound/LostFoundScreen.kt`
- Modify: `android/app/src/main/res/values/themes.xml`

- [ ] Make both system bars transparent and disable platform contrast scrims where supported.
- [ ] Apply icon appearance from dark theme plus current route policy.
- [ ] Let full-bleed routes paint behind the status bar while padding only their controls.
- [ ] Preserve bottom content protection through the existing dock and navigation-bar insets.

### Task 3: Soften back buttons and verify representative screens

**Files:**
- Modify: `android/app/src/main/java/com/example/campusai/ui/components/CampusKit.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/lostfound/LostFoundScreen.kt`

- [ ] Reduce shared and lost-and-found back-button surface opacity while retaining contrast and tap targets.
- [ ] Run unit tests, `:app:compileDebugKotlin`, and `:app:assembleDebug` with JDK 17.
- [ ] Install the APK and capture at least a light root screen, a full-bleed hero screen, and a secondary screen.
- [ ] Confirm readable system icons, no duplicate top inset, no clipped top controls, and no bottom content hidden by the gesture area.

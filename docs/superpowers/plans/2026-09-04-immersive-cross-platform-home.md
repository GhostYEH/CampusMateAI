# 沉浸式跨端首页与失物招领客户端下线 Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with verification after each increment.

**Goal:** 在 Android 与 HarmonyOS 上实现固定的沉浸式校园首页，并安全下线失物招领客户端而不影响校园社区。

**Architecture:** 两端分别保留各自的 Compose/ArkUI 页面实现，共享相同的信息层级、路由语义和素材选择。首页只移除客户端 Banner 消费；失物招领只移除客户端产品层，后端与社区 `lostfound` 分类保持不变。

**Tech Stack:** Kotlin, Jetpack Compose, ArkTS/ArkUI, existing repositories and resources.

**Spec:** `docs/superpowers/specs/2026-09-04-immersive-cross-platform-home-design.md`

## Global Constraints

- 不修改 Android `CampusDock` 或 Harmony `AppDock` 的项目、样式、手势和选中策略。
- 不修改后端接口、数据库结构、历史数据或校园社区的 `lostfound` 分类。
- JVM 命令必须使用 `android/.tools/jdk21-full/jdk-21.0.12+8`。
- 保留并尊重 `reduceMotion` 与现有底部悬浮导航安全间距。
- 不覆盖工作区已有未提交改动。

---

### Task 1: Add behavior contracts before UI edits

**Files:**
- Create: `android/app/src/test/java/com/example/campusai/ui/screens/dashboard/ImmersiveDashboardSpecTest.kt`
- Create: `android/app/src/main/java/com/example/campusai/ui/screens/dashboard/ImmersiveDashboardSpec.kt`
- Test: `android/app/src/test/java/com/example/campusai/ui/screens/dashboard/ImmersiveDashboardSpecTest.kt`

**Interfaces:**
- Produces `dashboardFeatureCards()` and `dashboardUtilityActions()` as pure, testable route contracts for the new fixed homepage.

- [ ] Write tests asserting the orange community card, blue focus card, notification route and scan route exist, and `lostfound` is absent from homepage actions.
- [ ] Run the focused test and confirm it fails because the new contract is not yet implemented.
- [ ] Implement the smallest immutable contract data and functions.
- [ ] Re-run the focused test and confirm it passes.

### Task 2: Android fixed immersive homepage

**Files:**
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/dashboard/DashboardScreen.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/dashboard/ClassicDashboardScreen.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/dashboard/gamified/GamifiedDashboardScreen.kt` or route selection as needed
- Modify: `android/app/src/main/java/com/example/campusai/ui/system/SystemBarPolicy.kt` only if required by the existing immersive inset contract
- Reuse: `android/app/src/main/res/drawable-nodpi/campus_login_poster.png`, `cpm_avatar_fallback.png`

**Interfaces:**
- Consumes `AppRepository` course/task/news/session flows and existing navigation callback.
- Produces a fixed homepage with `notifications`, `qr_scanner`, `counselor`, `community`, and `focus` actions.

- [ ] Add the failing/contract coverage for fixed card routes from Task 1.
- [ ] Replace the classic top Banner carousel and five quick actions with the immersive header, CPM assistant card, two feature cards, information overview and today-course sections.
- [ ] Make the dashboard route render the new fixed page consistently, without changing the five bottom navigation items.
- [ ] Remove the dashboard-side `homeBanners` collection/request and dead Banner rendering imports only where no other Android consumer remains.
- [ ] Run focused dashboard tests and Android unit tests.

### Task 3: Android client-side lost-and-found removal

**Files:**
- Modify: `android/app/src/main/java/com/example/campusai/ui/navigation/AppNavHost.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/navigation/SecondaryDestinationSpec.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/system/SystemBarPolicy.kt`
- Modify: `android/app/src/main/java/com/example/campusai/data/repository/ModuleRepositories.kt`
- Delete: `android/app/src/main/java/com/example/campusai/ui/screens/lostfound/`
- Delete: `android/app/src/main/java/com/example/campusai/data/repository/LostFoundRepository.kt`
- Delete: `android/app/src/main/java/com/example/campusai/data/model/LostFoundItem.kt`
- Modify: Android client tests/resources only after `rg` confirms they are exclusively client lost-found assets

**Interfaces:**
- Removes only client routes and local module dependencies.
- Leaves `CommunityScreen.kt` and `CommunityPublishScreen.kt` category handling unchanged.

- [ ] Remove lost-found imports and navigation branches.
- [ ] Remove the standalone Android repository/model and exclusive assets after reference checks.
- [ ] Keep all community `lostfound` category strings and community post flows intact.
- [ ] Run `rg` assertions and Android compile/tests.

### Task 4: HarmonyOS fixed immersive homepage

**Files:**
- Modify: `harmony/entry/src/main/ets/features/dashboard/DashboardPage.ets`
- Modify: `harmony/entry/src/main/ets/pages/Index.ets` only for existing status-bar/page routing integration
- Reuse: `harmony/entry/src/main/resources/base/media/campus_login_poster.png`, `cpm_avatar.png`

**Interfaces:**
- Consumes existing `courses`, `tasks`, `notices`, `hotPosts`, `userName` and navigation callback.
- Produces the same fixed homepage route contract as Android.

- [ ] Replace `HomeBanner`/`QuickActions` dashboard composition with the fixed immersive header and cards.
- [ ] Add notification/scan controls and CPM avatar card without changing `AppDock`.
- [ ] Preserve reduce-motion and bottom dock spacing.
- [ ] Run Harmony tests after the page compiles.

### Task 5: HarmonyOS client-side lost-and-found removal

**Files:**
- Modify: `harmony/entry/src/main/ets/navigation/AppRoute.ets`
- Modify: `harmony/entry/src/main/ets/pages/Index.ets`
- Modify: `harmony/entry/src/main/ets/data/Models.ets`
- Delete: `harmony/entry/src/main/ets/features/lostfound/LostFoundPage.ets`
- Delete: `harmony/entry/src/main/ets/features/lostfound/LostFoundFeed.ets`
- Modify/delete: exclusive Harmony lost-found tests after reference checks

**Interfaces:**
- Removes standalone Harmony lost-found routes, state, fetch and publish methods.
- Leaves community routes, models and category handling unchanged.

- [ ] Remove route definitions/titles/parent mappings and page import/branch.
- [ ] Remove only lost-found state and API calls from `Index.ets`.
- [ ] Keep community `lostfound` category handling in place.
- [ ] Run Harmony static references and tests.

### Task 6: Cross-platform verification and hygiene

**Files:**
- Verify: all modified Android/Harmony files and `docs/superpowers/*`

- [ ] Run Android tests/build with the bundled JDK 21.
- [ ] Run Harmony tests/build with the configured DevEco toolchain.
- [ ] Verify `community` references remain and `lostfound` references are limited to backend/community compatibility code.
- [ ] Inspect `git diff`, `git diff --cached`, and `git status`; do not stage or alter unrelated pre-existing changes.
- [ ] Commit only the implementation/doc files belonging to this task in atomic commits if the worktree allows it.

# CampusMate AI HarmonyOS NEXT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the HarmonyOS NEXT CampusMate AI client in `harmony/` with Android-equivalent UI, navigation, server integration, and safe platform adaptations.

**Architecture:** A Stage-model ArkTS app stores session and UI preferences in a small app-state service. Feature repositories call a typed `ApiClient`; page components use the same shared visual tokens, surfaces, form controls, route host, and floating tab shell. Device-specific functionality stays behind capability services so every route works when a permission or device feature is unavailable.

**Tech Stack:** HarmonyOS NEXT API 6.1.1, ArkTS, ArkUI, `@ohos.net.http`, `@ohos.data.preferences`, Hypium, Hvigor.

## Global Constraints

- Create or modify only `harmony/` and this migration documentation path.
- Android files are read-only reference material.
- Preserve Android's Chinese copy, warm light/dark theme, route behavior, assets, transition policy, and reduced-motion preference.
- API base URL is configurable and never hard-codes Android emulator host `10.0.2.2`.
- Android notification listener behavior is represented by server-backed/in-app notices, not an unsupported third-party notification listener.

---

### Task 1: Create a buildable HarmonyOS project and app state

**Files:**
- Create: `harmony/build-profile.json5`, `harmony/oh-package.json5`, `harmony/AppScope/app.json5`
- Create: `harmony/entry/build-profile.json5`, `harmony/entry/oh-package.json5`, `harmony/entry/src/main/module.json5`
- Create: `harmony/entry/src/main/ets/entryability/EntryAbility.ets`, `harmony/entry/src/main/ets/pages/Index.ets`
- Create: `harmony/entry/src/main/ets/core/AppState.ets`
- Test: `harmony/entry/src/test/ets/core/AppState.test.ets`

**Interfaces:**
- Produces `AppState.restore()`, `AppState.signIn(token: string)`, `AppState.signOut()`, `AppState.toggleTheme()`, and `AppState.setReduceMotion(value: boolean)`.

- [ ] Write the failing unit tests for session restoration, sign-in/sign-out, and preference mutations.
- [ ] Run the unit test target and confirm it fails because `AppState` is missing.
- [ ] Create the Stage project files and implement `AppState` with HarmonyOS preferences-backed storage.
- [ ] Re-run the unit test target and confirm it passes.
- [ ] Build the entry module with Hvigor and confirm an installable HAP is produced.

### Task 2: Build the reusable visual system and shell

**Files:**
- Create: `harmony/entry/src/main/ets/ui/Theme.ets`, `harmony/entry/src/main/ets/ui/Components.ets`, `harmony/entry/src/main/ets/ui/AppShell.ets`
- Create: `harmony/entry/src/main/resources/base/media/` assets copied from Android without source changes
- Test: `harmony/entry/src/test/ets/ui/Theme.test.ets`

**Interfaces:**
- Consumes `AppState.darkMode` and `AppState.reduceMotion`.
- Produces `CampusTheme`, `CampusCard`, `CampusButton`, `CampusInput`, `EmptyState`, `ErrorState`, and `AppShell(activeTab, onTabChange, content)`.

- [ ] Write a failing test that asserts light and dark token sets contain distinct background, surface, text, and primary colors.
- [ ] Run the test and confirm the token module is absent.
- [ ] Implement the token set, card/input/button/error primitives, and five-tab floating shell to match Android hierarchy.
- [ ] Copy only required drawable/video assets from `android/app/src/main/res` into HarmonyOS media resources.
- [ ] Re-run the token test and build the project.

### Task 3: Implement typed API and authentication

**Files:**
- Create: `harmony/entry/src/main/ets/data/Models.ets`, `harmony/entry/src/main/ets/data/ApiClient.ets`, `harmony/entry/src/main/ets/data/AppRepository.ets`
- Create: `harmony/entry/src/main/ets/features/login/LoginPage.ets`
- Test: `harmony/entry/src/test/ets/data/ApiClient.test.ets`, `harmony/entry/src/test/ets/data/AppRepository.test.ets`

**Interfaces:**
- Consumes `AppState`.
- Produces `ApiClient.login(username, password)`, `ApiClient.get<T>(path)`, `ApiClient.post<T>(path, body)`, `AppRepository.login(username, password)`, and `AppRepository.chat(message)`.

- [ ] Write failing tests for API URL normalization, bearer header construction, and successful login session persistence.
- [ ] Run the tests and confirm the client/repository imports fail.
- [ ] Implement typed HTTP handling, JSON decoding, server-error conversion, session persistence, and the Android-equivalent login page.
- [ ] Re-run tests, then verify login errors render an actionable inline error state.

### Task 4: Implement root navigation and primary pages

**Files:**
- Create: `harmony/entry/src/main/ets/navigation/Routes.ets`, `harmony/entry/src/main/ets/features/dashboard/DashboardPage.ets`
- Create: `harmony/entry/src/main/ets/features/tasks/TasksPage.ets`, `harmony/entry/src/main/ets/features/notifications/NotificationsPage.ets`
- Create: `harmony/entry/src/main/ets/features/counselor/CounselorPage.ets`, `harmony/entry/src/main/ets/features/profile/ProfilePage.ets`
- Modify: `harmony/entry/src/main/ets/pages/Index.ets`
- Test: `harmony/entry/src/test/ets/navigation/Routes.test.ets`

**Interfaces:**
- Consumes `AppRepository`, `AppShell`, and `CampusTheme`.
- Produces `RouteController.go(route)`, `RouteController.back()`, and the five primary pages.

- [ ] Write failing route tests for login restoration, primary tab changes, and back-stack restoration.
- [ ] Run the tests and confirm no route controller exists.
- [ ] Implement route state, root selection, transition gating by reduced motion, dashboard quick links, task list, notice list, AI chat, and profile overview.
- [ ] Re-run route tests and build the entry module.

### Task 5: Implement academic and productivity routes

**Files:**
- Create: `harmony/entry/src/main/ets/features/courses/CoursesPage.ets`, `harmony/entry/src/main/ets/features/exams/ExamsPage.ets`
- Create: `harmony/entry/src/main/ets/features/classrooms/ClassroomsPage.ets`, `harmony/entry/src/main/ets/features/focus/FocusPage.ets`
- Modify: `harmony/entry/src/main/ets/data/AppRepository.ets`, `harmony/entry/src/main/ets/navigation/Routes.ets`
- Test: `harmony/entry/src/test/ets/features/focus/FocusTimer.test.ets`

**Interfaces:**
- Produces `FocusTimer.start(durationSeconds)`, `FocusTimer.pause()`, `FocusTimer.reset()`, and routes for courses, exams, classrooms, and focus.

- [ ] Write failing timer tests for start, pause, tick, completion, and reset.
- [ ] Run the timer test and confirm it fails because `FocusTimer` is absent.
- [ ] Implement server-backed course/exam/classroom pages and the resilient focus timer with the Android no-camera fallback.
- [ ] Re-run timer tests and verify every new route can open and return.

### Task 6: Implement services and lost-and-found flows

**Files:**
- Create: `harmony/entry/src/main/ets/features/services/ServicesPage.ets`, `harmony/entry/src/main/ets/features/services/ServiceFormPage.ets`
- Create: `harmony/entry/src/main/ets/features/lostfound/LostFoundPage.ets`, `harmony/entry/src/main/ets/features/lostfound/LostFoundFormPage.ets`
- Modify: `harmony/entry/src/main/ets/data/Models.ets`, `harmony/entry/src/main/ets/data/AppRepository.ets`, `harmony/entry/src/main/ets/navigation/Routes.ets`
- Test: `harmony/entry/src/test/ets/data/ModuleRepositories.test.ets`

**Interfaces:**
- Produces `AppRepository.createServiceRequest(payload)` and `AppRepository.publishLostFound(payload)`.

- [ ] Write failing repository tests that assert valid payload submission and readable failure responses.
- [ ] Run the tests and confirm submission APIs are missing.
- [ ] Implement list/detail/create interactions for service requests and lost-and-found, including loading/empty/error states.
- [ ] Re-run tests and build the complete navigation graph.

### Task 7: Implement profile, settings, and platform capability fallbacks

**Files:**
- Create: `harmony/entry/src/main/ets/features/profile/SettingsPage.ets`, `harmony/entry/src/main/ets/features/profile/PersonalHubPage.ets`
- Create: `harmony/entry/src/main/ets/platform/CameraCapability.ets`, `harmony/entry/src/main/ets/platform/NotificationInbox.ets`
- Modify: `harmony/entry/src/main/ets/features/profile/ProfilePage.ets`, `harmony/entry/src/main/ets/navigation/Routes.ets`
- Test: `harmony/entry/src/test/ets/platform/CapabilityFallback.test.ets`

**Interfaces:**
- Produces `CameraCapability.status()` and `NotificationInbox.load()` with explicit unavailable states.

- [ ] Write failing tests for unavailable-camera and server-notice fallback messages.
- [ ] Run the tests and confirm capability modules are missing.
- [ ] Implement theme/motion/account settings, personal hub, camera permission status, and server-backed notification inbox fallback.
- [ ] Re-run tests and verify sign-out returns to login without stale route state.

### Task 8: Verify visual parity and delivery quality

**Files:**
- Modify: `harmony/README.md`
- Test: `harmony/entry/src/ohosTest/ets/test/NavigationSmoke.test.ets`

**Interfaces:**
- Consumes the completed application routes and repository interfaces.

- [ ] Write a failing smoke test that opens login, restores a session, changes all five tabs, opens a secondary route, and returns.
- [ ] Run the smoke test and confirm it identifies any missing route registration.
- [ ] Implement missing registrations and document build, configuration, feature parity, and platform limitations in `harmony/README.md`.
- [ ] Run unit tests, device/emulator smoke test, and the Hvigor production build.
- [ ] Compare implemented screens against Android reference at the same viewport and correct any remaining layout or content mismatches.

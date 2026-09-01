# Android Gamified Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Classic and Gamified Android dashboards in one app with persisted style selection and idempotent, real-activity-driven gamification.

**Architecture:** Keep `AppRepository` and module repositories as the data sources. Add pure gamification rules plus a small DataStore-backed store, map combined facts in a ViewModel, and render two presentation branches behind one `DashboardScreen` route.

**Tech Stack:** Kotlin 2.0.21, Jetpack Compose Material 3, Navigation Compose 2.9.8, DataStore Preferences, Coroutines/Flow, Moshi, JUnit 4.

**Spec:** `android/docs/specs/2026-09-01-gamified-dashboard-design.md`

## Global Constraints

- Modify only `android/`; preserve all existing routes, repositories, APIs, and other clients.
- Use `android/.tools/jdk21-full/jdk-21.0.12+8` for every Gradle/JVM command.
- Do not award XP from page refreshes, course presence, expression recognition, or behavior recognition.
- Do not add coins, shop, equipment, pets, ranking, PvP, or social systems.
- Use centralized theme tokens and honor the existing reduce-motion setting.

---

### Task 1: Gamification contracts and rules

**Files:**
- Create: `android/app/src/main/java/com/example/campusai/features/gamification/GamificationModels.kt`
- Create: `android/app/src/main/java/com/example/campusai/features/gamification/LevelCalculator.kt`
- Create: `android/app/src/main/java/com/example/campusai/features/gamification/GamificationEngine.kt`
- Test: `android/app/src/test/java/com/example/campusai/features/gamification/DashboardStyleTest.kt`
- Test: `android/app/src/test/java/com/example/campusai/features/gamification/LevelCalculatorTest.kt`
- Test: `android/app/src/test/java/com/example/campusai/features/gamification/XpEventTest.kt`

**Interfaces:**
- Produces: `DashboardStyle.fromStoredValue(String?)`, `LevelCalculator.calculate(Int)`, and `GamificationEngine.reconcile(GamificationSnapshot, GamificationFacts, Instant, ZoneId)`.
- Event identity includes `eventType`, `sourceType`, and `sourceId`; facts include timestamped completed tasks and stable-id completed focus sessions.

- [ ] Write literal, behavior-focused tests for unknown style fallback, level boundaries, task/focus XP, daily goals, stable deduplication, real-activity streaks, and achievement unlock-once behavior.
- [ ] Run `gradlew.bat :app:testDebugUnitTest --tests "com.example.campusai.features.gamification.*" --no-daemon` and verify RED because production types do not exist.
- [ ] Implement immutable models and the minimal pure rule engine matching the spec.
- [ ] Re-run the focused tests and verify GREEN.
- [ ] Commit as `feat(android): add gamification domain rules`.

### Task 2: Persist style and gamification snapshot

**Files:**
- Create: `android/app/src/main/java/com/example/campusai/features/gamification/GamificationStore.kt`
- Modify: `android/app/src/main/java/com/example/campusai/data/local/AppDataStore.kt`
- Modify: `android/app/src/main/java/com/example/campusai/data/repository/AppRepository.kt`
- Modify: `android/app/src/main/java/com/example/campusai/data/model/Task.kt`
- Modify: `android/app/src/main/java/com/example/campusai/data/model/FocusModels.kt`
- Modify: `android/app/src/main/java/com/example/campusai/data/repository/ApiFocusRepository.kt`
- Modify: `android/app/src/main/java/com/example/campusai/data/repository/FocusRepository.kt`

**Interfaces:**
- Consumes: Task 1 rule engine.
- Produces: `AppRepository.dashboardStyle: StateFlow<DashboardStyle>`, `setDashboardStyle(DashboardStyle)`, `gamificationStore.snapshot`, `Task.completedAt`, and `FocusRecord.sourceId`.

- [ ] Extend the Task 1 tests with a round-trip snapshot codec test and verify RED.
- [ ] Add DataStore style preference and a Moshi-backed snapshot store over existing `KeyValueStorage`; tolerate missing/corrupt legacy values.
- [ ] Preserve remote task `updated_at` only when completed and preserve focus backend session ids; legacy records retain safe defaults.
- [ ] Run the focused tests and `:app:compileDebugKotlin`.
- [ ] Commit as `feat(android): persist dashboard preference and XP state`.

### Task 3: Dashboard state mapping

**Files:**
- Create: `android/app/src/main/java/com/example/campusai/ui/screens/dashboard/gamified/GamifiedDashboardUiState.kt`
- Create: `android/app/src/main/java/com/example/campusai/ui/screens/dashboard/gamified/GamifiedDashboardStateFactory.kt`
- Create: `android/app/src/main/java/com/example/campusai/ui/screens/dashboard/gamified/GamifiedDashboardViewModel.kt`
- Test: `android/app/src/test/java/com/example/campusai/ui/screens/dashboard/gamified/GamifiedDashboardStateFactoryTest.kt`

**Interfaces:**
- Consumes: existing app/module flows and Task 2 snapshot store.
- Produces: display-ready player, adventure, quest, growth, achievement, campus-world, loading, and error fields.

- [ ] Write tests for empty state, long real task/course data, upcoming-exam hero override, rewards, and loading/error propagation; verify RED.
- [ ] Implement the pure factory, then the ViewModel that refreshes and combines existing flows and reconciles facts outside Compose.
- [ ] Run focused tests and `:app:compileDebugKotlin`.
- [ ] Commit as `feat(android): map dashboard data into gamified state`.

### Task 4: Preserve Classic and wire style selection

**Files:**
- Rename: `android/app/src/main/java/com/example/campusai/ui/screens/dashboard/DashboardScreen.kt` to `ClassicDashboardScreen.kt`
- Create: `android/app/src/main/java/com/example/campusai/ui/screens/dashboard/DashboardScreen.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/profile/SettingsScreen.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/navigation/AppNavHost.kt`

**Interfaces:**
- Consumes: `AppRepository.dashboardStyle` and existing navigation callbacks.
- Produces: one unchanged `home` route that selects Classic/Gamified immediately and a two-option settings selector.

- [ ] Rename only the Classic entry composable and keep its internal layout/functions intact.
- [ ] Add the route wrapper and pass existing app/exam/focus dependencies without changing route strings.
- [ ] Add an accessible Classic/Gamified selector under display settings.
- [ ] Run style tests and `:app:compileDebugKotlin`.
- [ ] Commit as `feat(android): add persisted dashboard style switch`.

### Task 5: Compose Gamified dashboard

**Files:**
- Create: `android/app/src/main/java/com/example/campusai/ui/theme/GamificationTokens.kt`
- Create: `android/app/src/main/java/com/example/campusai/ui/screens/dashboard/gamified/GamifiedDashboardScreen.kt`
- Create: `android/app/src/main/java/com/example/campusai/ui/screens/dashboard/gamified/GamifiedDashboardHero.kt`
- Create: `android/app/src/main/java/com/example/campusai/ui/screens/dashboard/gamified/GamifiedDashboardSections.kt`
- Test: `android/app/src/test/java/com/example/campusai/ui/screens/dashboard/gamified/GamifiedDashboardLayoutPolicyTest.kt`

**Interfaces:**
- Consumes: Task 3 immutable UI state and unchanged route callbacks.
- Produces: all seven required dashboard sections, achievement details dialog, finite progress/completion animations, and compact/wide layout policy.

- [ ] Write layout-policy tests for small, normal, and large phone widths and verify RED.
- [ ] Implement centralized blue/indigo/purple/amber/green tokens and the keyed `LazyColumn` orchestration.
- [ ] Implement player/adventure/main-quest components with animated progress disabled by reduce-motion.
- [ ] Implement side quests, growth, achievement dialog, campus world, and explicit empty/loading/error presentations.
- [ ] Add phone-width previews with long and empty sample states; use Compose-native decoration only.
- [ ] Run focused tests and `:app:compileDebugKotlin`.
- [ ] Commit as `feat(android): build adaptive gamified dashboard`.

### Task 6: Verification and review

**Files:**
- Inspect all changed Android files and Git history; no new production file is required.

**Interfaces:**
- Consumes: Tasks 1-5.
- Produces: verified branch history and final acceptance report.

- [ ] Run focused gamification/style/layout tests with the bundled JDK and require zero failures.
- [ ] Run full `:app:testDebugUnitTest`; compare any failures with the two recorded baseline failures.
- [ ] Run `:app:assembleDebug` and require exit code 0.
- [ ] Inspect `git diff`, `git diff --cached`, `git status`, and staged content for secrets or machine-specific paths.
- [ ] Dispatch a read-only code-review agent over the branch range, fix Critical/Important findings, and re-run affected verification.
- [ ] Commit final fixes with a descriptive Android-only commit and report branch, files, tests, build, commit hash, and remaining issues.

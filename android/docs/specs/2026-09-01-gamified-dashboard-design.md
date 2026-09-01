# Android Gamified Dashboard Design

## Scope

Add a second Android dashboard presentation without changing backend, Web, HarmonyOS, or WeChat code. `ClassicDashboardScreen` keeps the existing layout and routes. `GamifiedDashboardScreen` consumes the same Android repositories and is selected by a DataStore-backed `DashboardStyle` preference.

## Audited data sources

- User, tasks, courses, campus news, and home banners: existing `AppRepository` flows. Tasks and courses are remote-first; campus news and courses can retain existing default data when remote data is unavailable.
- Task completion: remote `PersonalTaskDto.status == "completed"`; `updated_at` is retained as the Android completion timestamp because the API does not expose `completed_at`.
- Focus: existing `ApiFocusRepository` completed sessions. The backend session id is preserved in `FocusRecord.sourceId` for stable XP deduplication.
- Exams: existing `ExamRepository`. Its local implementation persists records and seeds first-run demo exams when no saved records exist.
- Campus world: existing `AppRepository.campusNews` and unchanged `campus-news-detail/{id}` routes.
- AI counselor, focus, classrooms, services, lost and found, exams, courses, tasks, profile, and community: unchanged Navigation Compose routes.
- Existing Classic-only fixed UI: the Classic course schedule and 72% weekly overview remain unchanged to preserve the current dashboard. Gamified UI does not reuse those fixed values.

## Architecture

`AppRepository` remains the app-wide data source and gains only the persisted dashboard style plus access to a focused `GamificationStore`. Pure classes in `features/gamification` own XP reconciliation, level thresholds, streaks, achievement evaluation, and summary calculations. Event identity is `eventType + sourceType + sourceId`, so opening or refreshing the dashboard cannot add XP twice.

`GamifiedDashboardViewModel` combines existing user/task/course/news, exam, focus, and gamification flows into an immutable `GamifiedDashboardUiState`. A pure state factory maps those facts to Daily Adventure, main quests, growth metrics, achievements, and loading/error states. Compose receives display-ready state and callbacks only.

The top-level `DashboardScreen` switches immediately between Classic and Gamified presentations based on `AppRepository.dashboardStyle`. Settings persists the selected style through DataStore. Navigation routes are passed through unchanged.

## XP and activity policy

- Completed normal task: 20 XP; high or urgent task: 30 XP.
- Completed focus session of at least 25 minutes: 15 XP.
- First real completed task on a local date: 20 XP daily goal.
- At least 60 real focus minutes on a local date: 30 XP daily goal.
- Streak dates come only from completed tasks with a real completion timestamp and finished focus records.
- Legacy/default completed tasks without a completion timestamp are displayed but do not award XP or extend streaks.
- Level 1 requires 100 XP; each next threshold grows by 25 XP, matching the Web policy.

## UI and adaptation

The gamified screen is a keyed `LazyColumn` with Player Header, Daily Adventure, Main Quest, Campus Exploration, Growth, Achievement, and Campus World sections. Compact phone widths use a two-column side-quest grid and stacked metrics; wider phones use a three-column grid and wider metric rows. Long titles are ellipsized, empty/loading/error states stay actionable, and all animations honor the existing reduce-motion preference. Visuals use Compose gradients, Canvas decoration, and centralized gamification color tokens; no generated images are required.

## Verification

Pure JVM tests cover `DashboardStyle`, level boundaries, XP event identity and reconciliation, daily rewards, streaks, achievements, and UI-state mapping for empty/exam/data states. Build verification uses the repository-bundled JDK 21.0.12 and `:app:testDebugUnitTest` plus `:app:assembleDebug`. Two unrelated baseline test failures are recorded before implementation and are not part of this change.

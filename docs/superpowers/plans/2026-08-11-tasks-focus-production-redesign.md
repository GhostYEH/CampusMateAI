# Tasks and Focus Production Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Rebuild the task and focus screens from the supplied references while making backend database records the only source of business truth.

**Architecture:** FastAPI gains a user-scoped persisted daily-goal resource beside the existing server-clock study-session machine. Android adds typed study DTOs and a remote focus repository, removes generated/local task and focus records, then renders the new repository states in Compose.

**Tech Stack:** FastAPI, SQLite, pytest, Android Jetpack Compose, Retrofit, Moshi, coroutines and JVM tests.

## Global Constraints

- All reads and writes require JWT identity and service-side user ownership checks.
- Do not render fabricated task, course, activity, timer, focus record, statistic, or goal data.
- Failed writes retain last confirmed remote state, expose an error, and provide retry.
- Server session state and server-computed duration win on app resume and after every mutation.
- Preserve unrelated edits outside this isolated worktree.

---

### Task 1: Persist daily focus goals in the backend

**Files:**
- Modify: backend/app/database/sqlite_db.py
- Create: backend/app/models/study_goal.py
- Create: backend/app/repositories/study_goal_repository.py
- Modify: backend/app/schemas/study.py
- Modify: backend/app/api/routes/study.py
- Test: backend/tests/test_study_goals.py

**Interfaces:**
- Produces: StudyGoalOut(target_minutes: int, updated_at: str)
- Produces: StudyGoalRepository.get_or_create(user_id: str) and set_target(user_id: str, target_minutes: int)

- [ ] **Step 1: Write the failing test**

    def test_goal_is_scoped_and_persisted():
        student = _headers(_client(), "student_demo")
        assert get_goal(student)["target_minutes"] == 60
        assert put_goal(student, 90)["target_minutes"] == 90
        assert get_goal(student)["target_minutes"] == 90

- [ ] **Step 2: Run test to verify it fails**

Run: python -m pytest tests/test_study_goals.py::test_goal_is_scoped_and_persisted -q
Expected: FAIL because /study/goals/daily does not exist.

- [ ] **Step 3: Write minimal implementation**

Create a migration-safe study_goals table with user_id as its primary key, target_minutes CHECK constrained to 15 through 480, and updated_at. Add authenticated GET and PUT /api/v1/study/goals/daily routes. GET inserts and returns a 60-minute default only for the requesting user.

- [ ] **Step 4: Run test to verify it passes**

Run: python -m pytest tests/test_study_goals.py -q
Expected: PASS for persistence, user isolation, 15/480 bounds, and 422 range failures.

- [ ] **Step 5: Commit**

Run:
    git add backend/app/database/sqlite_db.py backend/app/models/study_goal.py backend/app/repositories/study_goal_repository.py backend/app/schemas/study.py backend/app/api/routes/study.py backend/tests/test_study_goals.py
    git commit -m "feat: persist per-user study goals"

### Task 2: Replace Android local focus records with the existing study API

**Files:**
- Modify: android/app/src/main/java/com/example/campusai/data/remote/ApiService.kt
- Modify: android/app/src/main/java/com/example/campusai/data/model/FocusModels.kt
- Modify: android/app/src/main/java/com/example/campusai/data/repository/FocusRepository.kt
- Modify: android/app/src/main/java/com/example/campusai/data/repository/ModuleRepositories.kt
- Test: android/app/src/test/java/com/example/campusai/RemoteFocusRepositoryTest.kt

**Interfaces:**
- Produces: FocusUiState(records, activeSession, stats, goalMinutes, loading, error)
- Produces: FocusRepository.refresh(), start(goal, relatedTaskId), pause(), resume(), finish(), setGoal(minutes), each returning Result.

- [ ] **Step 1: Write the failing test**

    @Test fun server_completed_sessions_derive_today_statistics() = runTest {
        val repository = RemoteFocusRepository(fakeStudyApi(completedSession(minutes = 25)))
        repository.refresh()
        assertEquals(25, repository.state.value.stats.todayMinutes)
    }

- [ ] **Step 2: Run test to verify it fails**

Run: gradlew testDebugUnitTest --tests com.example.campusai.RemoteFocusRepositoryTest
Expected: FAIL because RemoteFocusRepository is absent.

- [ ] **Step 3: Write minimal implementation**

Add Retrofit DTOs and calls for GET/POST study sessions, active, pause, resume, finish and daily goal. Implement RemoteFocusRepository so refresh reads active session, completed sessions and goal; derives UI statistics from returned sessions; and only changes flows after successful calls. Use it from ModuleRepositories instead of LocalFocusRepository.

- [ ] **Step 4: Run test to verify it passes**

Run: gradlew testDebugUnitTest --tests com.example.campusai.RemoteFocusRepositoryTest
Expected: PASS for server-derived statistics, retained state after failed mutations, and successful goal updates.

- [ ] **Step 5: Commit**

Run:
    git add android/app/src/main/java/com/example/campusai/data/remote/ApiService.kt android/app/src/main/java/com/example/campusai/data/model/FocusModels.kt android/app/src/main/java/com/example/campusai/data/repository/FocusRepository.kt android/app/src/main/java/com/example/campusai/data/repository/ModuleRepositories.kt android/app/src/test/java/com/example/campusai/RemoteFocusRepositoryTest.kt
    git commit -m "feat: connect focus sessions to backend"

### Task 3: Make task state backend-authoritative

**Files:**
- Modify: android/app/src/main/java/com/example/campusai/data/repository/AppRepository.kt
- Modify: android/app/src/main/java/com/example/campusai/data/remote/ApiService.kt
- Test: android/app/src/test/java/com/example/campusai/TaskRepositoryStateTest.kt

**Interfaces:**
- Produces: TaskLoadState(items, isLoading, stale, error)
- Produces: task mutations returning Result rather than silently falling back to local records.

- [ ] **Step 1: Write the failing test**

    @Test fun empty_server_response_clears_default_tasks() = runTest {
        val repository = taskRepositoryReturning(emptyList())
        repository.refreshTasks()
        assertTrue(repository.tasks.value.isEmpty())
    }

- [ ] **Step 2: Run test to verify it fails**

Run: gradlew testDebugUnitTest --tests com.example.campusai.TaskRepositoryStateTest
Expected: FAIL because the current repository preserves defaultTasks on empty responses.

- [ ] **Step 3: Write minimal implementation**

Remove defaultTasks and local_* creation. Successful empty responses set the task list to empty. Failed list or mutation calls retain only the previously server-confirmed list and populate TaskLoadState.error. Add API query parameters for server-side status, priority and deadline filters.

- [ ] **Step 4: Run test to verify it passes**

Run: gradlew testDebugUnitTest --tests com.example.campusai.TaskRepositoryStateTest
Expected: PASS for empty reads, create failures, toggle failures, and refresh errors.

- [ ] **Step 5: Commit**

Run:
    git add android/app/src/main/java/com/example/campusai/data/repository/AppRepository.kt android/app/src/main/java/com/example/campusai/data/remote/ApiService.kt android/app/src/test/java/com/example/campusai/TaskRepositoryStateTest.kt
    git commit -m "fix: make task state backend authoritative"

### Task 4: Implement screenshot-faithful task and focus flows

**Files:**
- Modify: android/app/src/main/java/com/example/campusai/ui/screens/tasks/TasksScreen.kt
- Modify: android/app/src/main/java/com/example/campusai/ui/screens/tasks/TaskDetailScreen.kt
- Create: android/app/src/main/java/com/example/campusai/ui/screens/tasks/TaskCalendarScreen.kt
- Modify: android/app/src/main/java/com/example/campusai/ui/screens/focus/FocusScreen.kt
- Modify: android/app/src/main/java/com/example/campusai/ui/navigation/AppNavHost.kt
- Test: android/app/src/test/java/com/example/campusai/ui/TasksFocusRouteTest.kt

**Interfaces:**
- Consumes: TaskLoadState and FocusUiState.
- Produces: tasks/calendar?date=YYYY-MM-DD and focus?taskId={realTaskId} routes.

- [ ] **Step 1: Write the failing test**

    @Test fun task_calendar_route_contains_selected_date() {
        assertEquals("tasks/calendar?date=2026-05-14", TaskCalendarRoute.forDate(LocalDate.of(2026, 5, 14)))
    }

- [ ] **Step 2: Run test to verify it fails**

Run: gradlew testDebugUnitTest --tests com.example.campusai.ui.TasksFocusRouteTest
Expected: FAIL because TaskCalendarRoute does not exist.

- [ ] **Step 3: Write minimal implementation**

Recreate the supplied shallow-card, blue-purple visual hierarchy. Tasks renders real derived statistics, date strip, search and filters, smart focus, responsive summary cards, calendar page, detail page, and backend action errors. Focus renders mode selector, dotted circular timer, assistance state, backend-derived stats and daily-goal sheet. Start awaits successful server session creation; pause/resume/finish await server responses; every secondary control has a matching route or modal.

- [ ] **Step 4: Run test to verify it passes**

Run: gradlew testDebugUnitTest --tests com.example.campusai.ui.TasksFocusRouteTest
Expected: PASS for calendar date and focus task handoff route building.

- [ ] **Step 5: Commit**

Run:
    git add android/app/src/main/java/com/example/campusai/ui/screens/tasks android/app/src/main/java/com/example/campusai/ui/screens/focus/FocusScreen.kt android/app/src/main/java/com/example/campusai/ui/navigation/AppNavHost.kt android/app/src/test/java/com/example/campusai/ui/TasksFocusRouteTest.kt
    git commit -m "feat: redesign database-backed tasks and focus"

### Task 5: Verify production data path and visual fidelity

**Files:**
- Modify: design-qa.md
- Test: backend/tests/test_study_goals.py
- Test: backend/tests/test_personal_tasks.py
- Test: Android tests introduced in Tasks 2 through 4.

- [ ] **Step 1: Write the failing test**

    def test_finished_session_is_visible_after_write():
        session = create_session()
        finish(session["id"])
        assert list_sessions()[0]["status"] == "completed"

- [ ] **Step 2: Run test to verify it fails**

Run: python -m pytest tests/test_study_goals.py tests/test_personal_tasks.py -q
Expected: FAIL until goal and write-read coverage are complete.

- [ ] **Step 3: Complete verification implementation**

Add the write-read integration assertion, start the backend against a disposable database, capture the task and focus screens at the reference viewport, compare the matching interaction states, and record findings in design-qa.md.

- [ ] **Step 4: Run verification to confirm it passes**

Run: python -m pytest tests/test_study_goals.py tests/test_personal_tasks.py -q
Run: gradlew testDebugUnitTest
Expected: all selected tests PASS and design-qa.md ends with final result: passed.

- [ ] **Step 5: Commit**

Run:
    git add backend/tests android/app/src/test/java/com/example/campusai design-qa.md
    git commit -m "test: verify tasks and focus production flow"


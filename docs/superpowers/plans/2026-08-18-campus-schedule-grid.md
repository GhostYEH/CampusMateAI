# Campus Schedule Grid Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with tests and build checkpoints.

**Goal:** Replace the four timetable list views with a defensive weekday-by-section grid while preserving week filtering, course details, semester isolation, and manual/education data behavior.

**Architecture:** Keep the existing `edu/schedule/items` contract and normalize layout only at the clients. Each client derives visible sessions from normalized `weekday`, `start_section`, and `end_section`, computes the maximum section dynamically (minimum 12), and renders overlapping sessions in equal-width lanes. Invalid coordinates are ignored for the grid but never crash the page; details continue to use the original session object.

**Tech Stack:** Kotlin/Jetpack Compose, ArkUI/ArkTS, Vue 3/CSS Grid, WeChat Mini Program WXML/WXSS/TypeScript, Python/Pydantic tests.

**Spec:** User-provided CampusMateAI weekday × section timetable requirements in the current task.

## Global Constraints

- Preserve the existing academic login, connection, discovery, session, grade sync, and schedule API behavior.
- Do not add a second schedule API.
- Main cards show only course name and optional location; all other fields remain in details.
- Use normalized schedule JSON; do not parse `rawExtra` or `rawHtml` in clients.
- Never use unchecked weekday/section array indexing.
- Use the project JDK `F:\demo1\android\.tools\jdk21-full\jdk-21.0.12+8` for Android commands.
- Preserve unrelated pre-existing worktree changes.

---

### Task 1: Lock down schedule coordinate rules

**Files:**
- Modify: `backend/app/services/edu/normalizer.py`
- Modify: `backend/tests/test_edu_schedule_fields.py`
- Create: `android/app/src/main/java/com/example/campusai/ui/screens/profile/EduScheduleLayout.kt`
- Create: `android/app/src/test/java/com/example/campusai/ui/screens/profile/EduScheduleLayoutTest.kt`

- [ ] Add regression tests for valid 1–7 weekdays, 1–12+ sections, invalid coordinates, reversed ranges, week filtering, and overlap lane allocation.
- [ ] Run the focused tests and observe the expected failures.
- [ ] Implement minimal normalization/layout helpers with duration clamped to at least one section and safe coordinate validation.
- [ ] Run focused tests again and keep the existing full schedule-field tests green.

### Task 2: Convert Android to a horizontally scrollable section grid

**Files:**
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/profile/EduScheduleScreen.kt`

- [ ] Render a header row for seven weekdays and a section column for a dynamic maximum section (minimum 12).
- [ ] Position cards by `weekday`, `start_section`, and `end_section`; use dynamic height and equal lanes for overlaps.
- [ ] Keep stable course colors, name/location-only card content, whole-card click handling, empty-state handling, and the existing scrollable detail sheet.
- [ ] Run Android unit tests and debug build with the mandated JDK.

### Task 3: Convert Harmony to an ArkUI weekday × section grid

**Files:**
- Modify: `harmony/entry/src/main/ets/features/edu/EduSchedulePage.ets`

- [ ] Replace `scheduleGroups` list rendering with a horizontally scrollable grid and section rows.
- [ ] Keep ArkTS-typed data structures, dynamic section count, safe filtering, stable colors, conflict lanes, and overlay detail behavior.
- [ ] Run the project Harmony test/build command and fix ArkTS compiler errors.

### Task 4: Convert Web to CSS Grid

**Files:**
- Modify: `web/src/views/student/StudentAcademicView.vue`

- [ ] Derive valid grid sessions, dynamic section count, conflict lanes, and CSS grid row/column placement from normalized data.
- [ ] Replace weekday-group markup with a horizontally scrollable timetable; retain desktop readability and mobile overflow.
- [ ] Keep the existing modal details and all field visibility rules.
- [ ] Run `npm run build`.

### Task 5: Convert WX to a horizontally scrollable timetable

**Files:**
- Modify: `wx/miniprogram/package-academic/pages/edu/edu.ts`
- Modify: `wx/miniprogram/package-academic/pages/edu/edu.wxml`
- Modify: `wx/miniprogram/package-academic/pages/edu/edu.wxss`

- [ ] Derive safe positioned cards with dynamic section rows and conflict lanes.
- [ ] Render the grid inside horizontal `scroll-view`, preserving card tap events and the detail popup.
- [ ] Keep semester/week filtering and avoid unchecked `WEEKDAY_LABELS` access for invalid data.
- [ ] Run `npm run typecheck` and any formal package checks that are already configured.

### Task 6: Cross-platform verification and cleanup

- [ ] Run backend Edu/Schedule regression tests.
- [ ] Run Android debug build with JDK 21, Harmony `assembleHap`, Web build, and WX typecheck.
- [ ] Inspect diffs and confirm no secrets, temporary reports, test dumps, or unrelated files were introduced.
- [ ] Report the original layouts, changes, verification evidence, test-file decision, remaining limits, diff stat, and status.

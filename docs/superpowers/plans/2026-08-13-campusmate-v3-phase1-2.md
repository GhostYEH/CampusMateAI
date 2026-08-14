# CampusMateAI V3 Phase 1-2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清理教师/审批型产品入口并建立可迁移、可测试的 University Core。

**Architecture:** 使用兼容式纵向切片：Backend schema/API 先行，Android 先切换，HarmonyOS/Web 随后复用同一契约；旧数据列和历史表先保留但停止运行时暴露。

**Tech Stack:** FastAPI、Pydantic v2、SQLite、pytest、Kotlin/Jetpack Compose、ArkTS、Vue 3/Vite。

## Global Constraints

- 不执行 git reset/clean/checkout/restore/commit，不覆盖用户未提交代码。
- 所有新 API 使用 `/api/v1`，分页返回 `items/page/page_size/total`。
- 正式角色仅 `student`、`admin`；`teacher_name` 课程元数据保留。
- 大学公共数据默认由 `current_user.university_id` 隔离。
- Android 构建固定 JDK 17。
- 不伪造真实学校教务支持，不持久化或返回教务密码。

---

### Task 1: University schema migration and seed

**Files:**
- Modify: `backend/app/database/sqlite_db.py`
- Modify: `backend/app/services/demo_seeder.py`
- Create: `backend/tests/test_universities.py`

**Interfaces:**
- Produces: `universities` table and nullable `users.university_id`.
- Produces: Demo University bound to `student_demo`.

- [ ] Write failing migration tests proving a legacy database gains the table/column without losing users.
- [ ] Run `python -m pytest tests/test_universities.py -q` and confirm the missing schema failure.
- [ ] Add idempotent table/column/index creation and seed data.
- [ ] Re-run targeted tests and `tests/test_sqlite_migrations.py`.

### Task 2: University repository, schemas and API

**Files:**
- Create: `backend/app/repositories/university_repository.py`
- Create: `backend/app/schemas/university.py`
- Create: `backend/app/api/routes/universities.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/app/services/container.py`
- Test: `backend/tests/test_universities.py`

**Interfaces:**
- Produces: `GET /api/v1/universities`, `GET /api/v1/universities/{id}`, `PUT /api/v1/profile/university`.
- Produces: stable pagination contract and university_required semantics.

- [ ] Add failing API tests for search, filters, pagination, selection and null-compatible legacy users.
- [ ] Run targeted tests and verify route-not-found failures.
- [ ] Implement repository, schema, dependencies and routes with authenticated selection.
- [ ] Run targeted and full Backend tests.

### Task 3: Runtime teacher and approval cleanup

**Files:**
- Modify: `web/src/router.js`
- Delete: `web/src/views/teacher/*.vue`
- Modify: Android service navigation and screens under `ui/screens/services/`
- Modify: HarmonyOS services route/page
- Modify: Web student services route/page
- Test: existing navigation tests plus new no-legacy-route assertions.

**Interfaces:**
- Removes runtime teacher/approval entry points while preserving course teacher metadata and student assignments.
- Produces: Campus Life navigation using real implemented destinations.

- [ ] Add failing route/navigation tests asserting removed teacher and approval routes.
- [ ] Remove clients from deprecated service API calls.
- [ ] Replace “办事大厅” with “校园生活” and real destinations/official-guide semantics.
- [ ] Remove dead imports/files only after global reference scan is empty.

### Task 4: Android University picker

**Files:**
- Modify: `android/app/src/main/java/com/example/campusai/data/remote/ApiService.kt`
- Create: `android/app/src/main/java/com/example/campusai/data/repository/UniversityRepository.kt`
- Create: `android/app/src/main/java/com/example/campusai/ui/screens/university/UniversityPickerScreen.kt`
- Modify: Android navigation/profile files.
- Test: `android/app/src/test/java/com/example/campusai/UniversityRepositoryTest.kt`

**Interfaces:**
- Consumes: University API from Task 2.
- Produces: loading/success/empty/error search and switch confirmation.

- [ ] Write repository contract tests before implementation.
- [ ] Implement DTO/repository and UI state mapping.
- [ ] Add profile entry and optional first-login prompt.
- [ ] Run JDK17 unit tests, compileDebugKotlin and assembleDebug.

### Task 5: HarmonyOS and Web University parity

**Files:**
- Modify: `harmony/entry/src/main/ets/data/Models.ets`
- Modify: `harmony/entry/src/main/ets/data/ApiClient.ets`
- Create: HarmonyOS University picker/profile page.
- Modify: `web/src/services/studentApi.js`
- Create: Web University picker/profile view.
- Modify: routes and profile navigation.

**Interfaces:**
- Consumes: same `/api/v1/universities` and `/profile/university` contract.
- Produces: equivalent user flow and capability labels without hard-coded school lists.

- [ ] Add contract/layout assertions first.
- [ ] Implement four-state UI and switch warning.
- [ ] Run Harmony build and Web production build.

### Task 6: Phase evidence and parity matrix

**Files:**
- Create: `docs/V3_PARITY_MATRIX.md`
- Modify: `docs/V3_MIGRATION_AUDIT.md`

**Interfaces:**
- Produces: truthful DONE/PARTIAL/PLATFORM_LIMITED/MISSING evidence.

- [ ] Record exact routes/files removed and migration behavior.
- [ ] Record actual commands and outcomes without upgrading static UI to DONE.
- [ ] Run full phase tests and `git diff --stat`.

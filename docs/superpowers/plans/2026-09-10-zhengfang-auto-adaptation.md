# Zhengfang Auto-Adaptation Implementation Plan

> **Required sub-skill:** Use `executing-plans` to implement this plan task by task. Use `test-driven-development` for every behavioral change, `systematic-debugging` for unexpected failures, and `verification-before-completion` before reporting completion.

**Goal:** Make Web, Android, and HarmonyOS reliably log in through the existing backend-driven flow and synchronize schedules from most Zhengfang deployments without guessing endpoints or overwriting a valid schedule with uncertain data.

**Architecture:** Keep all school-page parsing in the FastAPI backend. Discover schedule capabilities only from authenticated, exact-origin menu/page evidence; classify and strictly parse responses; validate the complete batch before the existing transactional repository writes it. Expose additive sync diagnostics to all clients. Image CAPTCHA remains human-entered and complex challenges remain in the constrained WebView.

**Tech Stack:** Python 3 / FastAPI / Pydantic / httpx / pytest; React / Vite / Node tests; Kotlin / Jetpack Compose / Retrofit / JUnit; ArkTS / ArkUI / Hvigor.

**Spec:** `docs/superpowers/specs/2026-09-10-zhengfang-auto-adaptation-design.md`

**Global Constraints:** Never persist or log credentials, cookies, CAPTCHA answers, student data, or raw upstream responses. Only HTTPS exact-origin URLs derived from authenticated evidence may be requested. Do not OCR or bypass any challenge. Do not change the database schema or existing required response fields. Do not touch unrelated dirty Web files. JVM commands must use `android/.tools/jdk21-full/jdk-21.0.12+8`.

---

## Task 1: Add authenticated Zhengfang schedule capability discovery

**Files:**
- Create: `backend/app/services/edu/adapters/zhengfang_discovery.py`
- Modify: `backend/app/services/edu/adapters/zhengfang_strategy.py`
- Test: `backend/tests/test_zhengfang_discovery.py`
- Fixture: `backend/tests/fixtures/edu/zhengfang/menu_schedule.html`
- Fixture: `backend/tests/fixtures/edu/zhengfang/schedule_page.html`

1. Add failing tests for extracting the personal-schedule entry from an authenticated menu, resolving only an exact HTTPS origin, rejecting cross-origin/scheme-relative/javascript candidates, and extracting a form/script-declared data request from the selected schedule page.
2. Run `python -m pytest backend/tests/test_zhengfang_discovery.py -q` and confirm import/behavior failures.
3. Implement immutable `ScheduleProtocol`/`ScheduleCandidate` values and `ZhengfangCapabilityDiscoverer` with menu-semantic scoring, exact-origin canonicalization, query preservation, request method, semester parameter, response format hint, source path, and SHA-256 structural fingerprint. Do not include raw page text in returned diagnostics.
4. Extend `SchoolConfig` serialization with optional `schedule_protocol` data while retaining legacy `endpoint_overrides` compatibility.
5. Re-run the focused tests and commit `feat: discover Zhengfang schedule protocols from authenticated evidence`.

## Task 2: Classify, parse, and validate schedule batches fail-closed

**Files:**
- Create: `backend/app/services/edu/schedule_validator.py`
- Modify: `backend/app/services/edu/adapters/zhengfang_parser.py`
- Modify: `backend/app/schemas/edu.py`
- Test: `backend/tests/test_zhengfang_adapter.py`
- Test: `backend/tests/test_edu_schedule_validation.py`
- Fixture: `backend/tests/fixtures/edu/zhengfang/schedule_nested.json`
- Fixture: `backend/tests/fixtures/edu/zhengfang/schedule_string_wrapped.json`
- Fixture: `backend/tests/fixtures/edu/zhengfang/schedule_permission_error.html`

1. Add failing tests for JSON-string-wrapped responses, nested list containers, valid HTML tables, login/permission/verification pages, unknown payloads, weekday/section/week errors, semester conflicts, deterministic de-duplication, and explicit structurally valid empty schedules.
2. Run the two focused test modules and confirm the new cases fail.
3. Add a typed response classifier and strict parser entry point that returns both `EduSchedule` and non-sensitive structure metadata. Preserve existing parser methods as compatibility wrappers.
4. Add `EduScheduleValidator` returning `success`, `explicit_empty`, or a typed validation failure. Require course name, weekday, positive ordered sections, parseable reasonable weeks, no explicit semester conflict, and a stable de-duplication key.
5. Add only optional diagnostic fields to `EduSyncResult`: `stage`, `previous_schedule_preserved`, `requires_user_action`, and `protocol_source`.
6. Re-run focused tests and commit `feat: validate Zhengfang schedules before persistence`.

## Task 3: Integrate discovery, cache, session reuse, and retry limits

**Files:**
- Modify: `backend/app/services/edu/adapters/zhengfang_http.py`
- Modify: `backend/app/services/edu/adapters/zhengfang.py`
- Modify: `backend/app/services/edu/provider_detector.py`
- Modify: `backend/app/services/edu/connector.py`
- Modify: `backend/app/repositories/edu_repository.py`
- Test: `backend/tests/test_zhengfang_adapter.py`
- Test: `backend/tests/test_zhengfang_cookie_request.py`
- Test: `backend/tests/test_edu_connector.py`

1. Add failing tests showing one client/session is reused through login/discovery/fetch, authenticated menu discovery is used when `schedule_path` is absent, cached protocol is preferred, one stale-cache rediscovery is allowed, unsafe/error responses do not trigger path enumeration, and GET retries are bounded while login POST is not replayed.
2. Run the focused tests and confirm failures.
3. Keep a reusable `httpx.AsyncClient` within `ZhengfangHttpClient`, add explicit `aclose`, and implement bounded GET-only retry for transient transport errors.
4. In `ZhengfangAdapter.fetch_schedule`, use static verified protocol first, then session-cached protocol, then authenticated live discovery. Validate the candidate with a real read-only request and strict parser before updating the in-memory adapter session.
5. Add a narrow repository method to merge the verified, non-sensitive protocol descriptor into the existing `edu_systems.adapter_config`; call it from the connector after a successful schedule fetch, scoped to the binding’s system.
6. Remove HUEL’s deliberate `schedule_path: None` hard stop in favor of live discovery while keeping its verified login and identity endpoints.
7. Re-run focused tests and commit `feat: execute and cache verified Zhengfang schedule protocols`.

## Task 4: Guarantee preservation of the previous schedule and expose stages

**Files:**
- Modify: `backend/app/services/edu/connector.py`
- Modify: `backend/app/repositories/edu_data_repository.py`
- Test: `backend/tests/test_edu_connector.py`
- Test: `backend/tests/test_edu_data_repository.py`

1. Add failing tests proving parse/validation/fetch failures never call `sync_schedule_items`, never mark existing rows stale, and never advance `last_synced_at`; verify explicit-empty success can transactionally stale the requested semester only when the response structure explicitly declares emptiness.
2. Run the focused tests and confirm failures.
3. Validate the entire batch before entering the repository transaction. Extend `sync_schedule_items` with an explicit validated-empty mode and requested semester so deletion/staleness cannot occur from an ambiguous empty list.
4. Map failures to stable `stage` values and set `previous_schedule_preserved=true`; set `protocol_source` on successful and failed discovery/fetch results without returning raw upstream content.
5. Re-run focused tests and commit `fix: preserve schedules when upstream synchronization is uncertain`.

## Task 5: Update Web sync feedback and CAPTCHA handling

**Files:**
- Modify: `webreact/src/pages/IntegrationPages.jsx`
- Modify: `webreact/src/data/api.js`
- Create: `webreact/tests/edu-integration-contract.test.mjs`

1. Add a failing source/contract test for stage labels, preserved-schedule messaging, MIME-aware CAPTCHA data URLs, clearing old CAPTCHA input on refresh, and WebView action messaging.
2. Run `npm test -- --runInBand` from `webreact` (or the repository’s actual test command discovered from `package.json`) and confirm the new test fails.
3. Implement additive result formatting and safe CAPTCHA rendering using `captcha_mime_type`; keep the entered password only in component memory and clear sensitive fields on success/unmount.
4. Run Web tests and `npm run build`, then commit `feat: show trustworthy education sync status on web`.

## Task 6: Update Android contract and sync status

**Files:**
- Modify: `android/app/src/main/java/com/example/campusai/data/remote/ApiService.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/profile/EduSyncCoordinator.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/profile/EduViewModel.kt`
- Test: `android/app/src/test/java/com/example/campusai/ui/screens/profile/EduSyncCoordinatorTest.kt`
- Test: `android/app/src/test/java/com/example/campusai/ui/screens/profile/EduLoginSensitiveStateTest.kt`

1. Add failing unit tests for optional diagnostic DTO fields, stage-aware messages, preservation wording, and clearing CAPTCHA/token on refresh and lifecycle exit.
2. Set `JAVA_HOME` and `PATH` from the repository-bundled JDK 21, verify `java -version` contains `21.0.12`, and run the focused Gradle tests.
3. Implement DTO and coordinator/ViewModel mapping without parsing school HTML or persisting credentials/cookies.
4. Run `testDebugUnitTest` and `assembleDebug`, then commit `feat: surface verified education sync results on Android`.

## Task 7: Update HarmonyOS contract, status, and API-24 build blockers

**Files:**
- Modify: `harmony/entry/src/main/ets/data/ApiClient.ets`
- Modify: `harmony/entry/src/main/ets/features/edu/EduPostConnectController.ets`
- Modify: `harmony/entry/src/main/ets/features/profile/EduSystemPage.ets`
- Modify: `harmony/entry/src/main/ets/features/profile/ExpressionContributionPage.ets`
- Modify: `harmony/entry/src/main/ets/service/ExpressionPreprocessingLoader.ets`
- Test: `harmony/entry/src/test/ets/data/EduLoginSecurity.test.ets`

1. Add failing ArkTS tests for optional diagnostics, preservation wording, and no false success when schedule persistence/read-back fails.
2. Run the project’s existing Hvigor test command and confirm the focused failure.
3. Extend the DTO and stage mapping. Keep CAPTCHA and WebView behavior backend-driven.
4. Replace the unsupported picker enum and `TextDecoder` usage with APIs available in the configured HarmonyOS SDK, without changing the feature behavior.
5. Run Harmony tests and HAP build; record any remaining unrelated visual assertion failures separately. Commit `feat: complete education sync feedback on HarmonyOS`.

## Task 8: Full regression, security audit, and handoff

**Files:**
- Modify only if failures reveal task-related regressions in files already listed above.

1. Run backend education tests, then the full backend test suite if time permits.
2. Run full Web tests/build, Android unit tests/Debug build with bundled JDK 21, and Harmony tests/HAP build.
3. Use `rg` to verify no supplied student ID, password, Cookie, authorization token, raw authenticated page, machine-specific path, or private test data entered tracked files.
4. Review `git diff`, `git diff --cached`, and `git status`; leave pre-existing `webreact/src/pages/StudySubpages.jsx`, `webreact/src/styles/study-summer.css`, and `webreact/tests/e2e/shots/` untouched and uncommitted.
5. Do not perform another real-account login. Provide a credential-free local manual acceptance checklist for the user to run after changing their password.
6. Use `verification-before-completion` and `finishing-a-development-branch`, then create the final precise commit if verification fixes were needed.


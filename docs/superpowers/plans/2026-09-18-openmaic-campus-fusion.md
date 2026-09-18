# OpenMAIC–CampusMateAI Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Replace `/courses` with a native CampusMate-integrated OpenMAIC experience while retaining CampusMate as the sole identity and data authority.

**Architecture:** A verified, repository-owned Node 22.19+ service hosts OpenMAIC runtime capabilities; FastAPI is the authenticated course-context and session gateway; React 18 implements native routes without a whole-app iframe.

**Tech Stack:** React 18/Vite, FastAPI, managed Node/Next runtime, existing CampusMate repositories and tests.

**Spec:** `docs/superpowers/specs/2026-09-18-openmaic-campus-fusion-design.md`

## Global constraints

- Do not copy from the unversioned reference until the canonical source decision is approved.
- Do not change CampusMate schema or deployment before explicit approval.
- No React-major upgrade, second login, static course data, whole-app iframe, client-held provider key, or reference-path runtime dependency.
- Every implementation behavior starts with a failing test, passes relevant tests/build, and is committed separately.

## Review-revision execution contract

Every task below starts with the named failing test, then implements the named interface, runs the exact command with exit code 0, and commits only its listed paths. `openmaic-service/` is not created until the official v1.0.3 baseline is locally available and the diff gate in the spec records each copied file. Provider calls use a contract fake; real-provider E2E is a final, explicitly external acceptance step.

| Task | Files / interface | Failing test → implementation → command / expected result |
| --- | --- | --- |
| 1 Source diff | create `docs/openmaic-v1.0.3-local-diff.md`, `scripts/openmaic-diff.ps1` | test script rejects missing official SHA → compare official/local and reject `local-different` copy → `pwsh scripts/openmaic-diff.ps1`; exit 0, manifest complete |
| 2 Service health | `openmaic-service/app/api/health/route.ts`; `backend/app/services/openmaic/openmaic_service_client.py` `health() -> Health` | fake contract test expects `status/capabilities/version` → health implementation → `cd backend; pytest tests/test_openmaic_service_contract.py -q`; pass |
| 3 Course bridge | `stage_bridge.py` `resolve(user, course)->StageBinding` | foreign course and raw courseId-as-stageId fail → opaque mapping implementation → `pytest backend/tests/test_openmaic_stage_bridge.py -q`; pass |
| 4 Home | `OpenMaicHomePage.jsx`, `openmaic_fusion.py` `GET /courses/openmaic-home` | legacy grid absence and real rail states fail → native home/search/folders/recent → `cd webreact; npm test -- openmaic-home`; pass |
| 5 Workbench | `webreact/src/pages/OpenMaicWorkbenchPage.jsx`, `backend/app/services/openmaic/openmaic_sessions.py` `create_session()` | session lacks bound course fails → native panes/session create → `cd backend; pytest tests/test_openmaic_workbench.py -q`; then `cd webreact; npm test -- openmaic-workbench`; both pass |
| 6 Session flow | `webreact/src/hooks/useOpenMaicSession.js`, `backend/app/services/openmaic/openmaic_stream.py` `stream(session_id)` | switch-course stale chunk and refresh restore fail → SSE/retry/cancel/recovery → `cd backend; pytest tests/test_openmaic_session_flow.py -q`; then `cd webreact; npm test -- openmaic-session`; pass |
| 7 Editor | `OpenMaicEditorPage.jsx`, service `/api/stages/:id` facade | non-owner update fails → editor document bridge → editor contract/Web tests; pass |
| 8 Player | `OpenMaicPlayerPage.jsx`, `openmaic_player.py` | untrusted media origin fails → scenes/player/URL policy → player tests; pass |
| 9 Materials | `MaterialPanel.jsx`, `openmaic_materials.py` | foreign/oversize material fails → upload/extract facade → material tests; pass |
| 10 Import | service importer facade, `ImportDialog.jsx` | invalid MIME/zip fails → PPTX/MD/DOCX import → import fixtures; pass |
| 11 Export | service exporter facade, `ExportMenu.jsx` | cross-owner export fails → zip/PPTX/MD/DOCX export → export fixtures; pass |
| 12 Modes | `GenerationModePanel.jsx`, `generation_facade.py` | each requested mode unreported fails → slide/quiz/interactive/PBL/simulation/diagram/code/game/3D/procedural registry → `pytest backend/tests/test_openmaic_generation_modes.py -q`; pass |
| 13 Whiteboard | `WhiteboardPanel.jsx`, document facade | cross-session board leak fails → persisted board bridge → whiteboard tests; pass |
| 14 TTS | `TtsControls.jsx`, `tts_proxy.py` | redirect/private-IP provider URL fails → proxied TTS → TTS policy tests; pass |
| 15 Multi-agent | `AgentToolPanel.jsx`, tool facade | unapproved tool/course leak fails → allowlisted tools/search/PBL stream → tool ACL tests; pass |
| 16 Settings | admin page, `openmaic_settings.py` | student provider edit/secret response fails → admin health/capability settings → settings tests; pass |
| 17 Persistence | service store, mapping facade | user/course isolation and restore fail → durable mapping/session lifecycle → persistence tests; pass |
| 18 Course/task entry | `CourseDetailPage.jsx`, `TaskDetailPage.jsx`, explain route | submission/answer data enters prompt or no confirmation fails → preview/explain/deep-link → assignment tests; pass |
| 19 Acceptance | all changed paths | outage/keyboard/320–1440 tests fail → no production changes → backend pytest, `npm test`, `npm run build`; pass; real Provider E2E marked pending credentials |

### Task 1: Establish the approved managed-service source

**Files:** create `openmaic-service/`, `docs/openmaic-attribution.md`, service tests.

- [ ] Record the approved upstream commit, MIT notice, dependency license inventory, Node 22.19+ requirement, reproducible install/build commands and excluded assets.
- [ ] Write a failing health-contract test requiring `{status, capabilities, version}` without secrets.
- [ ] Implement only the authenticated health endpoint and run its test.
- [ ] Commit the isolated service foundation after approval.

### Task 2: Build the FastAPI service contract and opaque mapping

**Files:** modify `backend/app/services/openmaic/*`, schemas/routes/config; add focused pytest files.

- [ ] Write failing tests proving a foreign user/course gets 403/404 and a CampusMate course ID is never forwarded as `stageId`.
- [ ] Implement server-side opaque mapping, signed service assertion, health timeout/error mapping and cancellation.
- [ ] Run focused pytest and commit.

### Task 3: Replace the `/courses` page natively

**Files:** modify the actual `/courses` route/page and styles; add Web tests.

- [ ] Write failing tests that reject the legacy grid and require real-course loading/error/empty/retry states in a responsive course rail.
- [ ] Implement the OpenMAIC home layout (generation, recent, folders, search, import) plus native course rail, preserving original functional arrangement.
- [ ] Run Web tests/build and commit.

### Task 4: Add workbench chat and course session recovery

**Files:** native React workbench routes/components, FastAPI session/message endpoints, tests.

- [ ] Write failing tests for bound course context, stale-response discard on switch, refresh restore, and retained draft on error.
- [ ] Implement streaming/resume/retry with current-course labelling and safe exit/switch controls.
- [ ] Verify backend/Web tests, browser interaction and commit.

### Task 5: Add assignment explanation safely

**Files:** `TaskDetailPage`, related API client, FastAPI assignment-context endpoint, tests.

- [ ] Write failing tests covering assignment/course IDs, context preview/confirmation, excluded submission/answer data and service-outage preservation of task page behavior.
- [ ] Implement explain/steps/classroom dispatch with a deep link to the native session/player and no submission side effects.
- [ ] Verify focused tests/build/browser flow and commit.

### Task 6: Migrate every audited OpenMAIC capability

**Files:** approved service modules, native editor/player/import/export routes, FastAPI contract tests and Web tests.

- [ ] For each matrix row, write its failing reachability/authorization test before implementation.
- [ ] Migrate native workbench/editor/player, imports/exports, materials, all generation modes, media and settings in independently tested commits.
- [ ] Update the matrix only with test and browser evidence; no enabled control may lack a live implementation.

### Task 7: Final safety and acceptance

**Files:** deployment/env examples, capability matrix, test artifacts excluded from Git.

- [ ] Run backend pytest, service tests, `npm test`, `npm run build`, and authenticated browser checks at 320/768/1024/1440px against the approved real service.
- [ ] Scan staged changes for credentials, absolute paths, reference artifacts and unintended platform changes.
- [ ] Review `git diff`, `git diff --cached`, and `git status --short`; commit only this task's files.

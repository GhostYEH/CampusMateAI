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

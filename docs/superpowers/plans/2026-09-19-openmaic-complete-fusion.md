# OpenMAIC Complete Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the remaining CampusMate-owned OpenMAIC capabilities on top of the existing authenticated, persisted DSL/workspace baseline.

**Architecture:** Keep FastAPI as the authorization/context gateway and the Node service as the isolated OpenMAIC runtime. Add bounded, capability-advertised job/artifact contracts, then connect them to the existing React 18 workbench and assignment/course flows.

**Tech Stack:** Node 24 native TypeScript stripping, Node SQLite, FastAPI/Pydantic, React 18/Vite, existing zero-dependency archive and DSL utilities.

**Spec:** `docs/superpowers/specs/2026-09-19-openmaic-complete-fusion-design.md`

## Global Constraints

- CampusMate JWT is the only user identity and FastAPI is the only browser-facing gateway.
- Provider keys never enter browser code, API responses, database正文, snapshots, or logs.
- Node service assertions are short-lived, course-bound, single-use, and persisted.
- Unknown capabilities, DSL fields, future versions, and scene types fail explicitly.
- No static fake answers, dead buttons, whole-site iframe, React-major-version change, or unrelated platform changes.
- All writes use idempotency and conditional revision checks where applicable.

---

### Task 1: Establish the truthful artifact/job contract

**Files:**
- Create: `openmaic-service/src/jobs/*`, `openmaic-service/src/artifacts/*`
- Modify: `openmaic-service/src/db/migrations.ts`, `openmaic-service/src/main.ts`, `openmaic-service/src/capabilities.ts`
- Test: `openmaic-service/tests/jobs.test.mjs`, `openmaic-service/tests/capabilities.test.mjs`

**Steps:**

- [ ] Write failing tests for idempotent job creation, ownership, progress, retry, cancellation, expiry, and redacted artifacts.
- [ ] Run the focused Node tests and confirm the failures describe missing behavior.
- [ ] Implement bounded SQLite job/artifact records and deterministic state transitions.
- [ ] Add capability names only for mounted handlers and provider-safe redaction.
- [ ] Run focused tests, typecheck, and commit `feat(openmaic): persist truthful generation and artifact jobs`.

### Task 2: Add generation, whiteboard, TTS, and discussion handlers

**Files:**
- Create: `openmaic-service/src/generation/*`, `openmaic-service/src/whiteboard/*`, `openmaic-service/src/tts/*`, `openmaic-service/src/discussion/*`
- Modify: `openmaic-service/src/main.ts`
- Test: `openmaic-service/tests/generation.test.mjs`, `openmaic-service/tests/whiteboard.test.mjs`, `openmaic-service/tests/tts.test.mjs`, `openmaic-service/tests/discussion.test.mjs`

**Steps:**

- [ ] Write contract tests for every supported mode and unavailable-provider degradation.
- [ ] Implement handlers using the existing validated Stage/Scene DSL and course/material authorization.
- [ ] Ensure generated results are read back from persisted Stage/Scene content before returning.
- [ ] Verify no provider secret or raw upstream error crosses the boundary; commit.

### Task 3: Implement multi-format import/export

**Files:**
- Create: `openmaic-service/src/importers/pptx.ts`, `openmaic-service/src/exporters/markdown.ts`, `openmaic-service/src/exporters/docx.ts`, `openmaic-service/src/exporters/pptx.ts`
- Modify: `openmaic-service/src/archive/*`, `openmaic-service/src/main.ts`
- Test: `openmaic-service/tests/import-export-formats.test.mjs`

**Steps:**

- [ ] Write failing tests for bounded PPTX parsing, malformed-page degradation, sanitized filenames, and all requested export formats.
- [ ] Implement only the supported structural subset with explicit errors for unsupported content.
- [ ] Reuse existing archive ownership and short-lived artifact download rules.
- [ ] Run focused and full Node suites; commit.

### Task 4: Connect FastAPI gateway contracts

**Files:**
- Create: `backend/app/api/routes/openmaic_generation.py`, `backend/app/api/routes/openmaic_settings.py`, `backend/app/api/routes/openmaic_explanations.py`
- Modify: `backend/app/api/router.py`, `backend/app/services/openmaic/fusion_client.py`, `backend/app/schemas/openmaic_fusion.py`
- Test: corresponding `backend/tests/test_openmaic_*.py`

**Steps:**

- [ ] Write failing tests for status/capability filtering, course-bound quick ask/session recovery, assignment context confirmation, and ownership-safe artifact downloads.
- [ ] Implement JWT/course checks before internal calls and stable redacted error mapping.
- [ ] Verify closed/read-only/graded assignments remain explainable without changing submission permissions.
- [ ] Run the OpenMAIC pytest subset; commit.

### Task 5: Complete the native React workbench flows

**Files:**
- Modify: `webreact/src/components/openmaic/*`, `webreact/src/pages/ParityPages.jsx`, `webreact/src/pages/TaskDetailPage.jsx`, `webreact/src/data/api.js`
- Test: `webreact/tests/openmaic-*.test.mjs`, new generation/explanation tests

**Steps:**

- [ ] Write failing behavior tests for capability-gated actions, job polling/retry/cancel, session epoch guards, export/download states, and assignment confirmation gate.
- [ ] Implement native panels and accessible states using the existing React 18 shell.
- [ ] Add keyboard/reduced-motion behavior and remove any newly dead controls.
- [ ] Run focused tests and Web build; commit.

### Task 6: Security and browser acceptance closeout

**Files:**
- Modify: `docs/openmaic-capability-matrix.md`, `docs/openmaic-deployment.md`, `docs/openmaic-student-integration-design.md`
- Test: Node, backend, Web, and browser acceptance scripts/fixtures

**Steps:**

- [ ] Run complete Node test/typecheck/build and record exact counts.
- [ ] Repair/use a repository-local Python environment and run all OpenMAIC pytest tests.
- [ ] Run Web test/build and browser acceptance at 320/768/1024/1440 where tooling is available.
- [ ] Review staged diff/status for secrets, host paths, artifacts, and user changes.
- [ ] Commit documentation/evidence and merge the feature branch to master without overwriting user assets.

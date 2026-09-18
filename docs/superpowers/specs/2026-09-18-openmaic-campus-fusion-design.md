# OpenMAIC–CampusMateAI Fusion Design

**Status:** revised for independent review; implementation is intentionally paused.

> **2026-09-18 review revision:** source provenance and managed-runtime approval are now resolved. This specification remains in review; no source migration begins until this revised matrix and plan are approved.

## Approved source and local-reference diff gate

Formal source: `https://github.com/THU-MAIC/OpenMAIC.git`, tag `v1.0.3`, commit `e693e11a81644f84c258df73dbda378643520a62`. GitHub identifies it as the signed v1.0.3 security release. The local `F:` tree is visual/reference-only. Its observed `package.json` says `1.0.1` and Next `16.2.11`; v1.0.3 includes security fixes and Next `16.3.3`, so it is not a safe substitute.

Before copying each file, run `git diff --no-index --name-status <official-v1.0.3> <local-reference>` and record one of `identical`, `official-only`, or `local-different`. The official baseline could not be cloned in this environment (terminal GitHub connection failure), so this is the current checked-in diff checklist, not a fabricated file diff:

| Area | Local observation | disposition |
| --- | --- | --- |
| `package.json`, `CHANGELOG.md` | local identifies as 1.0.1 | local-different; do not copy |
| access-code, render-service, TTS/network guards | v1.0.3 release supplies security fixes | official-only until baseline checkout is available |
| `app/`, `components/`, `lib/`, `packages/`, `tests/` | present locally but provenance unverified | compare before every candidate migration |
| `.env.local`, `node_modules`, `.next`, `data`, `.workbuddy-ai` | present locally | forbidden input |

## React/runtime boundary

`webreact/` remains React 18/Vite. Native CampusMate UI is implemented only in `webreact/src/pages/OpenMaicHomePage.jsx`, `OpenMaicWorkbenchPage.jsx`, `OpenMaicEditorPage.jsx`, `OpenMaicPlayerPage.jsx` and focused `components/openmaic/*.jsx`; it consumes FastAPI JSON/SSE and never imports a React-19 component, Next route, or `@openmaic/*` UI package.

The repository-owned Node 22.19+ `openmaic-service/` contains the verified v1.0.3 Next/React-19 runtime, server APIs, importer/exporter, renderer, editor and provider adapters. FastAPI is its only CampusMate-facing gateway. It receives a short-lived service assertion and opaque `{ownerId, campusCourseId, stageId}` mapping; it cannot render an independent product root or login. Only individual generated interactive widgets may use a cross-origin sandboxed iframe. Workbench, editor, player and homepage are native CampusMate routes.

## Per-capability migration matrix

`S` = formal source/API; `T` = CampusMate target; `A` = authorization/data rule; `V` = required test and acceptance command. All are **planned**, not migrated.

| Capability | S | T | A | V | Status |
| --- | --- | --- | --- | --- | --- |
| Home/recent/folders/search | `components/workbench/workspace/WorkspaceHome.tsx`; `/api/stages` | `webreact/src/pages/OpenMaicHomePage.jsx`; `backend/app/api/routes/openmaic_fusion.py` | FastAPI lists only owned mappings; Campus courses stay source of truth | `webreact/tests/openmaic-home.test.mjs`; `npm test -- openmaic-home` | planned |
| Course bridge/stage mapping | `/api/stages`, `lib/workbench/course-refs.ts` | `backend/app/services/openmaic/stage_bridge.py` | opaque stageId, ACL before every read/write | `backend/tests/test_openmaic_stage_bridge.py`; `pytest ... -q` | planned |
| Workbench/chats | `WorkspaceShell.tsx`, `/api/agent/sessions/*` | `OpenMaicWorkbenchPage.jsx`, `openmaic_sessions.py` | service assertion binds user+course+session | `test_openmaic_workbench.py`; `openmaic-workbench.test.mjs` | planned |
| Streaming/resume/cancel/retry | `/events`, `/messages`; `use-workbench-session.ts` | `openmaic_stream.py`, `useOpenMaicSession.js` | stale course/session output discarded | backend/Web session tests | planned |
| Editor | `packages/@openmaic/editor/**` | service editor API; `OpenMaicEditorPage.jsx` | owner mapping, no direct React19 import | editor contract/Web route tests | planned |
| Player/scenes/media | `/api/stages/[id]/scenes`, renderer | `OpenMaicPlayerPage.jsx`, `openmaic_player.py` | signed resource URLs, trusted origin only | player policy/Web tests | planned |
| Materials/upload/extraction | `/api/materials`, importer | `openmaic_materials.py`, `MaterialPanel.jsx` | Campus material ACL/type/size; no private files | material ACL tests | planned |
| PPTX/Markdown/DOCX import | importer packages/routes | service import facade | server scan/limits/ownership | import fixture contract tests | planned |
| `.maic.zip` + PPTX/MD/DOCX export | exporter routes/packages | service export facade | session owner and content-disposition | export fixture tests | planned |
| Classroom generation/poll | `/api/generate-classroom/*` | existing classroom service + fusion facade | confirmation, idempotency, provider keys server-only | `test_openmaic_generation_modes.py` | planned |
| slide/quiz/interactive/PBL/simulation | generation, quiz, PBL routes | `GenerationModePanel.jsx`, mode facade | mode capability and course ACL | mode matrix tests | planned |
| diagram/code/game/3D/procedural skill | renderer/generation skills | player widgets + capability registry | safe widget URL/sandbox/capability gate | widget security tests | planned |
| Whiteboard | `components/whiteboard/**`, `lib/whiteboard/**` | `WhiteboardPanel.jsx`, service document API | session owner, sanitized persisted document | whiteboard persistence tests | planned |
| TTS/voice | `lib/workbench/tts-stage-sync.ts`, transcription routes | `tts_proxy.py`, `TtsControls.jsx` | provider key server-only; redirect/DNS policy | TTS URL-policy tests | planned |
| Multi-agent/web search | agent/PBL routes, `lib/web-search/**` | service tool facade, workbench cards | tool allowlist, SSRF guard, course context | tool authorization tests | planned |
| Settings/providers/health | `/api/health`, `/api/provider/*` | `openmaic_settings.py`, admin setting page | admin-only config; health redacts secrets | health/provider contract tests | planned |
| Persistence/isolation | stages/material/session APIs | service store + FastAPI mapping facade | `{user,course,stage,session}` enforced on every operation | cross-user/course tests | planned |
| Course detail/task explain | existing course/task pages | `CourseDetailPage.jsx`, `TaskDetailPage.jsx`, explain endpoint | no submissions/answers/private teacher data; confirmation | assignment-context tests | planned |

## Goal and non-goals

CampusMateAI remains the only shell, account system, course-data authority, and authorization gateway. OpenMAIC capabilities are made reachable inside CampusMate routes, without a whole-app iframe, second sign-in, or a runtime dependency on the reference directory. This design does not approve copying an unversioned reference tree or exposing an incomplete button as a feature.

## Audit evidence

CampusMate currently has a FastAPI adapter at `backend/app/services/openmaic/` and `/api/v1/courses/{course_id}/interactive-classroom/*`. It server-builds an authorized, bounded course context; stores sessions per user/course; performs idempotent generation and polling; and the Web course-detail panel can list/generate/embed a classroom. It does **not** provide an OpenMAIC home/workbench/editor/player/import-export runtime, nor does `/courses` replace its legacy course grid.

The supplied reference is not a Git worktree (`git -C <reference> rev-parse --is-inside-work-tree` fails). It contains 86 `app`, 365 `components`, 1,741 `packages`, and 725 `tests` files, requires Node `>=22.19.0`, Next 16.2.11 and React 19.2.3; CampusMate Web is React 18/Vite. Its root LICENSE is MIT © 2026 THU-MAIC, but the tree also bundles/transpiles `mathml2omml`, uses GSAP, and has no verified source revision from which attribution and third-party distribution obligations can be established.

## Architecture selected for approval

Add an internally managed `openmaic-service/` under this repository, pinned to a verified upstream source/revision and Node 22.19+. It owns only OpenMAIC rendering, workbench, editor, player, import/export, generation-provider integration and its own persistence. It is not a public product home and must accept a short-lived CampusMate-issued service assertion; it never presents an OpenMAIC login.

`webreact/` renders native CampusMate route components and calls FastAPI only. FastAPI authenticates the CampusMate JWT, checks course/assignment access, redacts and bounds context, creates or resumes an internal OpenMAIC session mapping, and proxies only contract-defined service calls with timeout/error conversion. An isolated iframe is permitted only for an individual untrusted interactive widget using a restrictive sandbox; it is not used for the workbench, editor, player, or homepage.

```text
CampusMate React routes -> FastAPI JWT/course gate -> managed OpenMAIC service
                         |                         |
                         +-> CampusMate course data +-> OpenMAIC session/content store
```

The mapping key is a server-issued opaque OpenMAIC `stageId` stored with `{campus_user_id, campus_course_id}` in the managed service. A CampusMate `courseId` is never sent as, or masquerades as, a stage ID. Assignment explain requests are an additional scoped context attached to the server-created session and exclude submissions, answers, peers, and private instructor material.

## Context, safety, and recovery

FastAPI derives course name/code/term, instructor, authorized chapters/knowledge points/material metadata, announcements, exams, assignments and the requesting student's progress. It caps text, redacts credentials/cookies/tokens, filters objects by current user and course, and declares source/truncation warnings. Each message and generation request carries the opaque session plus server-verified course binding; stale requests are cancelled/discarded when course changes. The UI preserves drafts on failure and clearly identifies the current course.

Generate is confirmation-gated after a context preview. OpenMAIC outages return an actionable unavailable state and cannot impair ordinary course pages, assignment viewing, drafts, or submission rules. Service health, capability discovery, URL-origin validation, upload limits, SSRF controls, HTML sanitization, idempotency, request cancellation and user/course isolation are required before exposure.

## Capability matrix

| Reference capability group | Current CampusMate evidence | Required destination | Data/permission authority | Status |
| --- | --- | --- | --- | --- |
| Home, recent items, folders, search, import | No `/courses` fusion implementation | Native React OpenMAIC home + course rail | FastAPI course read access | Blocked |
| Course/stage creation, workbench, agent chat, streaming, resume/retry, course refs | Classroom generation adapter only | Managed service + FastAPI session bridge | JWT + opaque mapping | Blocked |
| Materials/upload/extraction/web search | Bounded material selection for generation | Managed service endpoints behind FastAPI | Course material ACL, file/type/SSRF policy | Blocked |
| Generate/poll: slide, quiz, interactive, PBL, simulation, diagram, code, game, 3D, procedural skill, whiteboard, TTS, multi-agent | Existing adapter covers selected classroom generation/poll only | Managed service capability registry and player | Course context and provider keys server-side | Blocked |
| Editor, player, scene switching, media | External classroom embed panel only | Native React routes / safe widget sandbox | Session ownership check | Blocked |
| PPTX/Markdown/DOCX and `.maic.zip` import/export | No verified integration | Managed service import/export bridge | Session/content ownership check | Blocked |
| Settings, provider configuration, health, persistence, public API tests | Partial FastAPI health/config/session store | Admin-only service config, health contract, service persistence | CampusMate admin/JWT boundary | Blocked |
| Course detail quick ask/history and assignment explanation | Classroom panel exists; no required task explanation flow | Native React detail/task actions and FastAPI endpoints | Course/assignment ACL | Blocked |

No row is marked migrated: the current adapter is useful integration groundwork, not evidence of the requested complete migration.

## Migration and rollback

Keep current OpenMAIC endpoints disabled by default. Add new routes behind `OPENMAIC_FUSION_ENABLED=false`; release only after the managed service is healthy and all matrix tests pass. Rollback disables the flag and leaves CampusMate course/task flows intact. No CampusMate database schema change is assumed until the service persistence decision is approved; if CampusMate must own the mapping, supply a migration and rollback for review first.

## Verification contract

Tests must cover 401/403/404, cross-user/course isolation, redaction, stale-course cancellation, session restore, confirmation gating, trusted URLs, outage degradation, all reachable capability entries and desktop/mobile keyboard behavior. Required final evidence includes backend pytest, Web tests/build, managed-service tests, and authenticated browser flows at 320/768/1024/1440px with a real provisioned provider.

## Blocking decisions requiring user approval

1. **Canonical source and licensing:** provide the official Git remote plus immutable commit/tag (or a signed source archive) and approve third-party distribution review for the managed service. The local reference is not a Git repository, so its untracked provenance cannot legally be used as the formal migration source.
2. **Production/runtime change:** approve adding and operating the repository-owned Node 22.19+ managed service, its persistent store, health endpoint and deployment/start configuration. This is a production-deployment change explicitly called out as a pause condition.
3. **Credentials and real verification:** provide a non-production OpenMAIC/provider configuration and CampusMate test account/course. Without it, real generation, streaming, import/export and browser end-to-end acceptance cannot be truthfully verified.

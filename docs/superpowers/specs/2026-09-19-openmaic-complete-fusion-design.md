# OpenMAIC Complete CampusMate Fusion Design

## Scope

This design completes the approved CampusMate-owned OpenMAIC fusion boundary
from the existing branch baseline. The web client remains the only browser
product shell; FastAPI remains the only identity, course, assignment, material,
and authorization gateway; and the Node service owns workspace/stage content,
background artifact jobs, and its own SQLite persistence.

The existing DSL, assertion middleware, workspace/editor/player contracts,
material extraction, folder/search discovery, and `.maic.zip` archive are kept
as the foundation. The remaining capabilities are added as small service
contracts with explicit capability advertisement so the UI never exposes an
unimplemented action.

## Architecture

- FastAPI verifies CampusMate JWT and course/resource access, then mints a
  single-use short-lived internal assertion for Node calls.
- Node validates all external JSON against the versioned DSL, persists jobs and
  idempotency/replay state in its own database, and returns redacted status and
  artifact metadata only.
- Artifact producers are deterministic where no Provider is configured: they
  return a truthful degraded result or a local, structurally valid export; they
  never fabricate provider output or expose keys.
- Web routes use the existing React 18 shell and request guards. Context
  changes invalidate in-flight work so stale responses cannot write to a new
  user/course/workspace.

## Delivery slices

1. Add a job/artifact contract covering generation modes, whiteboard, TTS,
   multi-agent discussion, provider-safe capabilities, and export formats.
2. Add PPTX/Markdown/DOCX exporters and a constrained PPTX importer; keep
   `.maic.zip` atomic and subject to existing zip-slip limits.
3. Add FastAPI gateway endpoints for generation, artifact polling/download,
   provider settings, course-bound quick ask/session resume, and assignment
   explanation confirmation.
4. Add native workbench panels for generation, whiteboard, TTS, discussion,
   exports, provider settings, and resilient loading/error states.
5. Add regression tests, browser checks at 320/768/1024/1440, and update the
   capability matrix/deployment evidence.

## Security and failure handling

Provider keys stay in server environment configuration. Artifact downloads are
short-lived and ownership checked. Uploaded/imported content is bounded,
sanitized, and tied to user/course/workspace. Unsupported scene types render an
explicit degraded state. Provider or render-service outages preserve course and
assignment pages and expose retryable errors rather than fake content.

## Verification

Every slice follows red-green-refactor: add a behavior test, run it to observe
the expected failure, implement the smallest behavior, then run the focused
tests and affected Node/Python/Web suites. Before merging, run the complete
available suites, inspect staged diffs for credentials and host paths, and
record any unavailable external-provider or browser checks as explicit risks.

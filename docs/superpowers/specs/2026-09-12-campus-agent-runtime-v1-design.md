# CampusMateAI Agent Architecture v1.0

**Status:** Frozen design approved on 2026-09-12

**Scope:** CampusAgentRuntime foundation plus final-review planning, course research/homework assistance, and notice-to-workflow automation

**Clients:** Android, HarmonyOS, and React Web
**Delivery order:** Runtime foundation, final review, course research, notice workflow, then integrated verification and demo data

## 1. Purpose

CampusMateAI will add a small, domain-controlled Agent Runtime that turns existing learner state, course data, tasks, knowledge retrieval, and model integrations into auditable workflows. The runtime is not a general-purpose autonomous computer-use framework. It exists to support three verified student scenarios:

1. Create a versioned final-exam review campaign and adapt it through daily follow-up.
2. Research course questions and assist with coursework under explicit academic-policy limits.
3. Turn campus notices into safe, trackable workflows without silently performing external high-risk actions.

The design borrows control-plane ideas from EvoFlow—jobs, runs, steps, approvals, events, artifacts, recovery, and logical agent roles—but does not copy or embed EvoFlow source code. This avoids coupling CampusMateAI to EvoFlow's Python 3.12/LangGraph/Tauri stack and its PolyForm Noncommercial license.

## 2. Goals

- Keep all domain truth and authorization in the existing FastAPI backend.
- Give Android, HarmonyOS, and Web one stable API contract and one authoritative state.
- Route real model work through the repository's OpenAI-compatible client with direct Zhipu and Xunfei provider configurations.
- Prevent models from directly accessing databases or executing arbitrary actions.
- Persist runs, approvals, events, model/tool traces, plan versions, citations, and artifacts for recovery and evaluation.
- Support deterministic fallback, partial results, and explicit uncertainty.
- Preserve scientific and privacy boundaries around learner state, behavior recognition, and academic integrity.
- Produce architecture and metrics that can support a paper or competition demonstration without contaminating real user data.

## 3. Non-goals

- Embedding EvoFlow, LangGraph, a generic agent marketplace, or user-uploaded executable agents.
- Running six independent agent processes in v1.
- Providing arbitrary SQL, arbitrary shell/code execution, or unrestricted URL-fetch tools.
- Automatically logging into school systems, bypassing verification codes, paying fees, submitting assignments, or impersonating students.
- Storing complete prompts, hidden reasoning, raw model responses, school credentials, raw camera data, or complete homework answers as long-term memory.
- Implementing a general multi-tenant platform. Demo isolation uses a dedicated seeded demo user in development/test only.
- Requiring vector memory, Kafka, Redis, or a new external worker system for v1.

## 4. Architecture

```text
Android             HarmonyOS              Web
   \                    |                   /
    +------------- API Contract ------------+
                       |
                    FastAPI
                       |
             CampusAgentRuntime
   +------------------------------------------------+
   | ContextManager       MemoryManager              |
   | ModelRouter          AgentRegistry              |
   | ToolRegistry         RiskEngine                 |
   | ApprovalGate         RunManager                 |
   | AgentEventStore      ArtifactManager            |
   +------------------------------------------------+
                       |
                Domain Services
          +------------+-------------+
          |            |             |
     Final Review  Course Research  Notice Workflow
                       |
        Existing CampusMateAI repositories/services
```

The clients request work, display state, collect decisions, and schedule platform notifications. They do not calculate risk, academic policy, plan adjustments, or domain state. Domain decisions remain on the backend.

## 5. Runtime components

### 5.1 ContextManager

`ContextManager` builds immutable, bounded `ContextSnapshot` values from server-owned data. It composes the existing learner-state projection, knowledge state, courses, exams, personal tasks, focus sessions, study check-ins, and user-confirmed preferences.

A snapshot contains:

```json
{
  "snapshot_id": "ctx_xxx",
  "scope": {
    "user_id": "current-user",
    "course_ids": ["course_x"],
    "campaign_id": "campaign_x"
  },
  "facts": {
    "exams": [],
    "pending_tasks": [],
    "daily_capacity_minutes": 120,
    "knowledge_state": [],
    "confirmed_preferences": []
  },
  "source_refs": [],
  "source_digest": "sha256...",
  "generated_at": "2026-09-12T10:00:00+08:00",
  "valid_until": "2026-09-12T10:15:00+08:00"
}
```

Rules:

- Every source is checked against the current authenticated user's access.
- Each source type has row, character, and time limits.
- Logs store the snapshot ID, safe source types, and digests, not raw sensitive content.
- An expired snapshot may be rebuilt for read-only work. A write based on an expired snapshot is stopped and re-planned.
- Observable behavior and expression signals are supporting evidence only; they are never treated as direct proof of attention, learning quality, mental state, or academic outcome.

### 5.2 MemoryManager

The v1 memory allowlist is:

- `CONFIRMED_PREFERENCE`
- `CONFIRMED_STUDY_GOAL`
- `CONFIRMED_CONSTRAINT`
- `USER_APPROVED_SUMMARY`

Memory records include provenance, confirmation state, confidence, sensitivity, validity, withdrawal state, and whether a model may consume the record. The runtime does not store full conversations, full assignment answers, raw notice content, psychological inferences, or camera data as memory. Vector embeddings are deferred until there is a verified retrieval need, and then apply only to confirmed low-sensitivity summaries.

Users can view, withdraw, and clear runtime memory through the existing learner-data controls.

### 5.3 AgentRegistry

Agents are reusable logical roles described by code-owned, versioned metadata:

```json
{
  "agent_code": "planner",
  "version": "1.0",
  "capabilities": ["plan.generate", "schedule.adapt"],
  "tools": ["course.read", "exam.read", "plan.propose"],
  "model_policy": "reasoning_primary",
  "permission_policy": "student_owned_only"
}
```

Initial roles are `planner`, `analyzer`, `notice_interpreter`, `workflow_planner`, `coordinator`, `course_researcher`, `web_researcher`, `citation_verifier`, `tutor`, `critic`, and `synthesizer`.

In v1, one `AgentExecutor` runs these roles as versioned stages. Research roles may fan out bounded retrieval calls, but there are no independent agent processes or recursive delegation.

### 5.4 ToolRegistry

Tools are registered by resource and action, not only by broad READ/WRITE classes. Initial capabilities include:

```text
student.read
course.read
exam.read
schedule.read
learner_state.read
knowledge.search
task.propose
task.create
task.update
plan.propose
plan.activate
reminder.schedule
research.source.fetch
research.report.create
external_submission.prepare
```

Before a tool executes, the runtime verifies:

1. The role declares the tool.
2. The job/run grants the capability.
3. The resource belongs to the authenticated user or is explicitly accessible.
4. The arguments satisfy the tool's Pydantic schema and size limits.
5. The RiskEngine and ApprovalGate allow the action.
6. The idempotency key has not already completed.

No v1 tool exposes arbitrary SQL, bulk deletion, arbitrary file paths, arbitrary code execution, or unrestricted URL access.

### 5.5 RiskEngine and ApprovalGate

Risk evaluation is a shared runtime service used by all three domains. Actions are classified as:

- `AUTO_SAFE`: internal, reversible or idempotent actions explicitly enabled by the user.
- `CONFIRM_REQUIRED`: actions that change plans, messages, schedules, or external-action drafts.
- `MANUAL_ONLY`: authentication, CAPTCHA, payment, formal registration, assignment submission, or external school-system mutation.

`ApprovalGate` creates an expiring approval record for actions that require confirmation. Expiration never implies approval. Production builds cannot auto-approve high-risk actions.

### 5.6 RunManager and recovery

The persistent hierarchy is:

```text
agent_job          reusable long-lived objective
  +-- agent_run    one execution attempt
        +-- agent_run_step
```

Run status is one of:

```text
QUEUED
RUNNING
AWAITING_APPROVAL
SUCCEEDED
PARTIAL
FAILED
CANCELLED
```

The current phase is separate:

```text
CONTEXT_BUILDING
WAITING_FOR_MODEL
VALIDATING_OUTPUT
WAITING_FOR_TOOL
WAITING_FOR_APPROVAL
PERSISTING_RESULT
RECOVERY_CHECKING
IDLE
```

After process restart, incomplete runs enter `RECOVERY_CHECKING`. The runtime checks persisted tool records and authoritative domain rows before resuming. An ambiguous write is not blindly replayed.

Cancellation prevents future work. Completed internal actions remain recorded and are only undone through an explicit, supported compensating action.

### 5.7 Event store

`agent_events` is a transactional event table and lightweight outbox, not Kafka. Business state and the corresponding event are committed in the same database transaction.

The existing `learner_events` table remains the source of learner evidence. Agent lifecycle events stay in `agent_events`; a domain service explicitly bridges relevant completed actions into learner evidence.

The SSE event contract is:

```json
{
  "id": "evt_10001",
  "type": "TOOL_COMPLETED",
  "run_id": "run_xxx",
  "sequence": 18,
  "status": "RUNNING",
  "phase": "WAITING_FOR_TOOL",
  "role": "planner",
  "summary": "已完成课程信息查询",
  "progress": {
    "current": 3,
    "total": 7,
    "percent": 42
  },
  "artifact_id": null,
  "approval_id": null,
  "created_at": "2026-09-12T10:00:00+08:00"
}
```

Initial event types are:

```text
RUN_QUEUED
RUN_STARTED
CONTEXT_READY
MODEL_STARTED
MODEL_COMPLETED
MODEL_FALLBACK
TOOL_STARTED
TOOL_COMPLETED
TOOL_FAILED
APPROVAL_REQUIRED
APPROVAL_RESOLVED
ARTIFACT_CREATED
RUN_PARTIAL
RUN_COMPLETED
RUN_FAILED
RUN_CANCELLED
```

`GET /events/stream` accepts `Last-Event-ID`. Disconnecting a client does not cancel the run. Public events never contain prompts, hidden reasoning, complete model responses, credentials, or sensitive tool parameters.

### 5.8 Tool and model trace records

`agent_tool_calls` contains:

```text
id
run_id
step_id
tool_name
idempotency_key
request_hash
status
started_at
finished_at
result_digest
error_code
```

It stores hashes and safe summaries, not complete sensitive arguments or results. It is the basis for retry decisions, recovery, idempotency, and audit.

`agent_model_calls` contains:

```text
id
run_id
step_id
provider
route_policy
model
status
latency_ms
fallback_reason
started_at
finished_at
```

It does not store full prompts, user context, hidden reasoning, or raw provider responses.

### 5.9 ArtifactManager

Artifact types are:

- `FINAL_REVIEW_PLAN`
- `DAILY_AGENDA`
- `NOTICE_CHECKLIST`
- `COURSE_RESEARCH_REPORT`
- `CITATION_BUNDLE`

The database stores ownership, source run, content reference, content hash, version, MIME type, size, timestamps, and deletion state. JSON and Markdown are written atomically to a controlled artifact directory. PDF generation is a later export feature and is not required by v1. Every read or download rechecks ownership.

## 6. Model providers and routing

The existing `OpenAICompatibleClient` becomes a multi-instance provider registry. The existing `LLM_*` variables remain supported for compatibility. New backend-only configuration templates are:

```env
ZHIPU_LLM_BASE_URL=
ZHIPU_LLM_API_KEY=
ZHIPU_LLM_MODEL=

XUNFEI_LLM_BASE_URL=https://spark-api-open.xf-yun.com/v1
XUNFEI_LLM_API_KEY=
XUNFEI_LLM_MODEL=lite
```

Real credentials exist only in the untracked backend `.env`. They never enter Android, HarmonyOS, Web, logs, fixtures, artifacts, or commits.

Routing policies are:

```text
reasoning_primary
  Zhipu -> Xunfei -> controlled rules/RAG

fast_structured
  Xunfei -> Zhipu -> deterministic extraction

dual_review
  Zhipu generation + Xunfei review
  If one provider is unavailable, continue with one provider and return a warning.
```

Usage by domain:

- Final-review planning and research synthesis use `reasoning_primary`.
- Daily summaries and notice extraction use `fast_structured`.
- Citation/coverage review uses `dual_review`.

Every model output passes size checks, strict JSON parsing when structured output is required, Pydantic validation, allowed-field validation, citation/access validation, RiskEngine, and ToolRegistry. A model response is never itself a database write.

CI uses fake providers. A separate opt-in connectivity script reads local `.env` values, performs real provider checks, and masks all secrets in success and error output.

## 7. Data model

All migrations are additive and idempotent. Existing business tables remain authoritative.

### 7.1 Runtime tables

```text
agent_jobs
agent_runs
agent_run_steps
agent_context_snapshots
agent_tool_calls
agent_model_calls
agent_events
agent_memories
agent_approvals
agent_citations
agent_artifacts
```

### 7.2 Final-review tables

```text
final_review_campaigns
final_review_plan_versions
final_review_daily_agendas
final_review_daily_items
final_review_adjustment_proposals
```

Plan versions are immutable. Every daily agenda and daily item references its source plan version. Applying an adjustment creates a new version rather than overwriting the old version.

### 7.3 Notice-workflow tables

```text
notification_sources
notice_workflows
notice_workflow_actions
```

The source registry uses stable server-owned codes, initially `android_system`, `chaoxing`, `campus_announcement`, and `manual_input`. Server `permission_scope` expresses policy. Device notification permission remains device-owned state.

Workflow status transitions are:

```text
CREATED -> ANALYZING -> WAITING_CONFIRMATION -> PROCESSING -> COMPLETED
```

`EXPIRED` and `FAILED` are terminal states reachable from the applicable nonterminal states.

Action status transitions are:

```text
PROPOSED -> APPROVED -> EXECUTING -> DONE
PROPOSED -> REJECTED
APPROVED/EXECUTING -> FAILED
PROPOSED/APPROVED -> EXPIRED
```

### 7.4 Course-research tables

```text
course_research_sessions
course_research_reports
course_research_sources
```

Run lifecycle remains in `agent_runs`; research tables contain only domain input, policy, report, and source relationships.

### 7.5 Existing tables retained

```text
personal_tasks
study_sessions
study_checkins
learning_plans
learner_events
learner-state projection tables
```

## 8. Domain workflows

### 8.1 Final-exam review and daily follow-up

```text
Create campaign
-> build context snapshot
-> generate plan proposal
-> user edits/approves
-> create immutable plan v1
-> activate campaign
-> materialize today's agenda and near-term personal tasks
-> collect sessions, completions, check-in, and self-report evidence
-> Analyzer creates an adjustment proposal
-> RiskEngine classifies it
-> ApprovalGate resolves it when required
-> create plan v2 and retain v1
-> produce a final review artifact after the campaign
```

Rules:

- A campaign may include multiple courses and exams.
- Users explicitly set daily capacity, rest days, preferred periods, and intensity. Free time is not assumed to be study time.
- The full schedule lives in daily-agenda rows. Only the current and near-term items are materialized as idempotent `personal_tasks`.
- Morning follow-up explains today's priorities and expected time. Evening follow-up records completion, difficulty, and voluntary feedback.
- The Analyzer never edits a plan. It only creates an `AdjustmentProposal`.
- Reordering without changing total load may be `AUTO_SAFE` when the user enables it. Increasing total load, reducing rest, changing exam priority, or broadly moving work requires approval.
- Daily plans are server-authoritative. Android and HarmonyOS schedule local reminders; Web displays in-app reminders.

### 8.2 Course research and homework assistance

```text
User request
-> Coordinator decomposes the question
-> CourseResearcher searches accessible course material
-> WebResearcher searches public sources when policy permits
-> CitationVerifier checks accessibility, freshness, and agreement
-> Tutor applies the permitted assistance mode
-> Critic checks coverage, uncertainty, and academic policy
-> Synthesizer creates a cited Markdown report
```

The assistance mode is one of `HINT`, `EXPLAIN`, `REVIEW`, or `FULL_SOLUTION`.

Academic policy is independent:

```text
ALLOWED
LIMITED
EXAM_RESTRICTED
AI_PROHIBITED
UNKNOWN
```

The effective policy is the strictest result supported by course/assignment metadata, user declaration, and RiskEngine. Client input cannot force `ALLOWED`. `FULL_SOLUTION` is available only for ordinary practice where policy permits it. The runtime never submits coursework or fabricates sources, experiments, interviews, results, or learning history.

Source policy is explicit:

```json
{
  "course_material_priority": true,
  "allow_web": true,
  "allow_user_upload": true
}
```

Course sources take priority. Conflicts are shown with source and time instead of silently resolved. The initial implementation uses logical role switching in one executor, not six agent processes.

### 8.3 Campus notice to task workflow

```text
Android system notice / pasted text / campus announcement / Chaoxing sync
-> NoticeInterpreter extracts facts and uncertainty
-> WorkflowPlanner proposes steps
-> RiskEngine classifies every action
-> show preview where required
-> execute permitted internal actions
-> track materials and completion
-> remind on deadlines or missing information
```

Automation is disabled by default and enabled per source. Notice content fingerprints and source IDs prevent duplicates. When a notice changes, the runtime generates a difference preview and does not overwrite completed user work.

`AUTO_SAFE` includes creating a personal task, adding a reminder, associating a course, and generating a materials checklist. `CONFIRM_REQUIRED` includes changing existing plans, preparing messages or forms, and scheduling around conflicts. Authentication, CAPTCHA, payment, formal registration, assignment submission, and external school-system mutation are `MANUAL_ONLY`.

Without an official school interface, CampusMateAI provides steps and entry guidance only. It does not simulate private login or scrape private data.

## 9. API contract

### 9.1 Common runtime endpoints

```http
GET    /api/v1/agent-runtime/capabilities
POST   /api/v1/agent-jobs
GET    /api/v1/agent-jobs/{job_id}
GET    /api/v1/agent-runs/{run_id}
POST   /api/v1/agent-runs/{run_id}/cancel
GET    /api/v1/agent-runs/{run_id}/events
GET    /api/v1/agent-runs/{run_id}/events/stream
POST   /api/v1/agent-approvals/{approval_id}/decision
GET    /api/v1/agent-artifacts/{artifact_id}
```

All create and execute endpoints support `Idempotency-Key`. SSE supports `Last-Event-ID`.

### 9.2 Error envelope

```json
{
  "code": "AGENT_APPROVAL_REQUIRED",
  "message": "需要用户确认后继续",
  "request_id": "req_xxx",
  "details": {
    "run_id": "run_xxx",
    "approval_id": "approval_xxx"
  }
}
```

Stable initial codes are:

```text
AGENT_INVALID_STATE
AGENT_PERMISSION_DENIED
AGENT_TOOL_REJECTED
AGENT_APPROVAL_REQUIRED
AGENT_PROVIDER_UNAVAILABLE
AGENT_CONTEXT_EXPIRED
AGENT_IDEMPOTENCY_CONFLICT
AGENT_RUN_NOT_FOUND
AGENT_RUN_CANCELLED
AGENT_OUTPUT_SCHEMA_INVALID
AGENT_SOURCE_POLICY_VIOLATION
AGENT_ACADEMIC_POLICY_RESTRICTED
```

HTTP status codes continue to express transport/auth/conflict semantics. Clients branch on `code` for business behavior and never parse `message`.

### 9.3 Final-review endpoints

```http
POST   /api/v1/final-review/campaigns
GET    /api/v1/final-review/campaigns
GET    /api/v1/final-review/campaigns/{campaign_id}
POST   /api/v1/final-review/campaigns/{campaign_id}/plans/generate
GET    /api/v1/final-review/campaigns/{campaign_id}/plan-versions
GET    /api/v1/final-review/campaigns/{campaign_id}/plan-versions/{version}
POST   /api/v1/final-review/campaigns/{campaign_id}/activate
GET    /api/v1/final-review/campaigns/{campaign_id}/agendas/today
POST   /api/v1/final-review/daily-items/{item_id}/complete
POST   /api/v1/final-review/campaigns/{campaign_id}/daily-checkins
POST   /api/v1/final-review/campaigns/{campaign_id}/adjustments/analyze
GET    /api/v1/final-review/campaigns/{campaign_id}/adjustment-proposals
POST   /api/v1/final-review/adjustment-proposals/{proposal_id}/decision
```

### 9.4 Notice-workflow endpoints

```http
GET    /api/v1/notification-sources
PATCH  /api/v1/notification-sources/{source_id}
POST   /api/v1/notices/{notice_id}/workflow
GET    /api/v1/notice-workflows/{workflow_id}
POST   /api/v1/notice-workflows/{workflow_id}/reanalyze
POST   /api/v1/notice-workflow-actions/{action_id}/decision
POST   /api/v1/notice-workflow-actions/{action_id}/execute
```

### 9.5 Course-research endpoints

```http
POST   /api/v1/course-research/runs
GET    /api/v1/course-research/runs
GET    /api/v1/course-research/runs/{run_id}
POST   /api/v1/course-research/runs/{run_id}/cancel
GET    /api/v1/course-research/runs/{run_id}/artifacts
```

## 10. Client responsibilities

| Capability | Android | HarmonyOS | Web |
|---|---|---|---|
| Final-review planning | Add final-review area to Study | Equivalent ArkUI area | Extend existing learning-plan center |
| Today's agenda | Home card and Study page | Home card and Study page | Home and learner-state page |
| Daily reminders | WorkManager local notifications | Platform reminder/background task | In-app reminder |
| Plan versions | Timeline/diff presentation | Timeline/diff presentation | Wide-screen comparison |
| Notice workflow | Reuse notification inbox | Manual/backend sources initially | Notice center |
| Course research | Conversational progress/report | Conversational progress/report | Split-pane research workbench |
| Approval | Bottom confirmation surface | Bottom confirmation surface | Side panel or dialog |
| Run progress | SSE with lifecycle reconnect | SSE with lifecycle reconnect | Continuous SSE |
| Artifacts | View/share | View/share | View/export |

All three clients use identical field semantics, error codes, status enums, phases, risk levels, event sequences, and academic-policy values. Layouts remain platform-appropriate rather than visually identical.

Clients do not hold model credentials or domain-decision logic. Unknown enum values render a safe generic state instead of crashing or granting permission.

## 11. Reliability and security

- A provider call retries at most once before routing to the backup provider.
- Dual-provider failure uses existing rules/RAG when safe; otherwise the run fails explicitly.
- Context expiry, approval expiry, partial sources, cancellation, and restart recovery have explicit states and events.
- One campaign has at most one plan-generation/adjustment run at a time.
- Plan application uses optimistic version checks; old approvals cannot overwrite current plans.
- One notice fingerprint has at most one active workflow.
- Unique database indexes provide final idempotency guarantees; in-memory locks are only an optimization.
- All routes use existing JWT and student-only authorization as appropriate.
- Public source fetching blocks local/loopback/private/link-local destinations, non-HTTP(S) schemes, redirect escapes, oversized responses, and timeouts.
- Uploads reuse existing extension, size, path, and ownership checks.
- Production prohibits mock providers and automatic approval of high-risk actions.
- Provider status exposes availability, capabilities, and fallback state, never endpoints or credentials.

## 12. Verification strategy

### 12.1 Backend tests

Tests cover run/step/event/approval transitions, invalid transitions, context access/expiry/limits, role capability registration, action-level permissions, concurrent idempotency, provider routing, invalid structured output, risk classification, immutable plan versions, adjustment proposals, notice deduplication/differences, automation defaults, `MANUAL_ONLY` enforcement, academic-policy restriction, citation access, artifact isolation, SSE sequence/resume/redaction, and restart recovery without duplicate personal tasks.

CI uses fake providers. Real Zhipu/Xunfei connectivity is an opt-in local check whose output masks secrets.

### 12.2 API contract tests

OpenAPI is canonical:

```text
OpenAPI
-> generated/shared JSON fixtures
-> backend validation
-> Android parsing tests
-> HarmonyOS parsing tests
-> Web parsing tests
```

Contract checks reject removal or incompatible type changes to frozen fields. New optional fields and unknown enum values must remain safely parseable by older clients.

### 12.3 Client tests

Android tests repositories, DTO mapping, SSE resume, error mapping, WorkManager uniqueness, notification permission, lifecycle restoration, and Compose empty/loading/approval/partial/failure/offline states. JVM commands use the repository-bundled JDK 21.

HarmonyOS tests repositories, DTO mapping, SSE cursors, error mapping, reminder deduplication, lifecycle restoration, and ArkUI states. No provider credential or complete sensitive context is stored locally.

Web tests API clients, domain hooks, SSE resume, approvals, plan-version diffs, and accessible component states. Initial Playwright scope is limited to three golden paths:

1. Create final review -> generate -> approve -> view today's agenda.
2. Analyze notice -> confirm -> create personal task.
3. Ask research question -> observe run -> open artifact.

Other error combinations remain backend/unit/component tests until their end-to-end value justifies expansion.

## 13. Acceptance scenarios

### Final review

1. A student selects three exams and 120 daily minutes.
2. Zhipu generates the plan and Xunfei generates the daily summary.
3. Approval activates plan v1 and creates today's tasks exactly once.
4. The student misses one item and reports insufficient time.
5. Analyzer creates a lower-load adjustment proposal without editing the plan.
6. Approval creates plan v2; plan v1 remains readable.
7. All clients show the same current version and completion state.

### Notice workflow

1. Android captures a Chaoxing system notification.
2. The backend identifies deadline, materials, uncertainty, and steps.
3. An enabled `AUTO_SAFE` policy creates an internal task once.
4. A formal submission action remains `MANUAL_ONLY`.
5. Duplicate delivery does not create another task.
6. Updated notice content produces a difference preview without overwriting completed work.

### Course research

1. The student asks for an explanation scoped to a course.
2. Logical roles perform course retrieval, permitted public retrieval, citation verification, tutoring, and review.
3. Conflicting sources are shown with provenance and time.
4. Disabling web access prevents all public fetches.
5. An exam-restricted request is limited to permitted assistance.
6. A cited Markdown artifact is generated and ownership-checked.
7. Provider failure is visible as a fallback/partial condition, not presented as a dual-model success.

## 14. Demo-data isolation

Development/test seeding creates a deterministic dedicated demo student and demo-owned campaigns, runs, notices, research sessions, artifacts, and tasks. A reset command deletes only records owned by that demo user. Production refuses demo seeding and demo reset. No general tenant abstraction is introduced in v1.

## 15. Delivery milestones

### Milestone 1: Runtime foundation

- Additive database migration and repositories.
- Frozen schemas, errors, events, and OpenAPI contract fixtures.
- Context, memory, roles, tools, risk, approval, run, recovery, event, trace, and artifact services.
- Direct Zhipu/Xunfei provider registry and routing with deterministic fallback.
- Runtime unit/integration/contract tests.

### Milestone 2: Final-review loop

- Campaigns, immutable plan versions, daily agendas/items, adjustment proposals, artifacts, and APIs.
- Android, HarmonyOS, and Web surfaces.
- Local mobile reminders and cross-client state verification.

### Milestone 3: Course research and homework assistance

- Logical role pipeline, source policy, academic policy, citation validation, and report artifacts.
- Android, HarmonyOS, and Web surfaces.
- Research golden-path test.

### Milestone 4: Notice workflow automation

- Source registry, workflow/action state machines, deduplication, differences, risk and approval integration.
- Android notification inbox integration, HarmonyOS supported sources, and Web notice center.
- Notice golden-path test.

### Milestone 5: Integrated verification and demo

- Full backend and client regression suites.
- Three OpenAPI fixture consumers.
- Three Playwright golden paths.
- Dedicated resettable demo-user dataset.
- Documentation and competition demonstration flow.

Each milestone is independently verified and committed. A later milestone may add optional fields or a versioned endpoint, but cannot silently reinterpret frozen fields from an earlier milestone.

## 16. Frozen decisions

- CampusMateAI implements its own small domain runtime; EvoFlow remains a design reference only.
- Runtime infrastructure is delivered before domain modules; domain milestones follow the fixed order above.
- Logical role switching is used instead of physical multi-agent processes in v1.
- Context is built centrally and memory is explicit, confirmed, bounded, and removable.
- Models propose; validated tools and domain services act.
- Analyzer produces proposals; only the controlled application path creates a new plan version.
- Runtime events and learner evidence remain separate.
- Mobile background reminders are local in v1; Web uses in-app reminders.
- JSON/Markdown artifacts are first-class; PDF is a later export.
- Academic policy is independent of assistance mode and resolves to the strictest supported restriction.
- Client code never owns domain decisions.

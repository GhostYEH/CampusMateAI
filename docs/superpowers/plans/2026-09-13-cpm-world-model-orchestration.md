# CPM World Model Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CPM a safe, explainable entry point that uses CORE, ACADEMIC, and WORLD state, deterministic forecasts and simulations, and user-confirmed plans without allowing CampusMate-LM to affect production behavior.

**Architecture:** Add a read-only `CpmWorldContextService` that converts projection families into a fixed, privacy-safe DTO and refreshes only stale or absent families. Add a `CpmOrchestrator` that classifies a closed set of intents and invokes only the existing deterministic services; the counselor route remains the compatibility endpoint and lets RAG/primary LLM express, but never calculate or write, the result. Candidate-model calls are strictly asynchronous shadow observations over sanitized summaries.

**Tech Stack:** Python 3, FastAPI, Pydantic v2, SQLite repositories, pytest, React 18/Vite, node:test, Playwright, existing deterministic Forecast/Simulation/Planner services.

**Spec:** `docs/superpowers/specs/2026-09-13-cpm-world-model-orchestration-design.md`

## Global Constraints

- Preserve `POST /api/v1/counselor/chat` and `POST /api/v1/assistant/counselor/chat`; new request fields must be optional and existing clients must receive compatible response fields.
- CPM may read only the authenticated user's resources; it must never accept a client-supplied user ID, projection scope, internal run ID, or snapshot ID as authority.
- Context sent to a primary LLM or Shadow Runner must use an allowlisted DTO and must never contain raw `snapshot.value`, event payloads, internal IDs/table names, credentials, attachment/chat text, or psychological/medical/personality labels.
- Campus facts remain RAG-backed and cited; learner state can personalize advice but can never establish policy facts, places, amounts, forms, or deadlines.
- Forecast remains `ForecastService`; simulation remains `SimulationService` and is read-only with `causal_claim=false`; planner writes continue only through the existing confirmed plan state machine and transaction.
- CampusMate-LM remains Shadow-only: its output cannot alter an answer, forecast, simulation, plan, task, goal, event, or state. `campusmate_lm_affects_production` remains false.
- Do not reintroduce C-language/knowledge-point modules, alter navigation styling, create mobile clients, or change unrelated API/database/deployment configuration.
- Each task must be committed with only its listed files. Before every commit run `git diff --check`, inspect `git status --short`, and avoid staging other sessions' files.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `backend/app/schemas/cpm_world.py` | Closed CPM intent/action enums and safe context/orchestration DTOs. |
| `backend/app/services/cpm_world_context_service.py` | Freshness-aware CORE/ACADEMIC/WORLD reads, re-projection, allowlisting and bounded rendering. |
| `backend/app/services/cpm_orchestrator.py` | Fixed intent-to-service orchestration and safe response metadata/actions. |
| `backend/app/services/container.py` | Constructs and exposes the two CPM services without duplicate repositories. |
| `backend/app/api/routes/counselor.py` | Replaces direct snapshot serialization with orchestrated context while retaining stream/non-stream behavior. |
| `backend/app/schemas/chat.py` | Optional controlled CPM request parameters plus compatible `context_used` response shape. |
| `backend/app/services/model_capability_registry.py` | Aligns five Shadow capability names, schemas, safe tools and deterministic fallbacks. |
| `backend/app/schemas/model_capability.py` | Strict, generic Pydantic contracts shared by backend capability validation. |
| `backend/app/services/learning_agent_tools.py` | Replaces single-subject knowledge read with CPM's closed read-only tool vocabulary. |
| `backend/app/services/learner_event_service.py` | Records only explicit CPM feedback as a controlled event and invalidates/reprojects the affected families. |
| `webreact/src/data/api.js` | Sends optional controlled CPM fields and preserves SSE parsing of `context_used`/actions. |
| `webreact/src/pages/CounselorPage.jsx` | Shows state/forecast/simulation/plan provenance and opens existing pages or asks confirmation; never calls write APIs directly from model output. |
| `backend/tests/test_cpm_world_context.py` | Context freshness, family isolation, allowlist and anonymous/cross-user behavior. |
| `backend/tests/test_cpm_orchestrator.py` | Intent routing, service delegation, degradation and no-write behavior. |
| `backend/tests/test_counselor_cpm_world_model.py` | HTTP/SSE contract and RAG-versus-personal-state boundary. |
| `backend/tests/test_cpm_feedback_loop.py` | Explicit feedback event, invalidation and reprojection behavior. |
| `backend/tests/test_cpm_shadow_capabilities.py` | Backend/ML capability contract and no-production-impact guarantees. |
| `webreact/tests/counselor-world-model.test.mjs` | Client request/metadata/action rendering behavior. |
| `webreact/tests/e2e/cpm-world-model-journey.py` | Desktop/mobile real journey using two different students. |

## Task 1: Define the safe CPM contracts and a freshness-aware state context service

**Files:**
- Create: `backend/app/schemas/cpm_world.py`
- Create: `backend/app/services/cpm_world_context_service.py`
- Modify: `backend/app/services/container.py`
- Test: `backend/tests/test_cpm_world_context.py`

**Interfaces:**
- Consumes: `LearnerStateProjectionService.project_user`, `.project_academic`, `.project_world`; `LearnerStateRepository.get_current_run` and `.list_all_current_snapshots`.
- Produces: `CpmWorldContextService.build_context(*, user_id: str, as_of: datetime, projection_kinds: tuple[ProjectionKind, ...] = ("CORE", "ACADEMIC", "WORLD"), max_items_per_kind: int = 8, max_characters: int = 6000) -> CpmWorldContext`.
- Produces: `CpmWorldContext.to_prompt_block() -> str` and `.context_used() -> dict[str, object]`, both containing only safe DTO fields.

- [ ] **Step 1: Write failing context-service tests**

```python
def test_build_context_reads_all_three_families_and_never_serializes_raw_value(service, now):
    context = service.build_context(user_id="student-a", as_of=now)

    assert context.projection_kinds == ("CORE", "ACADEMIC", "WORLD")
    assert {item.projection_kind for item in context.items} == {"CORE", "ACADEMIC", "WORLD"}
    prompt = context.to_prompt_block()
    assert "raw_task_title" not in prompt
    assert "snapshot_id" not in prompt
    assert "source_id" not in prompt
    assert "user_id" not in prompt


def test_expired_academic_family_is_reprojected_without_blocking_core_and_world(service, state_spy, now):
    context = service.build_context(user_id="student-a", as_of=now)

    assert state_spy.project_user_calls == 0
    assert state_spy.project_academic_calls == 1
    assert state_spy.project_world_calls == 0
    assert "ACADEMIC_REPROJECTED" in context.warning_codes


def test_empty_or_failed_family_degrades_only_that_family(service, state_spy, now):
    state_spy.raise_for_kind = "WORLD"
    context = service.build_context(user_id="student-a", as_of=now)

    assert "CORE" in context.projection_kinds
    assert "ACADEMIC" in context.projection_kinds
    assert "WORLD_UNAVAILABLE" in context.warning_codes
    assert context.context_used()["learner_state_used"] is True
```

- [ ] **Step 2: Run the tests to verify the contract is absent**

Run: `cd backend; pytest tests/test_cpm_world_context.py -q`

Expected: collection fails because `cpm_world` and `CpmWorldContextService` do not exist.

- [ ] **Step 3: Add the strict DTOs in `backend/app/schemas/cpm_world.py`**

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

ProjectionKind = Literal["CORE", "ACADEMIC", "WORLD"]
ConfidenceBucket = Literal["HIGH", "MEDIUM", "LOW", "NONE"]

class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

class CpmStateContextItem(_StrictModel):
    projection_kind: ProjectionKind
    state_type: str = Field(min_length=1, max_length=80)
    scope_type: Literal["USER", "COURSE", "GOAL"]
    state_band: str = Field(min_length=1, max_length=64)
    confidence_bucket: ConfidenceBucket
    data_quality: Literal["verified", "partial", "stale", "unavailable"]
    explanation_codes: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    warning_codes: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    as_of: datetime
    valid_until: datetime | None = None

class CpmProjectionSummary(_StrictModel):
    projection_kind: ProjectionKind
    estimator_version: str = Field(min_length=1, max_length=96)
    as_of: datetime
    valid_until: datetime | None = None
    state_count: int = Field(ge=0, le=8)

class CpmWorldContext(_StrictModel):
    items: tuple[CpmStateContextItem, ...] = Field(default_factory=tuple, max_length=24)
    families: tuple[CpmProjectionSummary, ...] = Field(default_factory=tuple, max_length=3)
    projection_kinds: tuple[ProjectionKind, ...] = Field(default_factory=tuple, max_length=3)
    warning_codes: tuple[str, ...] = Field(default_factory=tuple, max_length=24)
```

Add `to_prompt_block()` with only the fields in `CpmStateContextItem`; make `context_used()` return booleans/counts/kinds and warnings, never raw values or identifiers. Use an explicit `STATE_VALUE_ADAPTERS: dict[str, Callable[[dict[str, Any]], str]]` keyed by state type; unknown values must render `"UNAVAILABLE"`, not `str(value)`.

- [ ] **Step 4: Implement `CpmWorldContextService` minimally and safely**

```python
class CpmWorldContextService:
    def __init__(self, *, state_service, state_repository) -> None:
        self._state_service = state_service
        self._state_repository = state_repository

    def build_context(self, *, user_id: str, as_of: datetime,
                      projection_kinds: tuple[ProjectionKind, ...] = ("CORE", "ACADEMIC", "WORLD"),
                      max_items_per_kind: int = 8, max_characters: int = 6000) -> CpmWorldContext:
        return self._build_bounded_context(
            user_id=user_id,
            as_of=as_of,
            projection_kinds=projection_kinds,
            max_items_per_kind=max_items_per_kind,
            max_characters=max_characters,
        )

    def _refresh_family(self, *, user_id: str, kind: ProjectionKind, as_of: datetime):
        methods = {"CORE": self._state_service.project_user,
                   "ACADEMIC": self._state_service.project_academic,
                   "WORLD": self._state_service.project_world}
        return methods[kind](user_id, as_of=as_of, trigger="cpm_context")
```

The service must call `list_all_current_snapshots(user_id=user_id, projection_kind=kind, projection_scope="__user__", max_items=max_items_per_kind + 1)`. It must parse `valid_until`, recognize absent/expired rows, use the projection service for refresh, and query again after refresh. Do not change the repository default projection kind; the CPM caller must always pass it explicitly.

Wire a single `cpm_world_context_service` instance into `ServiceContainer` after `learner_state_service` is created.

- [ ] **Step 5: Run focused tests and a type/import check**

Run:

```powershell
cd backend
pytest tests/test_cpm_world_context.py -q
python -m compileall -q app
```

Expected: all new tests pass and no import cycle occurs in `container.py`.

- [ ] **Step 6: Commit the independently testable context layer**

```powershell
git add backend/app/schemas/cpm_world.py backend/app/services/cpm_world_context_service.py backend/app/services/container.py backend/tests/test_cpm_world_context.py
git diff --cached --check
git commit -m "feat(backend): build safe CPM world context"
```

## Task 2: Add closed CPM intents, read-only orchestration, and response metadata

**Files:**
- Modify: `backend/app/schemas/cpm_world.py`
- Create: `backend/app/services/cpm_orchestrator.py`
- Modify: `backend/app/services/container.py`
- Test: `backend/tests/test_cpm_orchestrator.py`

**Interfaces:**
- Consumes: `CpmWorldContextService.build_context`, `ForecastService.list_forecasts`, `SimulationService.simulate`, `LearningPlannerService.generate`, user-owned goal/task/plan repositories.
- Produces: `CpmOrchestrator.prepare(*, user_id: str, message: str, requested_intent: CpmIntent | None, simulation_request: SimulationRequest | None, available_minutes: int | None, as_of: datetime) -> CpmOrchestrationResult`.
- `CpmOrchestrationResult` exposes `llm_context: str`, `context_used: dict[str, object]`, `warning_codes: tuple[str, ...]`, `suggested_actions: tuple[CpmSuggestedAction, ...]`, and never executes a write.

- [ ] **Step 1: Write failing orchestration tests with service spies**

```python
def test_forecast_intent_delegates_to_official_service_and_returns_provenance(orchestrator, forecast_spy, now):
    result = orchestrator.prepare(
        user_id="student-a", message="未来七天任务会不会太多？",
        requested_intent="FORECAST_QUERY", simulation_request=None,
        available_minutes=None, as_of=now,
    )

    assert forecast_spy.calls == [("student-a", 7)]
    assert result.context_used["forecast_used"] is True
    assert "FORECAST_QUERY" in result.llm_context
    assert all(action.type != "PROPOSE_PLAN_EXECUTION" for action in result.suggested_actions)


def test_scenario_intent_without_valid_intervention_returns_clarification(orchestrator, simulation_spy, now):
    result = orchestrator.prepare(
        user_id="student-a", message="如果我调整一下会怎么样？",
        requested_intent="SCENARIO_COMPARE", simulation_request=None,
        available_minutes=None, as_of=now,
    )

    assert simulation_spy.calls == []
    assert result.needs_clarification is True
    assert "SIMULATION_PARAMETERS_REQUIRED" in result.warning_codes


def test_plan_intent_generates_only_a_proposal(orchestrator, planner_spy, now):
    result = orchestrator.prepare(
        user_id="student-a", message="给我安排这周的行动", requested_intent="PLAN_REQUEST",
        simulation_request=None, available_minutes=120, as_of=now,
    )

    assert planner_spy.generate_calls == 1
    assert {action.type for action in result.suggested_actions} == {"OPEN_PLAN", "PROPOSE_PLAN_DECISION"}
    assert planner_spy.execute_calls == 0
```

- [ ] **Step 2: Run tests to prove orchestrator types and behavior are missing**

Run: `cd backend; pytest tests/test_cpm_orchestrator.py -q`

Expected: FAIL because `CpmOrchestrator` and `CpmIntent` do not exist.

- [ ] **Step 3: Extend `cpm_world.py` with the closed request/result contract**

```python
CpmIntent = Literal[
    "CAMPUS_POLICY_QUERY", "CURRENT_STATE_QUERY", "FORECAST_QUERY",
    "SCENARIO_COMPARE", "PLAN_REQUEST", "GOAL_PROGRESS", "GENERAL_CHAT",
]
CpmActionType = Literal[
    "OPEN_STATE", "OPEN_FORECAST", "OPEN_SIMULATION", "OPEN_PLAN", "OPEN_GOAL",
    "PROPOSE_PLAN_GENERATION", "PROPOSE_PLAN_DECISION", "PROPOSE_PLAN_EXECUTION", "PROPOSE_PLAN_UNDO",
]

class CpmSuggestedAction(_StrictModel):
    id: str = Field(min_length=1, max_length=96)
    label: str = Field(min_length=1, max_length=80)
    type: CpmActionType
    target: Literal["learning-state", "prediction", "learning-plan", "student-goals"]

class CpmOrchestrationResult(_StrictModel):
    intent: CpmIntent
    llm_context: str = Field(max_length=8000)
    context_used: dict[str, object]
    warning_codes: tuple[str, ...] = Field(default_factory=tuple, max_length=24)
    suggested_actions: tuple[CpmSuggestedAction, ...] = Field(default_factory=tuple, max_length=4)
    needs_clarification: bool = False
```

Do not include a `payload`, `plan_id`, `snapshot_id`, or `user_id` field in an LLM-generated action. The web client derives navigation from `target`; formal plan identifiers remain in server responses from the existing plan endpoints.

- [ ] **Step 4: Implement the deterministic `CpmOrchestrator`**

```python
class CpmOrchestrator:
    def prepare(self, *, user_id: str, message: str, requested_intent: CpmIntent | None,
                simulation_request: SimulationRequest | None, available_minutes: int | None,
                as_of: datetime) -> CpmOrchestrationResult:
        intent = requested_intent or self._classify_deterministically(message)
        context = self._context_service.build_context(user_id=user_id, as_of=as_of)
        if intent == "FORECAST_QUERY":
            forecasts, _ = self._forecast_service.list_forecasts(
                user_id=user_id, as_of=as_of, horizon_days=7, page=1, page_size=5)
            return self._with_forecasts(intent, context, forecasts)
        if intent == "SCENARIO_COMPARE":
            return self._with_simulation_or_clarification(intent, context, simulation_request, user_id, as_of)
        if intent == "PLAN_REQUEST":
            return self._with_plan_proposal(intent, context, user_id, available_minutes, as_of)
        return self._with_read_only_context(intent, context, user_id, as_of)
```

Implement a deterministic phrase classifier only for convenience: terms such as `预测/趋势/未来/风险` map to `FORECAST_QUERY`, `如果/方案/模拟/比较` map to `SCENARIO_COMPARE`, and `计划/安排/待办` map to `PLAN_REQUEST`; all other messages return `GENERAL_CHAT`. A supplied `requested_intent` wins only when it is a valid closed enum.

For simulation, call the existing `SimulationService.simulate` only when Pydantic has already validated a discriminated `SimulationRequest.intervention`; otherwise emit `SIMULATION_PARAMETERS_REQUIRED`. For plans, call only `LearningPlannerService.generate(user_id=user_id, available_minutes=max(15, min(available_minutes or 60, 480)), as_of=as_of)` and emit proposal/open actions. Catch a service failure by adding `FORECAST_UNAVAILABLE`, `SIMULATION_UNAVAILABLE`, or `PLAN_UNAVAILABLE`; never fabricate a result.

Instantiate the orchestrator in the container after forecast, simulation, planner, repositories and context service all exist. It must receive services by constructor injection rather than calling `get_container()`.

- [ ] **Step 5: Run orchestration tests and verify no database mutation**

Run:

```powershell
cd backend
pytest tests/test_cpm_orchestrator.py -q
pytest tests/test_simulation_service.py tests/test_phase4_learning_plans.py -q
```

Expected: orchestration tests pass; existing simulation/plan semantics still pass.

- [ ] **Step 6: Commit the read-only orchestration unit**

```powershell
git add backend/app/schemas/cpm_world.py backend/app/services/cpm_orchestrator.py backend/app/services/container.py backend/tests/test_cpm_orchestrator.py
git diff --cached --check
git commit -m "feat(backend): orchestrate CPM world model reads"
```

## Task 3: Integrate CPM orchestration into the counselor HTTP and SSE contracts

**Files:**
- Modify: `backend/app/schemas/chat.py`
- Modify: `backend/app/api/routes/counselor.py`
- Modify: `backend/tests/test_counselor_knowledge_grounding.py`
- Create: `backend/tests/test_counselor_cpm_world_model.py`

**Interfaces:**
- Consumes: `CpmOrchestrator.prepare` from Task 2.
- Produces: optional `ChatRequest.cpm_intent`, `.simulation_request`, and `.available_minutes`; compatible `ChatFinalMeta.context_used`, `.context_warnings`, and `SuggestedAction` items.
- The legacy `_collect_learner_state_context` is removed; the route never calls `LearnerStateRepository` directly for LLM context.

- [ ] **Step 1: Write failing HTTP and SSE tests**

```python
def test_authenticated_counselor_response_reports_all_state_families(client, student_headers, orchestrator_spy):
    response = client.post("/api/v1/counselor/chat", headers=student_headers, json={
        "message": "看看我最近的状态和未来一周风险", "stream": False,
        "cpm_intent": "FORECAST_QUERY",
    })

    assert response.status_code == 200
    body = response.json()
    assert body["context_used"]["projection_kinds"] == ["CORE", "ACADEMIC", "WORLD"]
    assert body["context_used"]["forecast_used"] is True
    assert orchestrator_spy.user_ids == ["student-a"]


def test_anonymous_counselor_request_never_reads_personal_world_model(client, orchestrator_spy):
    response = client.post("/api/v1/counselor/chat", json={"message": "学校图书馆几点关门？", "stream": False})

    assert response.status_code == 200
    assert orchestrator_spy.user_ids == []
    assert response.json()["context_used"]["learner_state_used"] is False


def test_policy_answer_keeps_rag_sources_separate_from_personal_state_context(client, student_headers):
    response = client.post("/api/v1/counselor/chat", headers=student_headers, json={
        "message": "奖学金申请材料有哪些？", "stream": False,
        "cpm_intent": "CAMPUS_POLICY_QUERY",
    })

    body = response.json()
    assert body["sources"]
    assert "WORLD" not in {source["title"] for source in body["sources"]}
    assert body["context_used"]["learner_state_used"] is True
```

- [ ] **Step 2: Run these tests to demonstrate that routing has not been wired**

Run: `cd backend; pytest tests/test_counselor_cpm_world_model.py -q`

Expected: FAIL because `cpm_intent` is rejected or the direct repository collector is used.

- [ ] **Step 3: Add optional, bounded request fields and compatible metadata**

```python
class ChatRequest(BaseModel):
    # existing fields remain unchanged
    cpm_intent: CpmIntent | None = None
    simulation_request: SimulationRequest | None = None
    available_minutes: int | None = Field(None, ge=15, le=480)

class SuggestedAction(BaseModel):
    id: str
    label: str
    type: str = "none"
    target: str | None = None
```

Import the two CPM request types from `schemas.cpm_world` and `schemas.simulation`. Preserve `payload` as an optional legacy field for existing clients, but new CPM action construction must set only `id`, `label`, `type`, and `target`.

- [ ] **Step 4: Replace direct state serialization in `counselor.py`**

```python
async def chat(req: ChatRequest, user: Optional[UserRow] = Depends(current_user_optional)):
    # retain current teaching context, task verification, attachment and web-search behavior
    cpm_result = None
    if user is not None:
        cpm_result = container.cpm_orchestrator.prepare(
            user_id=user.id, message=req.message, requested_intent=req.cpm_intent,
            simulation_request=req.simulation_request, available_minutes=req.available_minutes,
            as_of=datetime.now(timezone.utc),
        )
        context_used.update(cpm_result.context_used)
        all_ctx_warnings.extend(cpm_result.warning_codes)
        tasks_hint = "\n\n".join(part for part in [tasks_hint, cpm_result.llm_context] if part)
```

Convert `CpmSuggestedAction` to existing `SuggestedAction` before `_stream_answer`. Extend `_stream_answer` and `_stream` parameters with `suggested_actions`; after each RAG event, append only the server-built actions to `ChatFinalMeta.suggested_actions`. Do not modify RAG's document source collection and do not interpolate a CPM string into `context_block`, which is reserved for campus facts.

Delete `_collect_learner_state_context` rather than leaving an alternative code path that serializes `snapshot.value`. The only state text supplied to RAG must be `cpm_result.llm_context`.

- [ ] **Step 5: Run route, grounding, and SSE regressions**

Run:

```powershell
cd backend
pytest tests/test_counselor_cpm_world_model.py tests/test_counselor_knowledge_grounding.py -q
pytest tests/test_chat*.py -q
```

Expected: all response paths preserve existing sources/chunks/done SSE events and add only compatible optional metadata.

- [ ] **Step 6: Commit the backward-compatible CPM entry point**

```powershell
git add backend/app/schemas/chat.py backend/app/api/routes/counselor.py backend/tests/test_counselor_knowledge_grounding.py backend/tests/test_counselor_cpm_world_model.py
git diff --cached --check
git commit -m "feat(backend): connect CPM to world model orchestration"
```

## Task 4: Close the explicit feedback-to-state-update loop without ingesting chat content

**Files:**
- Modify: `backend/app/schemas/cpm_world.py`
- Modify: `backend/app/services/cpm_orchestrator.py`
- Modify: `backend/app/services/learner_event_service.py`
- Modify: `backend/app/api/routes/counselor.py`
- Create: `backend/tests/test_cpm_feedback_loop.py`

**Interfaces:**
- Produces: `CpmFeedbackRequest(feedback_code: Literal["HELPFUL", "NOT_HELPFUL", "TOO_EARLY", "TOO_LATE", "TOO_MANY", "IRRELEVANT"], plan_id: str | None, idempotency_key: str)`.
- Produces: `LearnerEventService.record_cpm_feedback(*, user_id: str, feedback_code: str, plan_id: str | None, occurred_at: datetime, idempotency_key: str) -> LearnerEventAppendResult | None`.
- Consumes: existing plan feedback persistence when `plan_id` is present; planner remains authoritative for plan state.

- [ ] **Step 1: Write failing tests for explicit-only feedback**

```python
def test_explicit_feedback_creates_safe_event_and_refreshes_world_state(client, student_headers, event_repo, state_spy):
    response = client.post("/api/v1/counselor/feedback", headers=student_headers, json={
        "feedback_code": "TOO_MANY", "idempotency_key": "feedback-001",
    })

    assert response.status_code == 200
    events, _ = event_repo.list_for_user(user_id="student-a", event_type="cpm_feedback", page=1, page_size=10)
    assert len(events) == 1
    assert events[0].payload == {"feedback_code": "TOO_MANY"}
    assert state_spy.project_world_calls == 1


def test_feedback_retry_is_idempotent_and_never_stores_chat_message(client, student_headers, event_repo):
    body = {"feedback_code": "HELPFUL", "idempotency_key": "feedback-002"}
    assert client.post("/api/v1/counselor/feedback", headers=student_headers, json=body).status_code == 200
    assert client.post("/api/v1/counselor/feedback", headers=student_headers, json=body).status_code == 200

    events, _ = event_repo.list_for_user(user_id="student-a", event_type="cpm_feedback", page=1, page_size=10)
    assert len(events) == 1
    assert "message" not in events[0].payload
```

- [ ] **Step 2: Run the feedback tests and verify the endpoint does not exist**

Run: `cd backend; pytest tests/test_cpm_feedback_loop.py -q`

Expected: FAIL with 404 or missing `record_cpm_feedback`.

- [ ] **Step 3: Add the request model and safe event writer**

```python
class CpmFeedbackRequest(_StrictModel):
    feedback_code: Literal["HELPFUL", "NOT_HELPFUL", "TOO_EARLY", "TOO_LATE", "TOO_MANY", "IRRELEVANT"]
    plan_id: str | None = Field(None, max_length=128)
    idempotency_key: str = Field(min_length=8, max_length=128)

def record_cpm_feedback(self, *, user_id: str, feedback_code: str, plan_id: str | None,
                        occurred_at: datetime, idempotency_key: str):
    event = LearnerEventCreate(
        source="campus", event_type="cpm_feedback", occurred_at=occurred_at,
        subject_type="learning_plan" if plan_id else "cpm", subject_id=plan_id or "cpm",
        outcome=feedback_code.lower(), data_quality="verified", consent_scope="core_learning_record",
        dedupe_key=f"cpm:feedback:{idempotency_key}", payload={"feedback_code": feedback_code},
    )
    return self.record_event(user_id=user_id, event=event)
```

Never put free-form message text, action label, plan content, target ID other than the verified plan ID, or model output in the event payload. If `plan_id` is supplied, lookup must be constrained by `user_id`; missing/other-user plans must return the existing not-found semantics before writing any event.

- [ ] **Step 4: Add the confirmed feedback route and reprojection trigger**

```python
@router.post("/counselor/feedback")
def submit_feedback(req: CpmFeedbackRequest, user: UserRow = Depends(current_active_user)):
    result = container.cpm_orchestrator.record_feedback(
        user_id=user.id, request=req, as_of=datetime.now(timezone.utc))
    return {"accepted": True, "event_reused": result.reused}
```

`CpmOrchestrator.record_feedback` must call the safe event writer, then request `project_user`, `project_academic`, and `project_world` with `trigger="cpm_feedback"`. Per-family projection errors return warning codes but do not delete the already-auditable event. Do not add a route accepting free-form feedback text.

- [ ] **Step 5: Run feedback, event, and state tests**

Run:

```powershell
cd backend
pytest tests/test_cpm_feedback_loop.py tests/test_learner_events.py tests/test_learner_state*.py -q
```

Expected: explicit feedback is idempotent, user-isolated, and generates only controlled evidence.

- [ ] **Step 6: Commit the explicit feedback loop**

```powershell
git add backend/app/schemas/cpm_world.py backend/app/services/cpm_orchestrator.py backend/app/services/learner_event_service.py backend/app/api/routes/counselor.py backend/tests/test_cpm_feedback_loop.py
git diff --cached --check
git commit -m "feat(backend): feed confirmed CPM outcomes into state"
```

## Task 5: Align Shadow capability contracts with the generic campus world model

**Files:**
- Modify: `backend/app/schemas/model_capability.py`
- Modify: `backend/app/services/model_capability_registry.py`
- Modify: `backend/app/services/learning_agent_tools.py`
- Modify: `backend/app/services/learner_control_service.py`
- Modify: `backend/app/demo/learner_model.py`
- Test: `backend/tests/test_cpm_shadow_capabilities.py`
- Modify: `ml/learner_state_evaluation/datasets/campusmate_lm_shadow_v1.manifest.json` only if a test proves its existing version metadata differs from backend.

**Interfaces:**
- Produces exactly: `student_state_summary_v1`, `campus_intent_routing_v1`, `notice_action_classification_v1`, `goal_support_classification_v1`, `read_only_tool_routing_v1`.
- Produces `READ_ONLY_TOOLS = ("read_core_state", "read_academic_state", "read_world_state", "read_state_evidence", "read_forecasts", "simulate_scenario", "read_personal_tasks", "read_student_goals", "read_learning_plans", "search_campus_materials")`.
- Removes these from new production runs: `learning_summary_v1`, `read_knowledge_state`, `search_course_materials`.

- [ ] **Step 1: Write the contract tests before changing registrations**

```python
EXPECTED = {
    "student_state_summary_v1", "campus_intent_routing_v1",
    "notice_action_classification_v1", "goal_support_classification_v1",
    "read_only_tool_routing_v1",
}

def test_backend_registry_and_ml_manifest_have_identical_capability_names(registry, manifest):
    assert set(registry.names()) == EXPECTED
    assert set(manifest["capabilities"]) == EXPECTED


def test_shadow_never_changes_production_or_executes_a_tool(runner, request, production_answer):
    result = run_async(runner.run(request))

    assert result.inference_source in {"DETERMINISTIC_FALLBACK", "FIXTURE", "REAL_MODEL"}
    assert production_answer() == "primary-answer"
    assert runner.tool_invocations == []


def test_old_capability_is_readable_history_but_rejected_for_new_request(registry):
    with pytest.raises(CapabilityValidationError):
        registry.validate_request(make_request(capability_name="learning_summary_v1"))
```

- [ ] **Step 2: Run the tests to record the old learning-platform mismatch**

Run: `cd backend; pytest tests/test_cpm_shadow_capabilities.py -q`

Expected: FAIL because old capability names/tools remain registered.

- [ ] **Step 3: Replace schemas and registry entries with generic, strict inputs**

```python
class StudentStateSummaryInput(_StrictModel):
    state_items: list[dict[str, str]] = Field(default_factory=list, max_length=24)
    warning_codes: list[str] = Field(default_factory=list, max_length=24)

class CampusIntentRoutingInput(_StrictModel):
    message_kind: Literal["policy", "state", "forecast", "scenario", "plan", "goal", "general"]
    authorized_tools: list[str] = Field(default_factory=list, max_length=10)

class NoticeActionClassificationInput(_StrictModel):
    notice_kind: Literal["ACADEMIC", "CAMPUS", "OTHER"]
    deadline_bucket: Literal["NONE", "LATER", "SOON", "URGENT", "OVERDUE"]

class GoalSupportClassificationInput(_StrictModel):
    goal_category: Literal["ACADEMIC", "RESEARCH", "COMPETITION", "CERTIFICATE", "JOB", "INTERNSHIP", "CAMPUS", "HEALTH", "GROWTH"]
    progress_band: Literal["NOT_STARTED", "EARLY", "ON_TRACK", "AT_RISK", "COMPLETE", "UNAVAILABLE"]
```

Define matching outputs with only controlled labels/scores. Register all five capability names in `ModelCapabilityRegistry`; only `read_only_tool_routing_v1` may name a tool, and validation must require it to be in the new `READ_ONLY_TOOLS`. Keep old records readable through repository/transparency migration logic, but make any newly submitted old capability fail with `MODEL_CAPABILITY_NOT_ALLOWED`.

Update `LearningAgentToolRegistry` to implement only the new closed read vocabulary. Each read must call the existing owned service/repository and return a safe DTO; `simulate_scenario` must call `SimulationService.simulate` with Pydantic-validated arguments. Do not add any write method to this registry.

- [ ] **Step 4: Make Shadow dispatch observational from CPM only**

Add `CpmOrchestrator._shadow_observe(result: CpmOrchestrationResult) -> None`, which submits only `StudentStateSummaryInput` or `CampusIntentRoutingInput` to `ModelShadowRunner` by a background task. It must catch and log only capability name plus exception class, must not await user-facing response completion, and must not read the result back into `CpmOrchestrationResult`.

Assert `settings.campusmate_lm_affects_production` remains false in the config/feature gate test; do not introduce any setting that can bypass the Shadow-only rule.

- [ ] **Step 5: Run backend/ML contract and Shadow regressions**

Run:

```powershell
cd backend
pytest tests/test_cpm_shadow_capabilities.py tests/test_model_capability_contracts.py tests/test_model_shadow_runner.py -q
cd ..\ml\learner_state_evaluation
pytest -q
```

Expected: backend and ML capability sets/versions match; synthetic or fallback results cannot be labelled as production inference.

- [ ] **Step 6: Commit capability alignment**

```powershell
git add backend/app/schemas/model_capability.py backend/app/services/model_capability_registry.py backend/app/services/learning_agent_tools.py backend/app/services/learner_control_service.py backend/app/demo/learner_model.py backend/tests/test_cpm_shadow_capabilities.py ml/learner_state_evaluation/datasets/campusmate_lm_shadow_v1.manifest.json
git diff --cached --check
git commit -m "refactor(ml): align CPM shadow capabilities"
```

If the manifest already matches and is untouched, omit it from `git add` rather than manufacturing a diff.

## Task 6: Make the React CPM client transparent and confirmation-only

**Files:**
- Modify: `webreact/src/data/api.js`
- Modify: `webreact/src/pages/CounselorPage.jsx`
- Create: `webreact/tests/counselor-world-model.test.mjs`
- Modify: `webreact/tests/e2e/learner-state-closed-loop.py` only if it remains present and is the project's existing shared browser harness.

**Interfaces:**
- Consumes counselor `context_used.projection_kinds`, `.forecast_used`, `.simulation_used`, `.plan_used`, `context_warnings`, and `suggested_actions[].target`.
- Produces: `chatStream(text, { cpmIntent, simulationRequest, availableMinutes, conversationId, recentTasks, webSearch, attachment, signal, onSources, onChunk, onDone, onError })` where absent CPM options are omitted from JSON.
- Produces client-side action handling that navigates only to `learning-state`, `prediction`, `learning-plan`, or `student-goals`; no action can invoke execute/undo/create/update APIs.

- [ ] **Step 1: Write failing node tests for request and action safety**

```javascript
test("chatStream sends optional controlled CPM fields but never a user id", async () => {
  await api.chatStream("看看趋势", { cpmIntent: "FORECAST_QUERY", availableMinutes: 90, onDone() {} });
  assert.deepEqual(sentBody, { message: "看看趋势", stream: true, cpm_intent: "FORECAST_QUERY", available_minutes: 90 });
  assert.equal("user_id" in sentBody, false);
});

test("CPM metadata renders provenance and routes proposal actions without writing", () => {
  const ui = renderCounselorDone({
    context_used: { learner_state_used: true, projection_kinds: ["CORE", "ACADEMIC", "WORLD"], forecast_used: true },
    suggested_actions: [{ id: "open-forecast", label: "查看趋势", type: "OPEN_FORECAST", target: "prediction" }],
  });
  assert.match(ui.textContent, /已参考：CORE、ACADEMIC、WORLD/);
  ui.getByRole("button", { name: "查看趋势" }).click();
  assert.equal(navigatedTo, "/prediction");
  assert.equal(writeRequests.length, 0);
});
```

- [ ] **Step 2: Run the tests to verify current API/UI lack CPM fields**

Run: `cd webreact; node --test tests/counselor-world-model.test.mjs`

Expected: FAIL because `chatStream` does not serialize the controlled fields and UI has no provenance/action renderer.

- [ ] **Step 3: Extend `chatStream` without changing existing callers**

```javascript
export async function chatStream(message, options = {}) {
  const body = { message, stream: true, conversation_id: options.conversationId, /* existing options */ };
  if (options.cpmIntent) body.cpm_intent = options.cpmIntent;
  if (options.simulationRequest) body.simulation_request = options.simulationRequest;
  if (Number.isInteger(options.availableMinutes)) body.available_minutes = options.availableMinutes;
  return streamJson("/counselor/chat", body, options);
}
```

Do not add an editable user-id or a free-form tool-call field. Preserve current SSE `sources`, `chunk`, `done`, and error behavior.

- [ ] **Step 4: Render answer provenance and server-built actions in `CounselorPage.jsx`**

Store final `meta` with each assistant message. Render a compact disclosure such as `已参考：当前状态（CORE、ACADEMIC、WORLD）· 未来趋势` and render `context_warnings` as non-alarmist text. Map action targets through a constant:

```javascript
const CPM_TARGET_PATHS = {
  "learning-state": "/learning-state",
  prediction: "/prediction",
  "learning-plan": "/learning-state?tab=plans",
  "student-goals": "/learning-state?tab=goals",
};

function handleCpmAction(action) {
  const path = CPM_TARGET_PATHS[action.target];
  if (path) navigate(path);
}
```

For `PROPOSE_PLAN_*`, label the button `查看并确认计划` and route to the plan screen. Do not show a button that claims an action has already been executed, and do not call `createTask`, plan decision, execute, or undo in `handleCpmAction`.

- [ ] **Step 5: Run client tests, production build, and targeted accessibility checks**

Run:

```powershell
cd webreact
node --test tests/counselor-world-model.test.mjs
npm test -- --run
npm run build
```

Expected: all tests pass and the build has no unhandled route/import errors.

- [ ] **Step 6: Commit the client transparency layer**

```powershell
git add webreact/src/data/api.js webreact/src/pages/CounselorPage.jsx webreact/tests/counselor-world-model.test.mjs
git diff --cached --check
git commit -m "feat(web): explain CPM world model context"
```

## Task 7: Add a true end-to-end CPM journey and regression-proof the boundaries

**Files:**
- Create: `webreact/tests/e2e/cpm-world-model-journey.py`
- Modify: `backend/tests/test_cpm_orchestrator.py`
- Modify: `backend/tests/test_counselor_cpm_world_model.py`
- Modify: `webreact/tests/counselor-world-model.test.mjs`

**Interfaces:**
- Consumes all Task 1–6 contracts.
- Produces a browser test that operates as two authenticated users, requests status/forecast/simulation/plan actions, uses only the existing confirmed plan pages for writes, sends explicit feedback, and verifies evidence after reprojection.

- [ ] **Step 1: Write the deterministic browser scenario before adding skips**

```python
def run_viewport(page, user, viewport):
    login(page, user)
    page.set_viewport_size(viewport)
    send_chat(page, "查看我的当前安排", intent="CURRENT_STATE_QUERY")
    expect(page.get_by_text("已参考：当前状态")).to_be_visible()
    expect(page.get_by_text("CORE、ACADEMIC、WORLD")).to_be_visible()

    send_chat(page, "未来七天会不会太忙？", intent="FORECAST_QUERY")
    page.get_by_role("button", name="查看趋势").click()
    expect(page).to_have_url(re.compile("/prediction"))

    response = api_simulate_same_origin(page, intervention="REDUCE_DAILY_LOAD")
    assert response["causal_claim"] is False
    assert response["baseline"] and response["simulated"] and response["delta"]

    send_chat(page, "给我安排本周行动", intent="PLAN_REQUEST", available_minutes=90)
    page.get_by_role("button", name="查看并确认计划").click()
    accept_and_execute_plan_via_existing_ui(page)
    submit_explicit_feedback(page, "HELPFUL")
    assert_reprojected_world_evidence(page)
```

Use `student_demo` for desktop and `student_demo_01` for mobile. Each must have its own session/database seed and must assert its displayed login identity before performing the flow.

- [ ] **Step 2: Run the new E2E test and confirm it fails at the first missing CPM assertion**

Run: `python webreact/tests/e2e/cpm-world-model-journey.py`

Expected: FAIL before Task 1–6 are implemented, not silently pass or conditionally skip.

- [ ] **Step 3: Implement test fixtures and hard assertions only**

The harness may start backend/Vite using the project's established command style, wait with bounded timeouts, then always terminate both subprocesses and remove only its own explicit temporary SQLite path. It must:

```python
assert "except AssertionError: pass" not in Path(__file__).read_text(encoding="utf-8")
assert "if not " not in critical_step_source
```

Do not seed rows through a separate SQLite connection after server startup; use existing demo seed endpoints or a service process invocation before starting the backend so the API and test see the same database. For cross-user assertions, request an existing plan/snapshot with the other user's token and assert a 404; do not infer isolation from a missing UI card.

- [ ] **Step 4: Run focused end-to-end and boundary regressions**

Run:

```powershell
cd backend
pytest tests/test_cpm_world_context.py tests/test_cpm_orchestrator.py tests/test_counselor_cpm_world_model.py tests/test_cpm_feedback_loop.py tests/test_cpm_shadow_capabilities.py -q
cd ..
python webreact/tests/e2e/cpm-world-model-journey.py
```

Expected: desktop and mobile both finish the same checked sequence; no action occurs without explicit UI confirmation.

- [ ] **Step 5: Commit only the validation additions**

```powershell
git add backend/tests/test_cpm_orchestrator.py backend/tests/test_counselor_cpm_world_model.py webreact/tests/counselor-world-model.test.mjs webreact/tests/e2e/cpm-world-model-journey.py
git diff --cached --check
git commit -m "test: verify CPM world model closed loop"
```

## Task 8: Run full verification, review exact diffs, and publish the implementation safely

**Files:**
- Modify only files required by fixes revealed by the following commands.
- Do not modify: `android/`, `harmony/`, `wx/`, `.github/workflows/`, visual navigation components, C-language deleted modules, or other sessions' files.

**Interfaces:**
- Acceptance is the spec's documented full loop; no new interface is introduced.

- [ ] **Step 1: Execute back-end, ML, and Web suites from clean tracked changes**

Run:

```powershell
cd backend
pytest -q
python -m compileall -q app
cd ..\ml\learner_state_evaluation
pytest -q
python -m compileall -q src
cd ..\..\webreact
npm test -- --run
npm run build
cd ..
python webreact/tests/e2e/cpm-world-model-journey.py
```

Expected: every command exits 0. Treat an existing Windows temp-directory cleanup warning as non-blocking only when pytest itself exits 0; do not describe a failed suite as passing.

- [ ] **Step 2: Run targeted safety scans and inspect artifacts**

Run:

```powershell
rg -n -i "c[_ -]?language|knowledge_band|read_knowledge_state|learning_summary_v1" backend webreact ml
rg -n -i "api[_-]?key|authorization:\s*bearer|password\s*=|token\s*=" backend webreact ml docs
git diff --check
git diff --cached --check
git status --short
```

Expected: the first scan has no active production references; any historical migration comment is reviewed manually and must not be registered for new capabilities. The credentials scan has no secret material. `git status` contains only this plan's intended files.

- [ ] **Step 3: Apply only demonstrated fixes and rerun the failed command**

For a contract failure, add a regression assertion in the closest Task 1–7 test before modifying production code. For a test fixture that refers to a deleted C-specific field, replace the field with `state_band` and keep the test's intended generic behavior. Do not restore a deleted subject-specific module merely to make an obsolete test green.

- [ ] **Step 4: Write the precise delivery statement into the final commit message/body**

```text
feat(cpm): complete explainable world model orchestration

CPM now uses safe CORE/ACADEMIC/WORLD context and deterministic forecast,
simulation and plan services. CampusMate-LM remains Shadow-only and all
writes continue through explicit user-confirmed business APIs.
```

- [ ] **Step 5: Make the final exact commit**

```powershell
$ownedPaths = git diff --name-only | Where-Object {
  $_ -match '^(backend/app/|backend/tests/|webreact/src/data/api\.js$|webreact/src/pages/CounselorPage\.jsx$|webreact/tests/|ml/learner_state_evaluation/)'
}
git add -- $ownedPaths
git diff --cached --check
git commit -m "feat(cpm): complete explainable world model orchestration"
git status --short
```

Before staging, use `git status --short` to list the exact task-owned paths; remove any unrelated path from `$ownedPaths` and stage filenames explicitly. The final status may contain user-owned unrelated changes, but no untracked local artifacts from this work.

## Self-Review

### Spec coverage

- Three projection families, freshness, bounded safe conversion, user isolation and partial-family degradation are Task 1.
- Fixed intent mapping, official Forecast/Simulation/Planner reuse, no free tools/writes and compatible response transparency are Tasks 2–3.
- Explicit-only feedback and re-projection are Task 4.
- Five generic capability contracts, strict read-only tool vocabulary, and Shadow-only behavior are Task 5.
- Web provenance, confirmation-only actions and no UI-mediated writes are Task 6.
- Desktop/mobile real journey, cross-user rejection, simulation proof, plan execution/undo and evidence validation are Task 7.
- Full suites, security scans, old deleted-contract repairs, exact staging and truthful delivery language are Task 8.

### Placeholder scan

The plan contains no `TODO`, `TBD`, “implement later”, “similar to Task”, ellipsis placeholders, or unspecified testing steps. Every test section names the test command and expected behavior; every production-code step names the input/output contract and its boundary conditions.

### Type consistency

`CpmWorldContextService.build_context` produces `CpmWorldContext`; `CpmOrchestrator.prepare` consumes it and produces `CpmOrchestrationResult`; the counselor route converts its `CpmSuggestedAction` instances into the existing compatible `SuggestedAction`; React consumes only `target`, never identifiers. The feedback contract is `CpmFeedbackRequest` through `CpmOrchestrator.record_feedback` to `LearnerEventService.record_cpm_feedback`. The five capability names are identical in Task 5 and all old learning-platform names are excluded from new production requests.

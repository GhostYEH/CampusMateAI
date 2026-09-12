from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ..core.exceptions import (
    AppException, InvalidTransition, LearningPlanExecutionFailed, LearningPlanExpired,
    LearningPlanIdempotencyConflict, LearningPlanStale, LearningPlanUndoConflict, NotFoundError,
)
from ..models.learning_plan import LearningPlanRow
from ..repositories.learning_plan_repository import LearningPlanRepository
from ..services.llm.base import LLMError

PLANNER_VERSION = "deterministic-learning-plan-v2"
PLAN_TTL = timedelta(minutes=15)
REJECTION_COOLDOWN = timedelta(hours=6)
MAX_TASKS = 200
MAX_CONTENT_PER_COURSE = 100
MAX_PLAN_ITEMS = 50
WEIGHTS = {
    "deadline_urgency": 0.30,
    "knowledge_need": 0.30,
    "evidence_confidence": 0.15,
    "prerequisite_readiness": 0.10,
    "estimated_effort_fit": 0.15,
    "source_freshness_penalty": 0.10,
}


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None:
        return None
    return result.astimezone(timezone.utc)


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()).hexdigest()


class LearningPlannerService:
    """Builds explainable plans from server-owned state and executes only stored items."""

    def __init__(self, *, repository: LearningPlanRepository, state_service, state_repository,
                 knowledge_service, knowledge_repository, task_repository, content_repository,
                 llm=None, source_policy=None) -> None:
        self.repository = repository
        self.state_service = state_service
        self.state_repository = state_repository
        self.knowledge_service = knowledge_service
        self.knowledge_repository = knowledge_repository
        self.task_repository = task_repository
        self.content_repository = content_repository
        self.llm = llm
        self._source_policy = source_policy

    def generate(self, *, user_id: str, available_minutes: int, course_id: str | None = None,
                 window_start: str | None = None, window_end: str | None = None,
                 idempotency_key: str | None = None, as_of: datetime | None = None,
                 force_new: bool = False, supersedes_plan_id: str | None = None,
                 replan_key: str | None = None, ignore_rejection: bool = False) -> LearningPlanRow:
        now = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
        if course_id and not self.knowledge_repository.user_can_access_course(user_id=user_id, course_id=course_id):
            raise NotFoundError()
        if window_start and _parse(window_start) is None:
            raise ValueError("window_start must be timezone-aware ISO 8601")
        if window_end and _parse(window_end) is None:
            raise ValueError("window_end must be timezone-aware ISO 8601")
        if window_start and window_end and _parse(window_end) <= _parse(window_start):
            raise ValueError("window_end must be after window_start")

        if self._source_policy is not None and self._source_policy.should_skip_proactive_suggestions(user_id=user_id):
            raise InvalidTransition("主动建议已被暂停")

        core = self.state_service.project_user(user_id, as_of=now, trigger="learning_plan")
        academic = self.state_service.project_academic(
            user_id, as_of=now, trigger="learning_plan"
        )
        tasks, task_total = self.task_repository.list_tasks(user_id, page=1, page_size=MAX_TASKS)
        warnings = list(core.warnings)
        if any(s.data_quality in {"stale", "partial", "unavailable"} for s in core.snapshots):
            warnings.append("data_quality_partial")
        if task_total > MAX_TASKS:
            warnings.append("tasks_truncated")
        tasks = [task for task in tasks if task.status == "pending" and not task.deleted_at]
        courses = {task.course_id for task in tasks if task.course_id}
        if course_id:
            courses = {course_id}
            tasks = [task for task in tasks if task.course_id in {None, course_id}]
        course_data: dict[str, list[Any]] = {}
        knowledge_data: dict[str, tuple[Any, list[Any]]] = {}
        prediction_data: dict[str, Any] = {}
        counterfactual_data: dict[str, dict[str, Any]] = {}
        for cid in sorted(courses):
            items = self.content_repository.list_items(
                user_id=user_id, course_id=cid, include_stale=True, page=1, page_size=MAX_CONTENT_PER_COURSE
            )
            if len(items) >= MAX_CONTENT_PER_COURSE and self.content_repository.count_items(user_id=user_id, course_id=cid) > MAX_CONTENT_PER_COURSE:
                warnings.append("course_content_truncated")
            course_data[cid] = items[:MAX_CONTENT_PER_COURSE]
            if any(x.is_stale for x in items):
                warnings.append("course_content_stale")
            try:
                if not self.knowledge_repository.user_can_access_course(user_id=user_id, course_id=cid):
                    continue
                knowledge = self.knowledge_service.project_knowledge(user_id=user_id, course_id=cid, as_of=now, trigger="learning_plan")
                knowledge_data[cid] = (knowledge, knowledge.snapshots)
                warnings.extend(knowledge.warnings)
                if any(s.data_quality in {"stale", "partial", "unavailable"} for s in knowledge.snapshots):
                    warnings.append("knowledge_data_quality_partial")
                prediction = self.state_service.project_prediction(
                    user_id, course_id=cid, as_of=now, trigger="learning_plan"
                )
                prediction_data[cid] = prediction
                warnings.extend(prediction.warnings)
                target_codes = sorted({s.scope_id for s in knowledge.snapshots})
                if target_codes:
                    counterfactual_data[cid] = self.state_service.simulate_counterfactual(
                        user_id,
                        course_id=cid,
                        as_of=now,
                        intervention={
                            "intervention_type": "additional_practice",
                            "knowledge_component_code": target_codes[0],
                            "additional_practice_count": 3,
                            "expected_score": 75.0,
                            "misconception_code": None,
                        },
                    )
            except Exception:
                warnings.append("knowledge_unavailable")

        core_inputs = {
            "run_id": core.run_id,
            "snapshots": [{"scope_type": s.scope_type, "scope_id": s.scope_id, "state_type": s.state_type,
                           "value": {k: v for k, v in (s.value or {}).items() if k not in {"valid_until", "computed_at"}},
                           "confidence": s.confidence, "data_quality": s.data_quality}
                          for s in sorted(core.snapshots, key=lambda x: (x.scope_type, x.scope_id, x.state_type))],
        }
        safe_tasks = [self._task_summary(t) for t in tasks]
        safe_content = {cid: [{"id": x.id, "external_id": x.external_id, "kind": x.kind, "deadline": x.deadline,
                               "published_at": x.published_at, "last_synced_at": x.last_synced_at, "is_stale": x.is_stale}
                              for x in rows] for cid, rows in course_data.items()}
        safe_knowledge = {cid: {"run_id": data[0].run_id, "snapshots": [
            {"scope_id": s.scope_id, "value": s.value, "confidence": s.confidence, "data_quality": s.data_quality,
             "valid_until": s.valid_until} for s in data[1]]} for cid, data in knowledge_data.items()}
        for value in safe_knowledge.values():
            value["snapshots"] = sorted(value["snapshots"], key=lambda x: x["scope_id"])
        safe_academic = {
            "run_id": academic.run_id,
            "snapshots": [
                {"state_type": s.state_type, "value": s.value, "confidence": s.confidence,
                 "data_quality": s.data_quality, "valid_until": s.valid_until}
                for s in sorted(academic.snapshots, key=lambda x: x.state_type)
            ],
        }
        safe_predictions = {
            cid: {"run_id": result.run_id, "snapshots": [
                {"scope_id": s.scope_id, "state_type": s.state_type, "value": s.value,
                 "confidence": s.confidence, "data_quality": s.data_quality,
                 "valid_until": s.valid_until}
                for s in sorted(result.snapshots, key=lambda x: (x.scope_id, x.state_type))
            ]}
            for cid, result in prediction_data.items()
        }
        safe_counterfactuals = {
            cid: {
                "deltas": value.get("deltas", []),
                "warning_codes": value.get("warning_codes", []),
                "explanation_codes": value.get("explanation_codes", []),
            }
            for cid, value in counterfactual_data.items()
        }
        input_digest = _digest({"planner_version": PLANNER_VERSION, "core": core_inputs, "tasks": safe_tasks,
                                "content": safe_content, "knowledge": safe_knowledge,
                                "academic": safe_academic, "predictions": safe_predictions,
                                "counterfactuals": safe_counterfactuals,
                                "available_minutes": available_minutes,
                                "course_id": course_id, "window_start": window_start, "window_end": window_end,
                                "time_bucket": now.replace(minute=0, second=0).isoformat(), "parameters": WEIGHTS})
        if idempotency_key:
            existing = self.repository.find_by_idempotency_key(user_id=user_id, idempotency_key=idempotency_key)
            if existing:
                if existing.run.input_digest != input_digest:
                    raise LearningPlanIdempotencyConflict()
                return existing
        reusable = None if force_new else self.repository.find_reusable(
            user_id=user_id, planner_version=PLANNER_VERSION, input_digest=input_digest, as_of=_iso(now)
        )
        if reusable:
            return reusable
        if not ignore_rejection and self.repository.has_recent_rejection(user_id=user_id, input_digest=input_digest,
                                                since=_iso(now - REJECTION_COOLDOWN)):
            raise InvalidTransition("相同建议仍在拒绝冷却期内")

        items = self._build_items(
            tasks, course_data, knowledge_data, prediction_data,
            counterfactual_data, academic.snapshots, available_minutes, now,
        )
        items = items[:MAX_PLAN_ITEMS]
        if len(items) >= MAX_PLAN_ITEMS:
            warnings.append("plan_items_truncated")
        valid_until = min(now + PLAN_TTL, self._next_hour(now))
        for knowledge, snapshots in knowledge_data.values():
            for snapshot in snapshots:
                boundary = _parse(snapshot.valid_until)
                if boundary:
                    valid_until = min(valid_until, boundary)
        for result in [academic, *prediction_data.values()]:
            for snapshot in result.snapshots:
                boundary = _parse(snapshot.valid_until)
                if boundary:
                    valid_until = min(valid_until, boundary)
        allocated = 0
        selected = []
        for item in sorted(items, key=lambda x: (-x["priority_score"], x.get("course_id") or "", x.get("task_id") or "", x.get("knowledge_component_code") or "")):
            if allocated + item["estimated_minutes"] > available_minutes:
                continue
            allocated += item["estimated_minutes"]
            selected.append(item)
        if any(w in {"stale", "partial", "data_quality_partial", "knowledge_data_quality_partial", "input_truncated", "course_content_truncated", "course_content_stale", "knowledge_unavailable"} for w in warnings):
            warnings.append("data_quality_degraded")
        selected_task_bindings = {item["task_id"]: self._task_summary_digest(next(t for t in tasks if t.id == item["task_id"]))
                                  for item in selected if item.get("task_id")}
        selected_knowledge_bindings = {}
        for cid, (knowledge, snapshots) in knowledge_data.items():
            selected_codes = {item.get("knowledge_component_code") for item in selected if item.get("course_id") == cid}
            selected_knowledge_bindings[cid] = {
                "run_id": knowledge.run_id,
                "input_digest": knowledge.input_digest,
                "prediction_input_digest": getattr(
                    prediction_data.get(cid), "input_digest", None
                ),
                "snapshots": {s.scope_id: self._knowledge_snapshot_digest(s) for s in snapshots if s.scope_id in selected_codes},
                "quality": {s.scope_id: s.data_quality for s in snapshots if s.scope_id in selected_codes},
            }
        selected_knowledge_bindings["__academic__"] = {
            "input_digest": getattr(academic, "input_digest", None),
            "quality": {
                s.state_type: s.data_quality for s in academic.snapshots
            },
        }
        truncated = any(code in {"tasks_truncated", "course_content_truncated", "plan_items_truncated", "input_truncated", "evidence_truncated"} for code in warnings)
        # Reusable plans are selected by the digest; run IDs must remain fresh
        # when an identical input becomes eligible again after expiry.
        run_id = f"lprun_{uuid.uuid4().hex[:16]}"
        run = {"run_id": run_id,
               "planner_version": PLANNER_VERSION, "input_digest": input_digest, "as_of": _iso(now),
               "valid_until": _iso(valid_until), "available_minutes": available_minutes, "allocated_minutes": allocated,
               "course_scope": course_id, "window_start": window_start, "window_end": window_end,
               "warning_codes": sorted(set(warnings)), "idempotency_key": idempotency_key,
               "core_run_id": core.run_id, "core_input_digest": core.input_digest,
               "knowledge_bindings": selected_knowledge_bindings,
               "task_binding_digest": _digest(selected_task_bindings),
               "task_bindings": selected_task_bindings, "input_truncated": truncated,
               "core_quality": "unavailable" if any(s.data_quality == "unavailable" for s in core.snapshots) else (
                   "stale" if any(s.data_quality == "stale" for s in core.snapshots) else (
                       "partial" if any(s.data_quality == "partial" for s in core.snapshots) else "verified"
                   )
               ),
               "supersedes_plan_id": supersedes_plan_id, "replan_key": replan_key}
        for item in selected:
            item_key = [run["run_id"], item["item_type"], item.get("task_id"), item.get("knowledge_component_code")]
            item["item_id"] = f"lpitem_{_digest(item_key)[:16]}"
        return self.repository.create_plan(user_id=user_id, run=run, items=selected)

    @staticmethod
    def _task_summary(task) -> dict[str, Any]:
        return {"id": task.id, "course_id": task.course_id, "deadline": task.deadline,
                "priority": task.priority, "importance": task.importance, "status": task.status,
                "completed_at": task.completed_at, "deleted_at": task.deleted_at,
                "source": task.source, "external_id": task.external_id,
                "title_digest": hashlib.sha256(task.title.encode("utf-8")).hexdigest()}

    @classmethod
    def _task_summary_digest(cls, task) -> str:
        return _digest(cls._task_summary(task))

    @staticmethod
    def _knowledge_snapshot_digest(snapshot) -> str:
        value = snapshot.value or {}
        # A new knowledge run is not itself a stale signal.  Replanning is
        # required only when the bound KC estimate/band changed; quality is
        # checked separately below so confidence metadata cannot cause churn.
        return _digest({"scope_id": snapshot.scope_id, "estimate": value.get("estimate"),
                        "band": value.get("band")})

    @staticmethod
    def _quality_rank(value: str | None) -> int:
        return {"verified": 0, "partial": 1, "stale": 2, "unavailable": 3}.get(value or "unavailable", 3)

    @staticmethod
    def _next_hour(now: datetime) -> datetime:
        return (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

    def _build_items(
        self, tasks, content_data, knowledge_data, prediction_data,
        counterfactual_data, academic_snapshots, available: int, now: datetime,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        exam_snapshot = next(
            (s for s in academic_snapshots if s.state_type == "exam_exposure"), None
        )
        if exam_snapshot is not None and exam_snapshot.data_quality != "unavailable":
            upcoming = int((exam_snapshot.value or {}).get("upcoming_exam_count", 0))
            if upcoming > 0:
                item = self._item_base(
                    estimated=30, urgency=min(1.0, 0.55 + upcoming * 0.1), need=0.35,
                    confidence=exam_snapshot.confidence, readiness=1.0,
                    fit=min(1.0, available / 30), freshness=0.0,
                )
                item.update(
                    item_type="ACADEMIC_PREPARATION", course_id=None,
                    explanation_codes=["upcoming_exam_exposure"],
                    evidence=[{
                        "evidence_type": "ACADEMIC_SNAPSHOT",
                        "reference_id": exam_snapshot.snapshot_id,
                        "metadata": {"relation": "SUPPORTS", "data_quality": exam_snapshot.data_quality},
                    }],
                )
                items.append(item)
        for task in tasks:
            urgency = self._deadline_urgency(task.deadline, now)
            freshness = self._freshness_penalty(task.last_synced_at, now)
            item = self._item_base(estimated=30, urgency=urgency, need=0.2, confidence=0.35,
                                   readiness=1.0, fit=min(1.0, available / 30), freshness=freshness)
            item.update(item_type="TASK_FOCUS", course_id=task.course_id, task_id=task.id,
                        explanation_codes=["pending_personal_task"] + (["deadline_urgent"] if urgency >= .75 else []),
                        evidence=[{"evidence_type": "PERSONAL_TASK", "reference_id": task.id,
                                   "metadata": {"relation": "SUPPORTS"}}])
            items.append(item)
        for cid, pair in knowledge_data.items():
            knowledge, snapshots = pair
            contents = content_data.get(cid, [])
            for snapshot in snapshots:
                value = snapshot.value or {}
                evidence_count = int(value.get("evidence_count", 0))
                estimate = float(value.get("estimate", 0.5))
                need = 0.25 if evidence_count == 0 else max(0.0, min(1.0, 1.0 - estimate))
                confidence = snapshot.confidence if snapshot.data_quality not in {"stale", "unavailable"} else .25

                prediction = next(
                    (
                        s for s in getattr(prediction_data.get(cid), "snapshots", [])
                        if s.scope_id == snapshot.scope_id
                        and s.state_type == "performance_prediction"
                    ),
                    None,
                )
                predicted_probability = None
                if prediction is not None and prediction.data_quality != "unavailable":
                    predicted_probability = float(
                        (prediction.value or {}).get("predicted_pass_probability", 0.5)
                    )
                    need = max(need, 1.0 - predicted_probability)
                    confidence = min(confidence, max(0.1, prediction.confidence))

                readiness = self._prerequisite_readiness(snapshot.scope_id, snapshots)
                freshness = .4 if any(x.is_stale for x in contents) else 0.0
                codes = ["diagnostic_or_review_recommended"] if evidence_count == 0 else ["practice_evidence"]
                if evidence_count and estimate < .45:
                    codes.append("knowledge_need")
                if readiness < .5:
                    codes.append("prerequisite_gap")
                if predicted_probability is not None and predicted_probability < .7:
                    codes.append("prediction_low_pass_probability")
                evidence = [{"evidence_type": "KNOWLEDGE_SNAPSHOT", "reference_id": snapshot.snapshot_id,
                             "metadata": {"relation": "SUPPORTS", "data_quality": snapshot.data_quality}}]
                if prediction is not None:
                    evidence.append({
                        "evidence_type": "PREDICTION_SNAPSHOT",
                        "reference_id": prediction.snapshot_id,
                        "metadata": {"relation": "SUPPORTS", "data_quality": prediction.data_quality},
                    })
                deltas = counterfactual_data.get(cid, {}).get("deltas", [])
                matching_delta = next(
                    (d for d in deltas if d.get("knowledge_component_code") == snapshot.scope_id),
                    None,
                )
                if matching_delta and float(matching_delta.get("pass_probability_delta", 0.0)) > 0:
                    codes.append("counterfactual_practice_benefit")
                if contents:
                    evidence.append({"evidence_type": "COURSE_MATERIAL", "reference_id": contents[0].id,
                                     "relevance_score": 1.0, "metadata": {"relation": "SUPPORTS"}})
                item = self._item_base(estimated=20 if evidence_count else 15, urgency=.2, need=need,
                                       confidence=confidence, readiness=readiness,
                                       fit=min(1.0, available / (20 if evidence_count else 15)), freshness=freshness)
                item.update(item_type="KNOWLEDGE_REVIEW" if evidence_count else "CREATE_PERSONAL_TASK",
                            course_id=cid, knowledge_component_code=snapshot.scope_id,
                            explanation_codes=codes, evidence=evidence)
                items.append(item)
        return items

    @staticmethod
    def _item_base(*, estimated: int, urgency: float, need: float, confidence: float,
                   readiness: float, fit: float, freshness: float) -> dict[str, Any]:
        components = {"deadline_urgency": round(urgency, 6), "knowledge_need": round(need, 6),
                      "evidence_confidence": round(confidence, 6), "prerequisite_readiness": round(readiness, 6),
                      "estimated_effort_fit": round(fit, 6), "source_freshness_penalty": round(freshness, 6)}
        score = sum(components[name] * weight for name, weight in WEIGHTS.items() if name != "source_freshness_penalty") - freshness * WEIGHTS["source_freshness_penalty"]
        return {"estimated_minutes": estimated, "priority_score": round(score, 6), "priority_components": components,
                "explanation_codes": [], "evidence": []}

    @staticmethod
    def _deadline_urgency(value: str | None, now: datetime) -> float:
        deadline = _parse(value)
        if deadline is None:
            return .1
        hours = (deadline - now).total_seconds() / 3600
        if hours <= 0: return 1.0
        if hours <= 24: return .9
        if hours <= 72: return .7
        if hours <= 168: return .45
        return .2

    @staticmethod
    def _freshness_penalty(value: str | None, now: datetime) -> float:
        synced = _parse(value)
        if synced is None: return .25
        age = max(0.0, (now - synced).total_seconds() / 86400)
        return min(1.0, age / 30.0)

    def _prerequisite_readiness(self, code: str, snapshots: list[Any]) -> float:
        target = next((s for s in snapshots if s.scope_id == code), None)
        if target is None:
            return .5
        component = self.knowledge_repository.get_component(code)
        prerequisites = component.prerequisite_codes if component else []
        if not prerequisites:
            return 1.0
        by_code = {s.scope_id: s for s in snapshots}
        readiness = []
        for prerequisite in prerequisites:
            state = by_code.get(prerequisite)
            if state is None:
                readiness.append(.5)
                continue
            value = state.value or {}
            if int(value.get("evidence_count", 0)) == 0:
                readiness.append(.7)
            else:
                readiness.append(float(value.get("estimate", .5)))
        return round(sum(readiness) / len(readiness), 6) if readiness else 1.0

    async def enhance_with_llm(self, plan: LearningPlanRow) -> LearningPlanRow:
        if self.llm is None or not getattr(self.llm, "available", False):
            return plan
        allowed = {"plan_id": plan.plan_id, "items": [{"item_id": x.item_id, "codes": x.explanation_codes} for x in plan.items]}
        try:
            response = await asyncio.wait_for(self.llm.chat([
                {"role": "system", "content": "只将已给出的解释码转写为简短说明；不得新增事实。返回 JSON: {summary:string}"},
                {"role": "user", "content": json.dumps(allowed, ensure_ascii=False)},
            ], temperature=0, max_tokens=160, timeout=3), timeout=4)
            data = json.loads(response.content)
            summary = data.get("summary") if isinstance(data, dict) else None
            if not isinstance(summary, str) or not summary.strip() or len(summary) > 500:
                return plan
            return self.repository.set_llm_summary(plan_id=plan.plan_id, user_id=plan.user_id, summary=summary.strip()) or plan
        except (LLMError, asyncio.TimeoutError, ValueError, TypeError, json.JSONDecodeError):
            return plan

    def decide(self, *, user_id: str, plan_id: str, decision: str) -> LearningPlanRow:
        plan = self.repository.get_plan(plan_id, user_id=user_id)
        if plan is None: raise NotFoundError()
        if plan.status != "PROPOSED": raise InvalidTransition("计划当前状态不允许确认")
        self.repository.add_decision(plan_id=plan_id, user_id=user_id, decision=decision)
        return self.repository.update_status(plan_id=plan_id, user_id=user_id, status="ACCEPTED" if decision == "ACCEPT" else "REJECTED")  # type: ignore[return-value]

    def execute(self, *, user_id: str, plan_id: str) -> LearningPlanRow:
        plan = self.repository.get_plan(plan_id, user_id=user_id)
        if plan is None: raise NotFoundError()
        if plan.status == "EXECUTED":
            return plan
        if plan.status == "PROPOSED": raise InvalidTransition("计划尚未接受")
        if plan.status == "EXPIRED": raise LearningPlanExpired()
        if plan.status == "STALE": raise LearningPlanStale()
        if plan.status in {"REJECTED", "UNDONE", "SUPERSEDED"}: raise InvalidTransition("当前计划状态不能执行")
        if _parse(plan.run.valid_until) and datetime.now(timezone.utc) >= _parse(plan.run.valid_until):
            self.repository.update_status(plan_id=plan_id, user_id=user_id, status="EXPIRED")
            raise LearningPlanExpired()
        self._check_freshness(plan, user_id=user_id)
        try:
            self.repository.execute_atomic(plan_id=plan_id, user_id=user_id, task_repository=self.task_repository)
        except (LearningPlanStale, LearningPlanExpired, AppException):
            raise
        except Exception as exc:
            raise LearningPlanExecutionFailed() from exc
        return self.repository.get_plan(plan_id, user_id=user_id)  # type: ignore[return-value]

    def undo(self, *, user_id: str, plan_id: str) -> LearningPlanRow:
        plan = self.repository.get_plan(plan_id, user_id=user_id)
        if plan is None: raise NotFoundError()
        if plan.status == "UNDONE": return plan
        if plan.status not in {"EXECUTED", "PARTIALLY_EXECUTED"}: raise InvalidTransition("计划当前状态不能撤销")
        try:
            conflict = self.repository.undo_atomic(plan_id=plan_id, user_id=user_id, task_repository=self.task_repository)
        except Exception as exc:
            raise LearningPlanExecutionFailed() from exc
        if conflict:
            raise LearningPlanUndoConflict()
        return self.repository.get_plan(plan_id, user_id=user_id)  # type: ignore[return-value]

    def _check_freshness(self, plan: LearningPlanRow, *, user_id: str) -> None:
        now = datetime.now(timezone.utc)
        if plan.run.planner_version != PLANNER_VERSION:
            self.repository.mark_stale(plan_id=plan.plan_id, user_id=user_id, reason="planner_version")
            raise LearningPlanStale()
        current_core = self.state_service.project_user(user_id, as_of=now, trigger="learning_plan_revalidate")
        if plan.run.core_input_digest and current_core.input_digest != plan.run.core_input_digest:
            self.repository.mark_stale(plan_id=plan.plan_id, user_id=user_id, reason="core_input_changed")
            raise LearningPlanStale()
        current_core_quality = "unavailable" if any(s.data_quality == "unavailable" for s in current_core.snapshots) else (
            "stale" if any(s.data_quality == "stale" for s in current_core.snapshots) else (
                "partial" if any(s.data_quality == "partial" for s in current_core.snapshots) else "verified"
            )
        )
        if self._quality_rank(current_core_quality) > self._quality_rank(plan.run.core_quality):
            self.repository.mark_stale(plan_id=plan.plan_id, user_id=user_id, reason="core_quality_worsened")
            raise LearningPlanStale()
        for item in plan.items:
            if not item.task_id:
                continue
            task = self.task_repository.get_task(item.task_id, user_id=user_id)
            if task is None or task.status != "pending" or task.deleted_at:
                self.repository.mark_stale(plan_id=plan.plan_id, user_id=user_id, reason="task_state_changed")
                raise LearningPlanStale()
            expected = plan.run.task_bindings.get(item.task_id)
            if expected and self._task_summary_digest(task) != expected:
                self.repository.mark_stale(plan_id=plan.plan_id, user_id=user_id, reason="task_semantics_changed")
                raise LearningPlanStale()
        academic_binding = plan.run.knowledge_bindings.get("__academic__", {})
        if academic_binding.get("input_digest"):
            current_academic = self.state_service.project_academic(
                user_id, as_of=now, trigger="learning_plan_revalidate"
            )
            if current_academic.input_digest != academic_binding["input_digest"]:
                self.repository.mark_stale(
                    plan_id=plan.plan_id, user_id=user_id,
                    reason="academic_state_changed",
                )
                raise LearningPlanStale()
        for cid, binding in plan.run.knowledge_bindings.items():
            if cid == "__academic__":
                continue
            knowledge = self.knowledge_service.project_knowledge(user_id=user_id, course_id=cid, as_of=now,
                                                                 trigger="learning_plan_revalidate")
            current_by_code = {s.scope_id: s for s in knowledge.snapshots}
            for code, expected in binding.get("snapshots", {}).items():
                current = current_by_code.get(code)
                if current is None or self._knowledge_snapshot_digest(current) != expected:
                    self.repository.mark_stale(plan_id=plan.plan_id, user_id=user_id, reason="knowledge_state_changed")
                    raise LearningPlanStale()
            if any(current_by_code.get(code) and self._quality_rank(current_by_code[code].data_quality) >
                   self._quality_rank(binding.get("quality", {}).get(code))
                   for code in binding.get("snapshots", {})):
                self.repository.mark_stale(plan_id=plan.plan_id, user_id=user_id, reason="data_quality_worsened")
                raise LearningPlanStale()
            if binding.get("prediction_input_digest"):
                prediction = self.state_service.project_prediction(
                    user_id, course_id=cid, as_of=now,
                    trigger="learning_plan_revalidate",
                )
                if prediction.input_digest != binding["prediction_input_digest"]:
                    self.repository.mark_stale(
                        plan_id=plan.plan_id, user_id=user_id,
                        reason="prediction_state_changed",
                    )
                    raise LearningPlanStale()

    def replan(self, *, user_id: str, plan_id: str, idempotency_key: str | None = None) -> LearningPlanRow:
        old = self.repository.get_plan(plan_id, user_id=user_id)
        if old is None:
            raise NotFoundError()
        key = idempotency_key or f"replan:{plan_id}"
        existing = self.repository.find_by_idempotency_key(user_id=user_id, idempotency_key=key)
        if existing:
            return existing
        result = self.generate(
            user_id=user_id, available_minutes=old.run.available_minutes, course_id=old.run.course_scope,
            window_start=old.run.window_start, window_end=old.run.window_end, idempotency_key=key,
            force_new=True, supersedes_plan_id=plan_id, replan_key=key, ignore_rejection=True,
        )
        self.repository.link_superseded(old_plan_id=plan_id, new_plan_id=result.plan_id, user_id=user_id, replan_key=key)
        return self.repository.get_plan(result.plan_id, user_id=user_id)  # type: ignore[return-value]

    def record_feedback(self, *, user_id: str, plan_id: str, feedback: str) -> str:
        if self.repository.get_plan(plan_id, user_id=user_id) is None:
            raise NotFoundError()
        return self.repository.add_feedback(plan_id=plan_id, user_id=user_id, feedback=feedback)

    def evaluate(self, *, user_id: str, plan_id: str) -> dict[str, Any]:
        plan = self.repository.get_plan(plan_id, user_id=user_id)
        if plan is None:
            raise NotFoundError()
        from ..services.learner_state_service import _parse as parse_state_time
        baseline = _parse(plan.run.as_of) or parse_state_time(plan.run.as_of)
        evaluated = datetime.now(timezone.utc)
        events, total_events = self._event_repository().list_for_user(
            user_id=user_id, event_type="practice_answered", since=baseline, until=evaluated, page=1, page_size=100
        )
        action_rows = self.repository.list_actions(plan_id=plan_id, user_id=user_id)
        planned = len(plan.items)
        executed = sum(1 for item in plan.items if item.execution_status == "SUCCEEDED" or any(
            action.item_id == item.item_id and action.status == "SUCCEEDED" for action in action_rows
        ))
        completed_tasks = 0
        for action in action_rows:
            if action.target_task_id:
                task = self.task_repository.get_task(action.target_task_id, user_id=user_id)
                if task and task.source == "learning_plan" and task.status == "completed":
                    completed_tasks += 1
        evidence_count = sum(len(item.evidence) for item in plan.items)
        evidence_coverage = round(min(1.0, evidence_count / planned), 6) if planned else 0.0
        supported = sum(1 for event in events if event.data_quality in {"verified", "partial"})
        warnings = list(plan.run.warning_codes)
        if total_events > 100:
            warnings.append("followup_events_truncated")
        if any(event.data_quality in {"partial", "unverified", "stale"} for event in events):
            warnings.append("followup_evidence_partial")
        if plan.run.input_truncated:
            warnings.append("plan_input_truncated")
        status = "OUTCOME_OBSERVED" if events else "INSUFFICIENT_EVIDENCE"
        metrics = {
            "evaluation_status": status, "planned_item_count": planned, "executed_item_count": executed,
            "completed_plan_task_count": completed_tasks, "followup_practice_count": len(events),
            "supported_outcome_count": supported, "evidence_coverage": evidence_coverage,
        }
        input_digest = _digest({"plan_id": plan_id, "items": [(x.item_id, x.execution_status) for x in plan.items],
                                "actions": [(x.action_id, x.status, x.target_task_id) for x in action_rows],
                                "events": [(x.event_id, x.occurred_at, x.data_quality) for x in events],
                                "warnings": sorted(set(warnings))})
        version = "learning-plan-observational-v1"
        existing = self.repository.get_latest_evaluation(plan_id=plan_id, user_id=user_id,
                                                         evaluator_version=version, input_digest=input_digest)
        if existing:
            metrics = json.loads(existing["metrics_json"])
            warnings = json.loads(existing["warning_codes_json"] or "[]")
            baseline_value, evaluated_value = existing["baseline_as_of"], existing["evaluated_as_of"]
        else:
            baseline_value, evaluated_value = plan.run.as_of, _iso(evaluated)
            self.repository.add_evaluation(plan_id=plan_id, user_id=user_id, evaluator_version=version,
                                           input_digest=input_digest, baseline_as_of=baseline_value,
                                           evaluated_as_of=evaluated_value, metrics=metrics, warning_codes=warnings)
        return {"plan_id": plan_id, **metrics, "baseline_as_of": baseline_value,
                "evaluated_as_of": evaluated_value, "warning_codes": sorted(set(warnings)),
                "evaluator_version": version}

    def _event_repository(self):
        return self.knowledge_service.event_repository


__all__ = ["LearningPlannerService", "PLANNER_VERSION", "WEIGHTS"]

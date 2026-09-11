from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from ..core.exceptions import Forbidden, InvalidTransition, NotFoundError
from ..models.learning_plan import LearningPlanRow
from ..repositories.learning_plan_repository import LearningPlanRepository
from ..services.llm.base import LLMError

PLANNER_VERSION = "deterministic-learning-plan-v1"
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
                 llm=None) -> None:
        self.repository = repository
        self.state_service = state_service
        self.state_repository = state_repository
        self.knowledge_service = knowledge_service
        self.knowledge_repository = knowledge_repository
        self.task_repository = task_repository
        self.content_repository = content_repository
        self.llm = llm

    def generate(self, *, user_id: str, available_minutes: int, course_id: str | None = None,
                 window_start: str | None = None, window_end: str | None = None,
                 idempotency_key: str | None = None, as_of: datetime | None = None) -> LearningPlanRow:
        now = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
        if course_id and not self.knowledge_repository.user_can_access_course(user_id=user_id, course_id=course_id):
            raise NotFoundError()
        if window_start and _parse(window_start) is None:
            raise ValueError("window_start must be timezone-aware ISO 8601")
        if window_end and _parse(window_end) is None:
            raise ValueError("window_end must be timezone-aware ISO 8601")
        if window_start and window_end and _parse(window_end) <= _parse(window_start):
            raise ValueError("window_end must be after window_start")

        core = self.state_service.project_user(user_id, as_of=now, trigger="learning_plan")
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
            except Exception:
                warnings.append("knowledge_unavailable")

        core_inputs = {
            "run_id": core.run_id,
            "snapshots": [{"scope_type": s.scope_type, "scope_id": s.scope_id, "state_type": s.state_type,
                           "value": {k: v for k, v in (s.value or {}).items() if k not in {"valid_until", "computed_at"}},
                           "confidence": s.confidence, "data_quality": s.data_quality}
                          for s in sorted(core.snapshots, key=lambda x: (x.scope_type, x.scope_id, x.state_type))],
        }
        safe_tasks = [{"id": t.id, "course_id": t.course_id, "deadline": t.deadline, "priority": t.priority,
                       "importance": t.importance, "status": t.status, "updated_at": t.updated_at,
                       "source": t.source, "last_synced_at": t.last_synced_at} for t in tasks]
        safe_content = {cid: [{"id": x.id, "external_id": x.external_id, "kind": x.kind, "deadline": x.deadline,
                               "published_at": x.published_at, "last_synced_at": x.last_synced_at, "is_stale": x.is_stale}
                              for x in rows] for cid, rows in course_data.items()}
        safe_knowledge = {cid: {"run_id": data[0].run_id, "snapshots": [
            {"scope_id": s.scope_id, "value": s.value, "confidence": s.confidence, "data_quality": s.data_quality,
             "valid_until": s.valid_until} for s in data[1]]} for cid, data in knowledge_data.items()}
        for value in safe_knowledge.values():
            value["snapshots"] = sorted(value["snapshots"], key=lambda x: x["scope_id"])
        input_digest = _digest({"planner_version": PLANNER_VERSION, "core": core_inputs, "tasks": safe_tasks,
                                "content": safe_content, "knowledge": safe_knowledge, "available_minutes": available_minutes,
                                "course_id": course_id, "window_start": window_start, "window_end": window_end,
                                "time_bucket": now.replace(minute=0, second=0).isoformat(), "parameters": WEIGHTS})
        if idempotency_key:
            existing = self.repository.find_by_idempotency_key(user_id=user_id, idempotency_key=idempotency_key)
            if existing:
                if existing.run.input_digest != input_digest:
                    raise InvalidTransition("idempotency key 已用于不同的计划输入")
                return existing
        reusable = self.repository.find_reusable(user_id=user_id, planner_version=PLANNER_VERSION,
                                                 input_digest=input_digest, as_of=_iso(now))
        if reusable:
            return reusable
        if self.repository.has_recent_rejection(user_id=user_id, input_digest=input_digest,
                                                since=_iso(now - REJECTION_COOLDOWN)):
            raise InvalidTransition("相同建议仍在拒绝冷却期内")

        items = self._build_items(tasks, course_data, knowledge_data, available_minutes, now)
        items = items[:MAX_PLAN_ITEMS]
        if len(items) >= MAX_PLAN_ITEMS:
            warnings.append("plan_items_truncated")
        valid_until = min(now + PLAN_TTL, self._next_hour(now))
        for knowledge, snapshots in knowledge_data.values():
            for snapshot in snapshots:
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
        run = {"run_id": f"lprun_{_digest([user_id, input_digest, now.isoformat()])[:16]}",
               "planner_version": PLANNER_VERSION, "input_digest": input_digest, "as_of": _iso(now),
               "valid_until": _iso(valid_until), "available_minutes": available_minutes, "allocated_minutes": allocated,
               "course_scope": course_id, "window_start": window_start, "window_end": window_end,
               "warning_codes": sorted(set(warnings)), "idempotency_key": idempotency_key}
        for item in selected:
            item_key = [run["run_id"], item["item_type"], item.get("task_id"), item.get("knowledge_component_code")]
            item["item_id"] = f"lpitem_{_digest(item_key)[:16]}"
        return self.repository.create_plan(user_id=user_id, run=run, items=selected)

    @staticmethod
    def _next_hour(now: datetime) -> datetime:
        return (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

    def _build_items(self, tasks, content_data, knowledge_data, available: int, now: datetime) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
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
                readiness = self._prerequisite_readiness(snapshot.scope_id, snapshots)
                freshness = .4 if any(x.is_stale for x in contents) else 0.0
                codes = ["diagnostic_or_review_recommended"] if evidence_count == 0 else ["practice_evidence"]
                if evidence_count and estimate < .45:
                    codes.append("knowledge_need")
                if readiness < .5:
                    codes.append("prerequisite_gap")
                evidence = [{"evidence_type": "KNOWLEDGE_SNAPSHOT", "reference_id": snapshot.snapshot_id,
                             "metadata": {"relation": "SUPPORTS", "data_quality": snapshot.data_quality}}]
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
        if plan.status == "PROPOSED": raise InvalidTransition("计划尚未接受")
        if plan.status == "EXPIRED": raise InvalidTransition("计划已过期")
        if plan.status in {"REJECTED", "UNDONE"}: raise InvalidTransition("当前计划状态不能执行")
        if _parse(plan.run.valid_until) and datetime.now(timezone.utc) >= _parse(plan.run.valid_until):
            self.repository.update_status(plan_id=plan_id, user_id=user_id, status="EXPIRED")
            raise InvalidTransition("计划已过期")
        failures = 0
        for item in plan.items:
            action_type = "CREATE_PERSONAL_TASK" if item.item_type == "CREATE_PERSONAL_TASK" else "REVIEW_PLAN_ITEM"
            action = self.repository.create_action(plan_id=plan_id, item_id=item.item_id, user_id=user_id, action_type=action_type)
            if action.status in {"SUCCEEDED", "UNDONE"}: continue
            try:
                target = None
                if action_type == "CREATE_PERSONAL_TASK":
                    target = self.task_repository.create_task(user_id=user_id, title=f"学习诊断：{item.knowledge_component_code or '课程复习'}",
                                                              source="learning_plan", external_id=f"{plan_id}:{item.item_id}", course_id=item.course_id)
                self.repository.finish_action(action_id=action.action_id, status="SUCCEEDED", target_task_id=target.id if target else None)
                self.repository.mark_item(item_id=item.item_id, status="SUCCEEDED")
            except Exception:
                failures += 1
                self.repository.finish_action(action_id=action.action_id, status="FAILED", error_code="action_failed")
                self.repository.mark_item(item_id=item.item_id, status="FAILED")
        status = "PARTIALLY_EXECUTED" if failures else "EXECUTED"
        return self.repository.update_status(plan_id=plan_id, user_id=user_id, status=status)  # type: ignore[return-value]

    def undo(self, *, user_id: str, plan_id: str) -> LearningPlanRow:
        plan = self.repository.get_plan(plan_id, user_id=user_id)
        if plan is None: raise NotFoundError()
        if plan.status not in {"EXECUTED", "PARTIALLY_EXECUTED"}: raise InvalidTransition("计划当前状态不能撤销")
        for action in self.repository.list_actions(plan_id=plan_id, user_id=user_id):
            if action.status != "SUCCEEDED" or action.action_type != "CREATE_PERSONAL_TASK" or not action.target_task_id:
                continue
            task = self.task_repository.get_task(action.target_task_id, user_id=user_id)
            if task and task.source == "learning_plan" and task.external_id == f"{plan_id}:{action.item_id}" and task.status != "deleted":
                self.task_repository.soft_delete(task.id, user_id=user_id)
            self.repository.finish_action(action_id=action.action_id, status="UNDONE", target_task_id=action.target_task_id)
        return self.repository.update_status(plan_id=plan_id, user_id=user_id, status="UNDONE")  # type: ignore[return-value]


__all__ = ["LearningPlannerService", "PLANNER_VERSION", "WEIGHTS"]

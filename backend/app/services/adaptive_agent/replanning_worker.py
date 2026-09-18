"""Bounded, restart-safe adaptive outcome and decision worker."""
from __future__ import annotations

import asyncio
import json
import inspect
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .replan_policy import ReplanDecisionPolicy


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class AdaptiveReplanTickReport:
    scanned: int = 0
    evaluated: int = 0
    reused: int = 0
    decisions: int = 0
    applied: int = 0
    failed: int = 0


class AdaptiveReplanningWorker:
    """Runs bounded ticks and can be hosted by the application lifespan."""

    def __init__(self, *, repository, intervention_service, policy: ReplanDecisionPolicy | None = None,
                 clock: Callable[[], datetime] = _utc_now, interval_seconds: float = 60.0,
                 sleeper: Callable[[float], object] | None = None) -> None:
        self._repository = repository
        self._service = intervention_service
        self._policy = policy or ReplanDecisionPolicy()
        self._clock = clock
        self._interval_seconds = interval_seconds
        self._sleeper = sleeper or asyncio.sleep
        self._task: asyncio.Task | None = None
        self._stopping = False

    def tick(self, *, batch_size: int = 25) -> AdaptiveReplanTickReport:
        batch_size = max(1, min(int(batch_size), 100))
        now = self._clock().astimezone(timezone.utc).replace(microsecond=0)
        rows = self._repository.list_due_for_evaluation(as_of=now.isoformat(), limit=batch_size)
        evaluated = reused = failed = decisions = applied = 0
        for row in rows:
            try:
                result = self._service.observe_and_evaluate(
                    user_id=row.user_id, intervention_id=row.intervention_id, as_of=now,
                )
                if result is None:
                    continue
                if result.persisted:
                    evaluated += 1
                elif result.reused_evaluation:
                    reused += 1
            except Exception as exc:
                failed += 1
                self._log_failure(row, "evaluation", exc)
        pending_query = getattr(self._repository, "list_pending_decisions", None)
        if pending_query is None:
            return AdaptiveReplanTickReport(scanned=len(rows), evaluated=evaluated, reused=reused, failed=failed)
        for row, existing in pending_query(as_of=now.isoformat(), limit=batch_size):
            try:
                evaluation_row = self._repository.get_evaluation(user_id=row.user_id, intervention_id=row.intervention_id)
                if evaluation_row is None:
                    continue
                evaluation = self._service._restore_evaluation(evaluation_row)
                decision = existing
                if decision is None:
                    goal = self._service._load_goal(user_id=row.user_id, goal_id=row.goal_id)
                    payload = evaluation.model_dump(mode="json")
                    comparison = payload.get("state_comparison") or {}
                    state = dict(comparison.get("after_values") or {})
                    for key, item in (comparison.get("dimensions") or {}).items():
                        if isinstance(item, dict) and isinstance(item.get("after"), (int, float)):
                            state[key] = item["after"]
                    proposed = self._policy.decide(
                        evaluation=payload, state=state,
                        goal=getattr(goal, "__dict__", {}) or {}, now=now.isoformat(),
                        evidence_refs=list(comparison.get("evidence_refs") or [evaluation.evaluation_id]),
                    )
                    decision = self._repository.save_decision(
                        user_id=row.user_id, goal_id=row.goal_id, intervention_id=row.intervention_id,
                        evaluation_id=evaluation.evaluation_id, decision=proposed.decision,
                        decision_digest=proposed.decision_digest, reason_codes=proposed.reason_codes,
                        suggested_adjustments=proposed.suggested_adjustments,
                        confidence=proposed.confidence, evidence_refs=proposed.evidence_refs,
                    )
                    decisions += 1
                    self._emit_event(row, "intervention_decided", evaluation.evaluation_id, decision.decision_id, now)
                if decision.status == "APPLIED":
                    continue
                self._repository.update_decision_status(user_id=row.user_id, decision_id=decision.decision_id, status="APPLYING")
                if decision.decision == "REPLAN":
                    successor = self._service.replan_from_evaluation(
                        user_id=row.user_id, intervention_id=row.intervention_id,
                        evaluation_id=evaluation.evaluation_id, decision_id=decision.decision_id,
                        reason_codes=self._json_list(decision.reason_codes_json),
                        suggested_adjustments=self._json_list(decision.suggested_adjustments_json), as_of=now,
                    )
                    if successor is None:
                        raise RuntimeError("replan_not_applied")
                    self._emit_event(row, "intervention_replanned", evaluation.evaluation_id, decision.decision_id, now)
                self._repository.update_decision_status(user_id=row.user_id, decision_id=decision.decision_id, status="APPLIED")
                applied += 1
            except Exception as exc:
                failed += 1
                if existing is not None:
                    self._repository.update_decision_status(user_id=row.user_id, decision_id=existing.decision_id, status="FAILED", failure_code=type(exc).__name__)
                self._log_failure(row, "decision", exc)
        return AdaptiveReplanTickReport(scanned=len(rows), evaluated=evaluated, reused=reused,
                                        decisions=decisions, applied=applied, failed=failed)

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run_loop(), name="adaptive-replanning-worker")

    async def stop(self) -> None:
        self._stopping = True
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self) -> None:
        while not self._stopping:
            await asyncio.to_thread(self.tick, batch_size=25)
            waited = self._sleeper(self._interval_seconds)
            if inspect.isawaitable(waited):
                await waited

    @staticmethod
    def _json_list(raw: str) -> list[str]:
        try:
            value = json.loads(raw or "[]")
        except (TypeError, ValueError):
            return []
        return [str(item) for item in value] if isinstance(value, list) else []

    def _emit_event(self, row, event_type: str, evaluation_id: str, decision_id: str, now: datetime) -> None:
        service = getattr(self._service, "_learner_event_service", None)
        if service is not None:
            try:
                service.record_intervention_event(
                    user_id=row.user_id, event_type=event_type, intervention_id=row.intervention_id,
                    goal_id=row.goal_id, evaluation_id=evaluation_id, decision_id=decision_id,
                    occurred_at=now, evidence_refs=[evaluation_id, decision_id],
                )
            except Exception:
                pass

    @staticmethod
    def _log_failure(row, stage: str, exc: Exception) -> None:
        from ...core.logging import logger
        logger.warning("adaptive_replanning_failed intervention_id={} stage={} error_code={}",
                       row.intervention_id, stage, type(exc).__name__)


__all__ = ["AdaptiveReplanningWorker", "AdaptiveReplanTickReport"]

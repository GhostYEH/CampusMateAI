"""Small, restart-safe background entry point for adaptive outcome evaluation."""
from __future__ import annotations

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
    failed: int = 0


class AdaptiveReplanningWorker:
    """Runs one bounded tick; idempotency is delegated to evaluation/replan keys."""

    def __init__(self, *, repository, intervention_service, policy: ReplanDecisionPolicy | None = None,
                 clock: Callable[[], datetime] = _utc_now) -> None:
        self._repository = repository
        self._service = intervention_service
        self._policy = policy or ReplanDecisionPolicy()
        self._clock = clock

    def tick(self, *, batch_size: int = 25) -> AdaptiveReplanTickReport:
        now = self._clock().astimezone(timezone.utc).replace(microsecond=0)
        rows = self._repository.list_due_for_evaluation(as_of=now.isoformat(), limit=batch_size)
        evaluated = reused = failed = 0
        for row in rows:
            try:
                result = self._service.observe_and_evaluate(
                    user_id=row.user_id, intervention_id=row.intervention_id, as_of=now,
                )
            except Exception:  # one corrupt row must not block the bounded batch
                failed += 1
                continue
            if result is None:
                continue
            if result.persisted:
                evaluated += 1
                evaluation = result.evaluation.model_dump(mode="json")
                goal = self._service._load_goal(user_id=row.user_id, goal_id=row.goal_id)
                decision = self._policy.decide(
                    evaluation=evaluation, state={}, goal=getattr(goal, "__dict__", {}) or {},
                    now=now.isoformat(), evidence_refs=[result.evaluation.evaluation_id],
                )
                if decision.decision == "REPLAN":
                    try:
                        self._service.replan_from_evaluation(
                            user_id=row.user_id, intervention_id=row.intervention_id,
                            evaluation_id=result.evaluation.evaluation_id,
                            decision_id=decision.decision_digest, reason_codes=decision.reason_codes, as_of=now,
                        )
                    except Exception:
                        failed += 1
            elif result.reused_evaluation:
                reused += 1
        return AdaptiveReplanTickReport(scanned=len(rows), evaluated=evaluated, reused=reused, failed=failed)

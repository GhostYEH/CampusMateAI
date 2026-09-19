"""Bounded, restart-safe adaptive outcome and decision worker."""
from __future__ import annotations

import asyncio
import json
import inspect
import sqlite3
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
            decision = existing
            try:
                evaluation_row = self._repository.get_evaluation(user_id=row.user_id, intervention_id=row.intervention_id)
                if evaluation_row is None:
                    continue
                evaluation = self._service._restore_evaluation(evaluation_row)
                self._emit_observed_event(row, evaluation, now)
                if decision is None:
                    goal = self._service._load_goal(user_id=row.user_id, goal_id=row.goal_id)
                    payload = evaluation.model_dump(mode="json")
                    comparison = payload.get("state_comparison") or {}
                    state = dict(comparison.get("after_values") or {})
                    for key, item in (comparison.get("dimensions") or {}).items():
                        if isinstance(item, dict) and isinstance(item.get("after"), (int, float)):
                            state[key] = item["after"]
                    # 防抖必须在**持久化 REPLAN 之前**判定：冷却 / 日限额 / 链深
                    # 是安全策略，命中时本轮转成带稳定 reason code 的 SUSPEND
                    # （保守等待，不改动计划），而不是记成基础设施 FAILED。
                    proposed = self._policy.decide(
                        evaluation=payload, state=state,
                        goal=getattr(goal, "__dict__", {}) or {}, now=now.isoformat(),
                        evidence_refs=list(comparison.get("evidence_refs") or [evaluation.evaluation_id]),
                        replan_guard_code=self._guard_code(row, now),
                    )
                    decision = self._repository.save_decision(
                        user_id=row.user_id, goal_id=row.goal_id, intervention_id=row.intervention_id,
                        evaluation_id=evaluation.evaluation_id, decision=proposed.decision,
                        decision_digest=proposed.decision_digest, reason_codes=proposed.reason_codes,
                        suggested_adjustments=proposed.suggested_adjustments,
                        confidence=proposed.confidence, evidence_refs=proposed.evidence_refs,
                    )
                    decisions += 1
                # Re-emit through the idempotent key on recovery; a failed
                # prior append must be retried before applying the decision.
                self._emit_event(row, "intervention_decided", evaluation.evaluation_id, decision.decision_id, now)
                if decision.status == "APPLIED":
                    continue
                # CAS 抢占：只有把决策从 PENDING（或可恢复的 RETRYABLE）原子推进到
                # APPLYING 的 Worker 才拥有处理权。`False` 表示另一个 Worker 已经
                # 先一步接手，或决策已进入终态 —— 此时**不得**继续生成后继，
                # 更不得取消别人创建的后继。
                if not self._claim(row, decision):
                    continue
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
                if decision is not None:
                    marker = getattr(self._repository, "mark_decision_failure", None)
                    if marker is not None:
                        try:
                            marker(user_id=row.user_id, decision_id=decision.decision_id,
                                   failure_code=type(exc).__name__, retryable=self._is_retryable(exc), now=now)
                        except TypeError:
                            # Preserve compatibility with small test/double repositories
                            # that predate the injectable failure timestamp.
                            marker(user_id=row.user_id, decision_id=decision.decision_id,
                                   failure_code=type(exc).__name__, retryable=self._is_retryable(exc))
                    else:
                        self._repository.update_decision_status(user_id=row.user_id, decision_id=decision.decision_id, status="FAILED", failure_code=type(exc).__name__)
                self._log_failure(row, "decision", exc)
        return AdaptiveReplanTickReport(scanned=len(rows), evaluated=evaluated, reused=reused,
                                        decisions=decisions, applied=applied, failed=failed)

    def _claim(self, row, decision) -> bool:
        """抢占决策处理权；`False` 表示本 Worker 没拿到，必须原样退出。"""
        claim = getattr(self._repository, "claim_decision", None)
        if claim is None:
            # 兼容只实现状态推进的小型测试替身：没有 CAS 时退化为原语义。
            self._repository.update_decision_status(
                user_id=row.user_id, decision_id=decision.decision_id, status="APPLYING",
            )
            return True
        return bool(claim(user_id=row.user_id, decision_id=decision.decision_id))

    def _guard_code(self, row, now: datetime) -> str | None:
        resolver = getattr(self._service, "replan_guard_code", None)
        if resolver is None:
            return None
        return resolver(
            user_id=row.user_id, goal_id=row.goal_id, intervention_id=row.intervention_id,
            chain_depth=int(getattr(row, "chain_depth", 0) or 0), as_of=now,
        )

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
        """后台调度循环：**单轮失败绝不结束调度**。

        每一轮都有顶层异常隔离：扫描/评估/决策阶段抛出的任何异常都在这里被
        吸收并留下结构化日志（阶段 + 错误码，不含学生隐私内容与凭据），
        下一轮照常继续。只有 `CancelledError`（`stop()` 或进程退出）才会
        真正终止循环，保证关闭时不遗留后台任务。
        """
        while not self._stopping:
            try:
                await asyncio.to_thread(self.tick, batch_size=25)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - 顶层隔离：单轮失败不能杀死调度
                from ...core.logging import logger
                logger.warning(
                    "adaptive_replanning_round_failed stage=tick error_code={}",
                    type(exc).__name__,
                )
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
        if service is None:
            raise RuntimeError("learner_event_service_unavailable")
        service.record_intervention_event(
                    user_id=row.user_id, event_type=event_type, intervention_id=row.intervention_id,
                    goal_id=row.goal_id, evaluation_id=evaluation_id, decision_id=decision_id,
                    occurred_at=now, evidence_refs=[evaluation_id, decision_id],
                )

    def _emit_observed_event(self, row, evaluation, now: datetime) -> None:
        service = getattr(self._service, "_learner_event_service", None)
        if service is None:
            raise RuntimeError("learner_event_service_unavailable")
        service.record_intervention_event(
            user_id=row.user_id, event_type="intervention_observed",
            intervention_id=row.intervention_id, goal_id=row.goal_id,
            evaluation_id=evaluation.evaluation_id, occurred_at=now,
            outcome="observed_completed", adoption=evaluation.adoption,
            observed_outcome=evaluation.observed_outcome,
            evidence_refs=[evaluation.evaluation_id],
        )

    @staticmethod
    def _log_failure(row, stage: str, exc: Exception) -> None:
        from ...core.logging import logger
        logger.warning("adaptive_replanning_failed intervention_id={} stage={} error_code={}",
                       row.intervention_id, stage, type(exc).__name__)

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, (sqlite3.OperationalError, TimeoutError, ConnectionError)):
            return True
        text = str(exc).lower()
        return any(token in text for token in ("temporary", "unavailable", "timed out", "locked", "network"))


__all__ = ["AdaptiveReplanningWorker", "AdaptiveReplanTickReport"]

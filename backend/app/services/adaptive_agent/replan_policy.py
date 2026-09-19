"""Deterministic replan decisions; no model call participates in this decision."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReplanDecision:
    decision: str
    reason_codes: list[str]
    explanation: str
    confidence: float
    evidence_refs: list[str]
    suggested_adjustments: list[str]
    decided_at: str
    decision_digest: str


class ReplanDecisionPolicy:
    def decide(self, *, evaluation: dict[str, Any], state: dict[str, Any], goal: dict[str, Any], now: str,
               evidence_refs: list[str] | None = None,
               replan_guard_code: str | None = None) -> ReplanDecision:
        """给出本轮决策。

        `replan_guard_code` 是防抖守卫给出的稳定 reason code（冷却未到 / 单日上限 /
        链深上限）。它**不改变**策略判断本身，只把"想重规划"降级成"保守暂停"：
        防抖是正常的安全决策，不是基础设施失败，因此绝不能表现为 FAILED。
        """
        if str(goal.get("status", "active")).lower() in {"completed", "cancelled", "inactive", "stopped"}:
            return self._build("SUSPEND", ["goal_inactive_or_completed"], "目标已结束，停止后续规划。", [], now, evidence_refs)
        outcome = evaluation.get("observed_outcome", "INSUFFICIENT_EVIDENCE")
        adoption = evaluation.get("adoption", evaluation.get("execution_signal", "UNAVAILABLE"))
        if outcome == "INSUFFICIENT_EVIDENCE":
            return self._build("WAIT_FOR_EVIDENCE", ["insufficient_state_evidence"], "尚缺可比较的学生状态证据。", [], now, evidence_refs)
        stress = float(state.get("stress_risk") or 0.0)
        if stress >= 0.7:
            return self._guarded("REPLAN", ["stress_risk_high"], "压力风险升高，建议降低负荷。",
                                 ["reduce_workload", "split_tasks"], now, evidence_refs, replan_guard_code)
        if outcome == "DECLINED":
            return self._guarded("REPLAN", ["state_declined"], "观测到相关状态下降，建议加强基础或调整顺序。",
                                 ["reinforce_foundation", "lower_challenge"], now, evidence_refs, replan_guard_code)
        if adoption in {"NOT_STARTED", "IN_PROGRESS"}:
            return self._build("CONTINUE", ["adoption_still_in_progress"], "执行证据尚在积累，保持当前计划。", [], now, evidence_refs)
        return self._build("CONTINUE", ["state_improved_or_stable"], "状态未显示需要调整的信号，保持当前策略。", [], now, evidence_refs)

    @classmethod
    def _guarded(cls, decision: str, codes: list[str], explanation: str, adjustments: list[str],
                 now: str, evidence_refs: list[str] | None,
                 replan_guard_code: str | None) -> ReplanDecision:
        if decision == "REPLAN" and replan_guard_code:
            return cls._build(
                "SUSPEND", [replan_guard_code],
                "重规划被防抖守卫拦住，本轮保守等待而不是改动计划。", [], now, evidence_refs,
            )
        return cls._build(decision, codes, explanation, adjustments, now, evidence_refs)

    @staticmethod
    def _build(decision: str, codes: list[str], explanation: str, adjustments: list[str], now: str,
               evidence_refs: list[str] | None) -> ReplanDecision:
        payload = {"decision": decision, "codes": codes, "adjustments": adjustments, "at": now}
        return ReplanDecision(
            decision, codes, explanation, 0.7 if decision != "WAIT_FOR_EVIDENCE" else 0.3,
            evidence_refs or [], adjustments, now,
            hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
        )

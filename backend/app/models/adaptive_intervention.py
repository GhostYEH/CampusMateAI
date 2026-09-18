"""Adaptive Intervention Record —— 状态驱动干预的持久化行模型。

只存安全、结构化、有限字段：策略码、理由码、预期结果、基线状态 run 引用，
以及经过 schema 校验的 assessment/strategy JSON。不存完整聊天、原始作业答案或隐私文本。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# 本轮真实写入的状态。
INTERVENTION_STATUSES = (
    "PROPOSED",
    "PLAN_GENERATED",
    "ACCEPTED",
    "EXECUTING",
    "CANCELLED",
)
# 下一轮（结果反馈 / 评估）预留：本轮不写入，避免伪造尚未发生的生命周期。
RESERVED_INTERVENTION_STATUSES = ("OBSERVING", "EVALUATED", "SUPERSEDED")


@dataclass(frozen=True)
class AdaptiveInterventionRow:
    intervention_id: str
    user_id: str
    goal_id: str
    plan_id: str | None
    agent_job_id: str | None
    agent_run_id: str | None
    status: str
    strategy_code: str
    strategy_version: str
    assessment_id: str
    assessment_json: str
    strategy_json: str
    rationale_codes_json: str
    expected_outcomes_json: str
    baseline_core_run_id: str | None
    baseline_academic_run_id: str | None
    baseline_world_run_id: str | None
    baseline_state_digest: str
    confidence: float
    warning_codes_json: str
    idempotency_key: str
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: Any) -> "AdaptiveInterventionRow":
        return cls(
            intervention_id=row["intervention_id"],
            user_id=row["user_id"],
            goal_id=row["goal_id"],
            plan_id=row["plan_id"],
            agent_job_id=row["agent_job_id"],
            agent_run_id=row["agent_run_id"],
            status=row["status"],
            strategy_code=row["strategy_code"],
            strategy_version=row["strategy_version"],
            assessment_id=row["assessment_id"],
            assessment_json=row["assessment_json"],
            strategy_json=row["strategy_json"],
            rationale_codes_json=row["rationale_codes_json"],
            expected_outcomes_json=row["expected_outcomes_json"],
            baseline_core_run_id=row["baseline_core_run_id"],
            baseline_academic_run_id=row["baseline_academic_run_id"],
            baseline_world_run_id=row["baseline_world_run_id"],
            baseline_state_digest=row["baseline_state_digest"],
            confidence=float(row["confidence"]),
            warning_codes_json=row["warning_codes_json"],
            idempotency_key=row["idempotency_key"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


__all__ = [
    "AdaptiveInterventionRow",
    "INTERVENTION_STATUSES",
    "RESERVED_INTERVENTION_STATUSES",
]

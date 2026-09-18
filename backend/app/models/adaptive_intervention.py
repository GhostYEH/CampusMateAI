"""Adaptive Intervention Record —— 状态驱动干预的持久化行模型。

只存安全、结构化、有限字段：策略码、理由码、预期结果、基线状态 run 引用，
以及经过 schema 校验的 assessment/strategy JSON。不存完整聊天、原始作业答案或隐私文本。

生命周期（第二阶段加入结果反馈与评估）：

    PROPOSED ──绑定计划──> PLAN_GENERATED ──观测到执行──> OBSERVING ──评估完成──> EVALUATED
    任意阶段失败 ──> CANCELLED（不参与评估）

`SUPERSEDED` 已经在表约束里预留（重规划切片再写入），但本轮没有代码路径会写它，
所以 `WRITABLE_INTERVENTION_STATUSES` 仍然拒绝它，避免出现"写进去但没人推进"的伪状态。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# 表约束允许的完整生命周期（写入前还会再过一遍 WRITABLE_* 白名单）。
INTERVENTION_STATUSES = (
    "PROPOSED",
    "PLAN_GENERATED",
    "ACCEPTED",
    "EXECUTING",
    "CANCELLED",
    "OBSERVING",
    "EVALUATED",
    "SUPERSEDED",
)
# 本轮真实会写入的状态：SUPERSEDED 只有表约束预留，没有推进路径。
WRITABLE_INTERVENTION_STATUSES = (
    "PROPOSED",
    "PLAN_GENERATED",
    "ACCEPTED",
    "EXECUTING",
    "CANCELLED",
    "OBSERVING",
    "EVALUATED",
)
RESERVED_INTERVENTION_STATUSES = ("SUPERSEDED",)


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
    observation_started_at: str | None
    evaluated_at: str | None
    outcome_verdict: str | None
    evaluation_id: str | None
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
            observation_started_at=row["observation_started_at"],
            evaluated_at=row["evaluated_at"],
            outcome_verdict=row["outcome_verdict"],
            evaluation_id=row["evaluation_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True)
class InterventionEvaluationRow:
    """一次结果评估的持久化行：只存通过 schema 校验的评估 JSON 与有限枚举列。"""

    evaluation_id: str
    intervention_id: str
    user_id: str
    goal_id: str
    plan_id: str | None
    evaluator_version: str
    input_digest: str
    observation_status: str
    execution_signal: str
    plan_fidelity: str
    verdict: str
    evaluation_json: str
    warning_codes_json: str
    as_of: str
    created_at: str

    @classmethod
    def from_row(cls, row: Any) -> "InterventionEvaluationRow":
        return cls(
            evaluation_id=row["evaluation_id"],
            intervention_id=row["intervention_id"],
            user_id=row["user_id"],
            goal_id=row["goal_id"],
            plan_id=row["plan_id"],
            evaluator_version=row["evaluator_version"],
            input_digest=row["input_digest"],
            observation_status=row["observation_status"],
            execution_signal=row["execution_signal"],
            plan_fidelity=row["plan_fidelity"],
            verdict=row["verdict"],
            evaluation_json=row["evaluation_json"],
            warning_codes_json=row["warning_codes_json"],
            as_of=row["as_of"],
            created_at=row["created_at"],
        )


__all__ = [
    "AdaptiveInterventionRow",
    "InterventionEvaluationRow",
    "INTERVENTION_STATUSES",
    "WRITABLE_INTERVENTION_STATUSES",
    "RESERVED_INTERVENTION_STATUSES",
]

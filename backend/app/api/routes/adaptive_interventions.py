"""状态驱动干预记录的只读查询接口。

只读、仅学生本人：

- `GET /api/v1/adaptive-interventions` 分页列出自己的干预记录
- `GET /api/v1/adaptive-interventions/{intervention_id}` 查看单条
- `GET /api/v1/adaptive-interventions/{intervention_id}/outcome` 查看结果评估

不返回内部 `user_id`、原始 JSON 字符串或任何证据正文；跨用户访问与不存在同样返回 404，
与仓库其它资源隔离语义一致。不提供写入、人工篡改策略或管理员覆盖接口。

`/outcome` 是纯查询：后台闭环负责写入评估，页面访问绝不改变学生记录。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query

from ...core.exceptions import NotFoundError
from ...models.adaptive_intervention import AdaptiveInterventionRow
from ...models.multi_role import UserRow
from ...schemas.adaptive_intervention import (
    AdaptiveInterventionOut,
    AdaptiveInterventionOutcomeOut,
    AdaptiveInterventionPage,
)
from ...services.container import ServiceContainer, get_container
from ...services.adaptive_agent.intervention_service import PLAN_SCOPE_GOAL_PREFIX
from ..deps import student_only

router = APIRouter(prefix="/adaptive-interventions", tags=["adaptive-interventions"])


def _container() -> ServiceContainer:
    return get_container()


def _loads(value: str | None, fallback):
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return fallback
    return parsed if isinstance(parsed, type(fallback)) else fallback


# 公开的 before/after 比较形状。**白名单**而不是黑名单：只有列在这里的字段会出网。
_COMPARISON_KEYS = (
    "relevant_dimensions", "before_values", "after_values", "delta", "outcome",
    "confidence", "warnings", "comparison_as_of", "dimensions",
)
_DIMENSION_KEYS = (
    "before", "after", "before_data_quality", "after_data_quality",
    "before_confidence", "after_confidence", "before_observed_at", "after_observed_at",
)
# 内部 provenance 标识前缀：任何字符串值命中即丢弃。
_INTERNAL_ID_PREFIXES = ("lsnap_", "lrun_", "lprun_")


def _scope_type(goal_id: str) -> str:
    """这条干预的归因范围：真实学生目标 vs 计划本身。

    未绑定学生目标的普通计划用 `plan:{plan_id}` 作为 scope 键。它**同样**进入
    观测/评估/重规划闭环（有可归因维度时会安全替换计划）；这里只把"归因范围"
    显式出网，让三端不必去猜 `goal_id` 的字符串前缀。
    """
    return "PLAN" if goal_id.startswith(PLAN_SCOPE_GOAL_PREFIX) else "GOAL"


def _scrub_value(value):
    if isinstance(value, str) and value.startswith(_INTERNAL_ID_PREFIXES):
        return None
    return value


def _public_state_comparison(raw) -> dict | None:
    """把内部状态比较投影成公开形状。

    学生能看到的是：维度值、数据质量、置信度、观测时刻、结论与稳定 warning code。
    内部 provenance（状态 run id、快照 id、证据引用、原始异常文本）一律不出网，
    避免把内部实现标识泄露到客户端并形成隐式契约。
    """
    if not isinstance(raw, dict):
        return None
    out: dict = {}
    for key in _COMPARISON_KEYS:
        if key not in raw:
            continue
        value = raw[key]
        if key == "dimensions":
            dimensions: dict = {}
            if isinstance(value, dict):
                for name, record in value.items():
                    if not isinstance(record, dict):
                        continue
                    cleaned = {}
                    for field in _DIMENSION_KEYS:
                        if field not in record:
                            continue
                        item = _scrub_value(record[field])
                        if item is not None:
                            cleaned[field] = item
                    dimensions[str(name)] = cleaned
            out[key] = dimensions
        elif key == "warnings":
            out[key] = [str(code) for code in value] if isinstance(value, (list, tuple)) else []
        elif key in ("before_values", "after_values", "delta"):
            out[key] = (
                {str(k): v for k, v in value.items() if _scrub_value(v) is not None}
                if isinstance(value, dict) else {}
            )
        else:
            out[key] = value
    return out


def _out(row: AdaptiveInterventionRow) -> AdaptiveInterventionOut:
    assessment = _loads(row.assessment_json, {})
    return AdaptiveInterventionOut(
        intervention_id=row.intervention_id,
        goal_id=row.goal_id,
        plan_id=row.plan_id,
        scope_type=_scope_type(row.goal_id),
        status=row.status,
        strategy_code=row.strategy_code,
        strategy_version=row.strategy_version,
        rationale_codes=[str(code) for code in _loads(row.rationale_codes_json, [])],
        expected_outcomes=[str(code) for code in _loads(row.expected_outcomes_json, [])],
        baseline_core_run_id=row.baseline_core_run_id,
        baseline_academic_run_id=row.baseline_academic_run_id,
        baseline_world_run_id=row.baseline_world_run_id,
        confidence=row.confidence,
        problem_types=[str(code) for code in (assessment.get("problem_types") or [])],
        data_quality=assessment.get("data_quality"),
        warning_codes=[str(code) for code in _loads(row.warning_codes_json, [])],
        observation_started_at=row.observation_started_at,
        observation_due_at=row.observation_due_at,
        evaluated_at=row.evaluated_at,
        outcome_verdict=row.outcome_verdict,
        supersedes_intervention_id=row.supersedes_intervention_id,
        superseded_by_intervention_id=row.superseded_by_intervention_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=AdaptiveInterventionPage)
def list_adaptive_interventions(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> AdaptiveInterventionPage:
    rows, total = container.adaptive_intervention_repository.list_interventions(
        user_id=user.id, page=page, page_size=page_size
    )
    return AdaptiveInterventionPage(
        items=[_out(row) for row in rows], total=total, page=page, page_size=page_size,
        has_more=page * page_size < total,
    )


@router.get("/{intervention_id}", response_model=AdaptiveInterventionOut)
def get_adaptive_intervention(
    intervention_id: str,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> AdaptiveInterventionOut:
    row = container.adaptive_intervention_repository.get(
        user_id=user.id, intervention_id=intervention_id
    )
    if row is None:
        # 非本人访问与不存在返回同样的 404，不泄露记录是否存在。
        raise NotFoundError()
    return _out(row)


@router.get("/{intervention_id}/outcome", response_model=AdaptiveInterventionOutcomeOut)
def get_adaptive_intervention_outcome(
    intervention_id: str,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> AdaptiveInterventionOutcomeOut:
    intervention = container.adaptive_intervention_repository.get(
        user_id=user.id, intervention_id=intervention_id
    )
    if intervention is None:
        raise NotFoundError()
    stored = container.adaptive_intervention_repository.get_evaluation(
        user_id=user.id, intervention_id=intervention_id
    )
    if stored is None:
        # 尚无后台观测：响应保持兼容形状，但不临时计算、更不写入任何评估。
        return AdaptiveInterventionOutcomeOut(
            evaluation_id="", intervention_id=intervention_id, goal_id=intervention.goal_id,
            plan_id=intervention.plan_id,
            scope_type=_scope_type(intervention.goal_id),
            as_of=intervention.updated_at,
            observation_status="NOT_STARTED", execution_signal="NOT_STARTED", adoption="NOT_STARTED",
            plan_fidelity="UNVERIFIABLE", verdict="NOT_OBSERVED",
            observed_outcome="INSUFFICIENT_EVIDENCE", causal_claim="NOT_ESTIMATED",
            confidence=0.0, data_quality=None, evaluator_version="adaptive-intervention-outcome-v2",
            observation_due_at=intervention.observation_due_at,
            lineage={"supersedes_intervention_id": intervention.supersedes_intervention_id,
                      "superseded_by_intervention_id": intervention.superseded_by_intervention_id},
            created_at="",
        )
    evaluation = container.adaptive_intervention_service._restore_evaluation(stored)
    decision = container.adaptive_intervention_repository.get_decision(
        user_id=user.id, evaluation_id=evaluation.evaluation_id
    )
    summary = evaluation.safe_summary()
    return AdaptiveInterventionOutcomeOut(
        evaluation_id=evaluation.evaluation_id,
        intervention_id=summary["intervention_id"],
        goal_id=summary["goal_id"],
        plan_id=summary["plan_id"],
        scope_type=_scope_type(intervention.goal_id),
        as_of=summary["as_of"],
        window_start=evaluation.window_start,
        window_end=evaluation.window_end,
        observation_status=summary["observation_status"],
        execution_signal=summary["execution_signal"],
        adoption=summary["adoption"],
        plan_fidelity=summary["plan_fidelity"],
        verdict=summary["verdict"],
        observed_outcome=summary["observed_outcome"],
        causal_claim=summary["causal_claim"],
        state_comparison=_public_state_comparison(evaluation.state_comparison),
        decision=decision.decision if decision else None,
        decision_reason_codes=_loads(decision.reason_codes_json, []) if decision else [],
        suggested_adjustments=_loads(decision.suggested_adjustments_json, []) if decision else [],
        decision_confidence=decision.confidence if decision else None,
        decision_status=decision.status if decision else None,
        lineage={"supersedes_intervention_id": intervention.supersedes_intervention_id,
                 "superseded_by_intervention_id": intervention.superseded_by_intervention_id},
        observation_due_at=intervention.observation_due_at,
        outcome_checks=summary["outcome_checks"],
        execution_signals=summary["execution_signals"],
        confidence=summary["confidence"],
        data_quality=summary["data_quality"],
        warning_codes=summary["warning_codes"],
        evaluator_version=summary["evaluator_version"],
        created_at=stored.created_at,
    )


__all__ = ["router"]

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


def _out(row: AdaptiveInterventionRow) -> AdaptiveInterventionOut:
    assessment = _loads(row.assessment_json, {})
    return AdaptiveInterventionOut(
        intervention_id=row.intervention_id,
        goal_id=row.goal_id,
        plan_id=row.plan_id,
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
            plan_id=intervention.plan_id, as_of=intervention.updated_at,
            observation_status="NOT_STARTED", execution_signal="NOT_STARTED", adoption="NOT_STARTED",
            plan_fidelity="UNVERIFIABLE", verdict="NOT_OBSERVED",
            observed_outcome="INSUFFICIENT_EVIDENCE", causal_claim="NOT_ESTIMATED",
            confidence=0.0, data_quality=None, evaluator_version="adaptive-intervention-outcome-v2",
            created_at="",
        )
    evaluation = container.adaptive_intervention_service._restore_evaluation(stored)
    summary = evaluation.safe_summary()
    return AdaptiveInterventionOutcomeOut(
        evaluation_id=evaluation.evaluation_id,
        intervention_id=summary["intervention_id"],
        goal_id=summary["goal_id"],
        plan_id=summary["plan_id"],
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
        outcome_checks=summary["outcome_checks"],
        execution_signals=summary["execution_signals"],
        confidence=summary["confidence"],
        data_quality=summary["data_quality"],
        warning_codes=summary["warning_codes"],
        evaluator_version=summary["evaluator_version"],
        created_at=stored.created_at,
    )


__all__ = ["router"]

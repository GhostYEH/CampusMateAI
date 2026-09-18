"""状态驱动干预记录的只读查询接口。

只读、仅学生本人：

- `GET /api/v1/adaptive-interventions` 分页列出自己的干预记录
- `GET /api/v1/adaptive-interventions/{intervention_id}` 查看单条
- `GET /api/v1/adaptive-interventions/{intervention_id}/outcome` 查看结果评估

不返回内部 `user_id`、原始 JSON 字符串或任何证据正文；跨用户访问与不存在同样返回 404，
与仓库其它资源隔离语义一致。不提供写入、人工篡改策略或管理员覆盖接口。

`/outcome` 与既有的 `GET /learning-plans/{plan_id}/evaluation` 一样是"读触发观测"：
评估本身按观测输入摘要幂等（同一份观测只落一行），重复请求不会产生重复记录。
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
        evaluated_at=row.evaluated_at,
        outcome_verdict=row.outcome_verdict,
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
    result = container.adaptive_intervention_service.observe_and_evaluate(
        user_id=user.id, intervention_id=intervention_id
    )
    if result is None:
        raise NotFoundError()
    stored = container.adaptive_intervention_repository.get_evaluation(
        user_id=user.id, intervention_id=intervention_id
    )
    summary = result.evaluation.safe_summary()
    return AdaptiveInterventionOutcomeOut(
        evaluation_id=result.evaluation.evaluation_id,
        intervention_id=summary["intervention_id"],
        goal_id=summary["goal_id"],
        plan_id=summary["plan_id"],
        as_of=summary["as_of"],
        window_start=result.evaluation.window_start,
        window_end=result.evaluation.window_end,
        observation_status=summary["observation_status"],
        execution_signal=summary["execution_signal"],
        plan_fidelity=summary["plan_fidelity"],
        verdict=summary["verdict"],
        outcome_checks=summary["outcome_checks"],
        execution_signals=summary["execution_signals"],
        confidence=summary["confidence"],
        data_quality=summary["data_quality"],
        warning_codes=summary["warning_codes"],
        evaluator_version=summary["evaluator_version"],
        # 未落库的结论（无计划 / 还没开始执行）如实返回空，不伪造落库时间。
        created_at=stored.created_at if stored is not None else "",
    )


__all__ = ["router"]

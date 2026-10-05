from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from ...models.multi_role import UserRow
from ...schemas.forecast import ForecastPage
from ...services.container import ServiceContainer, get_container
from ..deps import require_role

router = APIRouter(prefix="/learner-state", tags=["学习预测"])


def _container() -> ServiceContainer:
    return get_container()


@router.get(
    "/forecasts",
    response_model=ForecastPage,
    summary="获取学习风险预测",
    responses={
        200: {
            "description": "校园生活与目标执行风险预测分页列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "风险预测列表",
                            "value": {
                                "items": [
                                    {
                                        "forecast_id": "fc_demo_1",
                                        "forecast_type": "DEADLINE_COMPLETION_RISK",
                                        "scope_type": "USER",
                                        "scope_id": "u_demo",
                                        "horizon_start": "2026-10-06T00:00:00+00:00",
                                        "horizon_end": "2026-10-13T00:00:00+00:00",
                                        "probability": 0.35,
                                        "value": {
                                            "pending_task_count": 4,
                                            "overdue_task_count": 1,
                                            "tasks_within_horizon": 3,
                                            "risk_band": "MODERATE",
                                            "data_completeness": "verified",
                                        },
                                        "confidence": 0.6,
                                        "data_quality": "verified",
                                        "estimator_version": "forecast-1.0.0",
                                        "input_digest": "sha256:demo",
                                        "as_of": "2026-10-06T08:00:00+00:00",
                                        "valid_until": "2026-10-06T20:00:00+00:00",
                                        "evidence_summary": {
                                            "observed_session_count": 5,
                                            "observed_task_count": 6,
                                            "observed_goal_count": 1,
                                            "observed_schedule_count": 2,
                                            "observed_exam_count": 0,
                                            "history_window_days": 30,
                                        },
                                    }
                                ],
                                "total": 1,
                                "page": 1,
                                "page_size": 20,
                                "has_more": False,
                            },
                        }
                    }
                }
            },
        }
    },
)
def list_forecasts(
    forecast_type: str | None = Query(
        None,
        pattern="^(DEADLINE_COMPLETION_RISK|UPCOMING_WORKLOAD|SCHEDULE_CONFLICT_RISK|GOAL_PROGRESS_OUTLOOK|ROUTINE_CONTINUITY)$",
    ),
    horizon_days: int = Query(7, ge=1, le=30),
    goal_id: str | None = Query(None, min_length=1, max_length=128),
    course_id: str | None = Query(None, min_length=1, max_length=128),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> ForecastPage:
    """获取校园生活与目标执行风险预测。

    确定性、版本化、可重复的基线估计器。
    数据不足时返回 UNAVAILABLE，不捏造概率。
    """
    as_of = datetime.now(timezone.utc)
    items, total = container.forecast_service.list_forecasts(
        user_id=user.id,
        as_of=as_of,
        forecast_type=forecast_type,
        horizon_days=horizon_days,
        goal_id=goal_id,
        course_id=course_id,
        page=page,
        page_size=page_size,
    )
    return ForecastPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=page * page_size < total,
    )


__all__ = ["router"]

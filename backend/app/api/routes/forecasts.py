from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from ...models.multi_role import UserRow
from ...schemas.forecast import ForecastPage
from ...services.container import ServiceContainer, get_container
from ..deps import require_role

router = APIRouter(prefix="/learner-state", tags=["forecasts"])


def _container() -> ServiceContainer:
    return get_container()


@router.get("/forecasts", response_model=ForecastPage)
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
    as_of = datetime.now(timezone.utc).replace(microsecond=0)
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
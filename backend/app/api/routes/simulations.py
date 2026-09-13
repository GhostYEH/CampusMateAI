from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ...models.multi_role import UserRow
from ...schemas.simulation import SimulationRequest, SimulationResponse
from ...services.container import ServiceContainer, get_container
from ..deps import require_role
from ...core.exceptions import NotFoundError

router = APIRouter(prefix="/learner-state", tags=["simulations"])


def _container() -> ServiceContainer:
    return get_container()


@router.post("/simulations", response_model=SimulationResponse)
def create_simulation(
    request: SimulationRequest,
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> SimulationResponse:
    """反事实方案模拟 — 只读地比较校园行动方案的影响。

    不创建任务、不修改目标、不执行计划、不暂停真实数据源。
    结果是"方案估计,不是因果保证"。
    跨用户 baseline_run_id 返回 404。
    """
    as_of = datetime.now(timezone.utc).replace(microsecond=0)
    try:
        return container.simulation_service.simulate(
            user_id=user.id,
            baseline_run_id=request.baseline_run_id,
            intervention=request.intervention,
            horizon_days=request.horizon_days,
            idempotency_key=request.idempotency_key,
            as_of=as_of,
        )
    except LookupError as exc:
        raise NotFoundError() from exc


__all__ = ["router"]
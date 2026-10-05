from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Body, Depends

from ...models.multi_role import UserRow
from ...schemas.simulation import SimulationRequest, SimulationResponse
from ...services.container import ServiceContainer, get_container
from ..deps import require_role
from ...core.exceptions import NotFoundError

router = APIRouter(prefix="/learner-state", tags=["学习模拟"])


def _container() -> ServiceContainer:
    return get_container()


@router.post(
    "/simulations",
    response_model=SimulationResponse,
    summary="模拟校园行动方案",
    responses={
        200: {
            "description": "只读的反事实模拟结果，不写入任何业务数据",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "方案模拟结果",
                            "value": {
                                "simulation_id": "sim_demo_1",
                                "baseline_digest": "sha256:demo",
                                "intervention": {
                                    "intervention_type": "ALLOCATE_FOCUS_MINUTES",
                                    "focus_minutes": 60,
                                    "target_date": "2026-10-07T09:00:00+00:00",
                                },
                                "changed_forecasts": [],
                                "assumptions": [
                                    "intervention_applied_in_memory_only",
                                    "baseline_state_unchanged",
                                ],
                                "limitations": [
                                    "baseline_estimator_only",
                                    "no_causal_claim",
                                    "intervention_not_executed",
                                ],
                                "confidence": 0.5,
                                "data_quality": "partial",
                                "estimator_version": "simulation-1.0.0",
                                "expires_at": "2026-10-06T20:00:00+00:00",
                                "causal_claim": False,
                            },
                        }
                    }
                }
            },
        }
    },
)
def create_simulation(
    request: Annotated[
        SimulationRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "为某天分配 60 分钟专注",
                    "value": {
                        "intervention": {
                            "intervention_type": "ALLOCATE_FOCUS_MINUTES",
                            "focus_minutes": 60,
                            "target_date": "2026-10-07T09:00:00+00:00",
                        },
                        "horizon_days": 7,
                        "idempotency_key": "sim-demo-1",
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> SimulationResponse:
    """反事实方案模拟 — 只读地比较校园行动方案的影响。

    不创建任务、不修改目标、不执行计划、不暂停真实数据源。
    结果是"方案估计,不是因果保证"。
    跨用户 baseline_run_id 返回 404。
    """
    as_of = datetime.now(timezone.utc)
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

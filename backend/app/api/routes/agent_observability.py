"""管理员 Agent Runtime 观测 API(Task 9)。

**只读、聚合优先、脱敏**:
- 仅 `role == "admin"` 可访问;未登录 401,学生/教师 403;
- 不提供任何重放、改状态、执行工具或查看原始模型内容的入口;
- 所有查询都带时间窗与行数上限,响应模型 `extra="forbid"` 且不含敏感字段。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ...core.exceptions import AgentPermissionDenied, AgentRunNotFound
from ...models.multi_role import UserRow
from ...schemas.agent_observability import AgentRunTraceOut, AgentRuntimeOverviewOut
from ...services.agent_runtime.observability import AgentObservabilityService
from ..deps import ServiceContainer, current_user, get_container

router = APIRouter(prefix="/admin/agent-runtime", tags=["admin-agent-runtime"])


def _require_admin(user: UserRow) -> UserRow:
    if user.role != "admin":
        raise AgentPermissionDenied("仅管理员可访问 Agent Runtime 观测接口")
    return user


def _service(container: ServiceContainer) -> AgentObservabilityService:
    return AgentObservabilityService(container.agent_runtime_repository)


@router.get("/overview", response_model=AgentRuntimeOverviewOut)
async def agent_runtime_overview(
    since_hours: int = Query(24, ge=1, le=24 * 30),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> AgentRuntimeOverviewOut:
    """队列深度、状态分布、成功率、耗时、Token、工具、重试与审批等待。"""
    _require_admin(user)
    return AgentRuntimeOverviewOut(**_service(container).overview(since_hours=since_hours))


@router.get("/runs/{run_id}/trace", response_model=AgentRunTraceOut)
async def agent_run_trace(
    run_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
) -> AgentRunTraceOut:
    """单 Run 时间线:状态、阶段、角色、模型名、Token、耗时、错误码与审批时长。"""
    _require_admin(user)
    trace = _service(container).run_trace(run_id)
    if trace is None:
        raise AgentRunNotFound("Run 不存在")
    return AgentRunTraceOut(**trace)


__all__ = ["router"]

"""CampusMate-owned status boundary for the managed OpenMAIC runtime."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from ...models.multi_role import UserRow
from ...schemas.openmaic_fusion import (
    FusionRecentItem,
    FusionRecentOut,
    FusionState,
    FusionStatus,
)
from ...services.container import ServiceContainer, get_container
from ...services.course_access import can_view_course
from ...services.openmaic.classroom_service import OpenMAICClassroomService
from ...services.openmaic.fusion_client import OpenMAICFusionClient
from ..deps import current_user

router = APIRouter(prefix="/openmaic/fusion", tags=["openmaic-fusion"])

# "最近内容"的上限。浏览器默认要 20 条；上限固定，避免被当成全量导出接口。
RECENT_DEFAULT_LIMIT = 20
RECENT_MAX_LIMIT = 50


def disabled_fusion_status() -> FusionStatus:
    return FusionStatus(
        enabled=False,
        available=False,
        state=FusionState.DISABLED,
        capabilities=[],
        reason="disabled",
    )


def _container() -> ServiceContainer:
    return get_container()


def _client(container: ServiceContainer = Depends(_container)) -> OpenMAICFusionClient:
    """构造内部客户端。

    配置取自容器而不是应用级单例：路由的其它依赖都走容器，混用两套配置源会让
    测试里的覆盖静默失效（真实症状是"开关明明是开的却报未启用"）。
    """
    settings = container.settings
    return OpenMAICFusionClient(
        base_url=settings.openmaic_service_url,
        secret=settings.openmaic_internal_secret,
        timeout_seconds=settings.openmaic_service_timeout_seconds,
    )


def _service(container: ServiceContainer = Depends(_container)) -> OpenMAICClassroomService:
    return container.openmaic_classroom_service


@router.get("/status", response_model=FusionStatus)
async def fusion_status(
    user: UserRow = Depends(current_user),
    client: OpenMAICFusionClient = Depends(_client),
) -> FusionStatus:
    if not container.settings.openmaic_fusion_enabled:
        return disabled_fusion_status()
    return await client.status(user_id=str(user.id))


@router.get("/recent", response_model=FusionRecentOut)
async def fusion_recent(
    limit: int = Query(RECENT_DEFAULT_LIMIT, ge=1, le=RECENT_MAX_LIMIT),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    service: OpenMAICClassroomService = Depends(_service),
) -> FusionRecentOut:
    """当前用户**所有可见课程**的最近学习内容（一次请求替代按课程轮询）。

    课程可见性走与课程详情/互动课堂完全相同的策略（`can_view_course`），
    因此这里不会出现别的用户的记录，也不会出现该用户已失去访问权的课程。
    """
    course_names = _course_name_resolver(container, user)
    rows = service.list_recent(
        user_id=str(user.id),
        course_name_of=course_names,
        limit=limit,
    )
    return FusionRecentOut(
        items=[FusionRecentItem(**row) for row in rows],
        limit=limit,
        # 已经按 limit 截断，只有拿满才可能还有更多。
        has_more=len(rows) >= limit,
    )


def _course_name_resolver(container: ServiceContainer, user: UserRow):
    """返回 `course_id -> 课程名`（不可见时 None），并缓存本次请求内的判定。"""
    cache: dict[str, Optional[str]] = {}

    def resolve(course_id: str) -> Optional[str]:
        if course_id not in cache:
            course = container.course_repository.get_course(course_id)
            if course is None or not can_view_course(container, user, course):
                cache[course_id] = None
            else:
                cache[course_id] = course.name or "课程"
        return cache[course_id]

    return resolve


__all__ = [
    "RECENT_DEFAULT_LIMIT",
    "RECENT_MAX_LIMIT",
    "disabled_fusion_status",
    "fusion_recent",
    "fusion_status",
    "router",
]

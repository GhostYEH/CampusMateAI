"""全校活动路由。

管理员负责创建、发布和结束活动；学生与教师只读取已发布活动。
活动与课程通知分表保存，避免权限和受众混淆。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from ...core.exceptions import NotFoundError
from ...models.multi_role import CampusActivityRow, UserRow
from ...schemas.multi_role import (
    CampusActivityCreate,
    CampusActivityOut,
    CampusActivityUpdate,
    Page,
)
from ...services.container import ServiceContainer, get_container
from ..deps import current_user, require_role

router = APIRouter(tags=["activities"])


def _container() -> ServiceContainer:
    return get_container()


def _to_out(
    row: CampusActivityRow,
    container: ServiceContainer,
) -> CampusActivityOut:
    author = container.user_repository.get_user_by_id(row.author_id)
    return CampusActivityOut(
        id=row.id,
        author_id=row.author_id,
        author_name=(author.display_name or author.username) if author else None,
        title=row.title,
        summary=row.summary,
        content=row.content,
        category=row.category,
        location=row.location,
        registration_deadline=row.registration_deadline,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        capacity=row.capacity,
        status=row.status,
        published_at=row.published_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/activities", response_model=Page)
def list_activities(
    status: Optional[str] = Query(
        None,
        pattern="^(draft|published|closed|archived)$",
    ),
    query: Optional[str] = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    visible_status = status if user.role == "admin" else "published"
    rows, total = container.campus_activity_repository.list_activities(
        status=visible_status,
        query=query,
        page=page,
        page_size=page_size,
    )
    return Page.from_rows(
        [_to_out(row, container) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/admin/activities", response_model=CampusActivityOut, status_code=201)
def create_activity(
    req: CampusActivityCreate,
    user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> CampusActivityOut:
    row = container.campus_activity_repository.create_activity(
        author_id=user.id,
        **req.model_dump(),
    )
    return _to_out(row, container)


@router.patch("/admin/activities/{activity_id}", response_model=CampusActivityOut)
def update_activity(
    activity_id: str,
    req: CampusActivityUpdate,
    user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> CampusActivityOut:
    row = container.campus_activity_repository.update_activity(
        activity_id,
        fields=req.model_dump(exclude_unset=True),
    )
    if row is None:
        raise NotFoundError("活动不存在")
    return _to_out(row, container)


@router.post(
    "/admin/activities/{activity_id}/publish",
    response_model=CampusActivityOut,
)
def publish_activity(
    activity_id: str,
    user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> CampusActivityOut:
    row = container.campus_activity_repository.update_activity(
        activity_id,
        fields={"status": "published"},
    )
    if row is None:
        raise NotFoundError("活动不存在")
    return _to_out(row, container)


@router.post(
    "/admin/activities/{activity_id}/close",
    response_model=CampusActivityOut,
)
def close_activity(
    activity_id: str,
    user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> CampusActivityOut:
    row = container.campus_activity_repository.update_activity(
        activity_id,
        fields={"status": "closed"},
    )
    if row is None:
        raise NotFoundError("活动不存在")
    return _to_out(row, container)


__all__ = ["router"]

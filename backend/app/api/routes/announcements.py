"""通知路由 — 列表/创建/详情/更新/发布/已读/已读统计。

权限:
- 列表: 学生只看已发布(published)通知;教师/管理员可看草稿。
- 创建: 仅教师或管理员(教师须为本班级负责教师)。
- 发布: 仅作者或管理员。
- 已读: 学生标记自己的已读记录(幂等)。
- 已读统计: 仅教师或管理员。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from ...core.exceptions import (
    AnnouncementNotFound,
    ClassGroupNotFound,
    Forbidden,
)
from ...models.multi_role import AnnouncementRow, UserRow
from ...schemas.multi_role import (
    AnnouncementCreate,
    AnnouncementOut,
    AnnouncementUpdate,
    Page,
    ReadReceiptOut,
    ReadStatusOut,
)
from ...services.container import ServiceContainer, get_container
from ..deps import current_user
from .classes import _assert_can_manage_class, _assert_can_view_class

router = APIRouter(tags=["announcements"])


def _container() -> ServiceContainer:
    return get_container()


def _announcement_to_out(
    ann: AnnouncementRow,
    *,
    author_name: Optional[str] = None,
    has_read: Optional[bool] = None,
) -> AnnouncementOut:
    return AnnouncementOut(
        id=ann.id,
        class_group_id=ann.class_group_id,
        author_id=ann.author_id,
        author_name=author_name,
        title=ann.title,
        content=ann.content,
        require_read=ann.require_read,
        status=ann.status,
        published_at=ann.published_at,
        created_at=ann.created_at,
        updated_at=ann.updated_at,
        has_read=has_read,
    )


def _author_name(container: ServiceContainer, author_id: str) -> Optional[str]:
    u = container.user_repository.get_user_by_id(author_id)
    if u is None:
        return None
    return u.display_name or u.username


@router.get("/classes/{class_id}/announcements", response_model=Page)
def list_announcements(
    class_id: str,
    status: Optional[str] = Query(None, pattern="^(draft|published|archived)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    cls = container.class_group_repository.get_class(class_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_view_class(cls, user, container)
    # 学生只能看 published
    if user.role == "student":
        status_filter = "published"
    else:
        status_filter = status  # 教师可看草稿等
    rows, total = container.announcement_repository.list_announcements(
        class_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    items: List[AnnouncementOut] = []
    for r in rows:
        has_read: Optional[bool] = None
        if user.role == "student":
            has_read = container.announcement_repository.is_read(r.id, user.id)
        items.append(_announcement_to_out(r, author_name=_author_name(container, r.author_id), has_read=has_read))
    return Page.from_rows(items, total=total, page=page, page_size=page_size)





@router.get("/announcements/{announcement_id}", response_model=AnnouncementOut)
def get_announcement(
    announcement_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AnnouncementOut:
    ann = container.announcement_repository.get_announcement(announcement_id)
    if ann is None:
        raise AnnouncementNotFound()
    cls = container.class_group_repository.get_class(ann.class_group_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_view_class(cls, user, container)
    # 学生不能看草稿
    if user.role == "student" and ann.status != "published":
        raise AnnouncementNotFound()
    has_read = (
        container.announcement_repository.is_read(ann.id, user.id)
        if user.role == "student"
        else None
    )
    return _announcement_to_out(ann, author_name=_author_name(container, ann.author_id), has_read=has_read)





@router.post("/announcements/{announcement_id}/read")
def mark_announcement_read(
    announcement_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> dict:
    ann = container.announcement_repository.get_announcement(announcement_id)
    if ann is None:
        raise AnnouncementNotFound()
    cls = container.class_group_repository.get_class(ann.class_group_id)
    if cls is None:
        raise ClassGroupNotFound()
    # 仅学生可标记已读(教师不需要)
    if user.role != "student":
        return {"ok": True, "message": "无需标记已读"}
    _assert_can_view_class(cls, user, container)
    if ann.status != "published":
        raise AnnouncementNotFound()
    first_time = container.announcement_repository.mark_read(ann.id, user.id)
    return {"ok": True, "first_time": first_time}


__all__ = ["router"]

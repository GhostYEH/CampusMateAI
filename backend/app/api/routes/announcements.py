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


@router.post("/classes/{class_id}/announcements", response_model=AnnouncementOut, status_code=201)
def create_announcement(
    class_id: str,
    req: AnnouncementCreate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AnnouncementOut:
    cls = container.class_group_repository.get_class(class_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_manage_class(cls, user, container)
    ann = container.announcement_repository.create_announcement(
        class_group_id=class_id,
        author_id=user.id,
        title=req.title,
        content=req.content,
        require_read=req.require_read,
        status=req.status,
    )
    return _announcement_to_out(ann, author_name=user.display_name or user.username)


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


@router.patch("/announcements/{announcement_id}", response_model=AnnouncementOut)
def update_announcement(
    announcement_id: str,
    req: AnnouncementUpdate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AnnouncementOut:
    ann = container.announcement_repository.get_announcement(announcement_id)
    if ann is None:
        raise AnnouncementNotFound()
    cls = container.class_group_repository.get_class(ann.class_group_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_manage_class(cls, user, container)
    if ann.author_id != user.id and user.role != "admin":
        raise Forbidden("只能修改自己发布的通知")
    fields = req.model_dump(exclude_unset=True)
    updated = container.announcement_repository.update_announcement(announcement_id, fields=fields)
    if updated is None:
        raise AnnouncementNotFound()
    return _announcement_to_out(updated, author_name=_author_name(container, updated.author_id))


@router.post("/announcements/{announcement_id}/publish", response_model=AnnouncementOut)
def publish_announcement(
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
    _assert_can_manage_class(cls, user, container)
    if ann.author_id != user.id and user.role != "admin":
        raise Forbidden("只能发布自己创建的通知")
    updated = container.announcement_repository.publish(announcement_id)
    if updated is None:
        from ...core.exceptions import InvalidTransition
        raise InvalidTransition("通知当前状态不允许发布")
    return _announcement_to_out(updated, author_name=_author_name(container, updated.author_id))


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


@router.get("/announcements/{announcement_id}/read-status", response_model=ReadStatusOut)
def announcement_read_status(
    announcement_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> ReadStatusOut:
    ann = container.announcement_repository.get_announcement(announcement_id)
    if ann is None:
        raise AnnouncementNotFound()
    cls = container.class_group_repository.get_class(ann.class_group_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_manage_class(cls, user, container)
    total = container.enrollment_repository.count_members(ann.class_group_id)
    read_count = container.announcement_repository.count_reads(ann.id)
    receipts = container.announcement_repository.list_read_receipts(ann.id)
    return ReadStatusOut(
        announcement_id=ann.id,
        total_recipients=total,
        read_count=read_count,
        unread_count=max(0, total - read_count),
        receipts=[ReadReceiptOut(**r) for r in receipts],
    )


@router.delete("/announcements/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> dict:
    """刪除通知。

    權限:
    - 僅作者本人或管理員可刪除。
    - 已發佈通知需先歸檔(PATCH status=archived)再刪除,避免誤刪線上通知。
    - 草稿與已歸檔通知可直接刪除。

    安全:
    - 不暴露其他班級通知的存在性(404 統一)。
    """
    ann = container.announcement_repository.get_announcement(announcement_id)
    if ann is None:
        raise AnnouncementNotFound()
    cls = container.class_group_repository.get_class(ann.class_group_id)
    if cls is None:
        raise AnnouncementNotFound()
    _assert_can_manage_class(cls, user, container)
    if ann.author_id != user.id and user.role != "admin":
        raise Forbidden("只能刪除自己發佈的通知")
    if ann.status == "published":
        from ...core.exceptions import InvalidTransition
        raise InvalidTransition("已發佈通知請先歸檔再刪除")
    ok = container.announcement_repository.delete_announcement(announcement_id)
    if not ok:
        raise AnnouncementNotFound()
    return {"ok": True, "message": "通知已刪除"}


__all__ = ["router"]

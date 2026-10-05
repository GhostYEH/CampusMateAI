"""班级公告读取与已读记录；仅限已加入班级的已发布公告。"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from ...core.exceptions import (
    AnnouncementNotFound,
    ClassGroupNotFound,
)
from ...models.multi_role import AnnouncementRow, UserRow
from ...schemas.multi_role import (
    AnnouncementOut,
    Page,
)
from ...services.container import ServiceContainer, get_container
from ..deps import current_user
from .classes import _assert_can_view_class

router = APIRouter(tags=["课程公告"])


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


@router.get(
    "/classes/{class_id}/announcements",
    response_model=Page,
    summary="列出班级公告",
    responses={
        200: {
            "description": "班级公告分页列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "公告列表",
                            "value": {
                                "items": [
                                    {
                                        "id": "ann_001",
                                        "class_group_id": "class_001",
                                        "author_id": "u_teacher",
                                        "author_name": "张老师",
                                        "title": "关于期中考试的通知",
                                        "content": "期中考试定于第 8 周周三进行。",
                                        "require_read": True,
                                        "status": "published",
                                        "published_at": "2026-09-20T08:00:00+00:00",
                                        "created_at": "2026-09-20T07:00:00+00:00",
                                        "updated_at": "2026-09-20T08:00:00+00:00",
                                        "has_read": False,
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
        },
    },
)
def list_announcements(
    class_id: str,
    status: Optional[str] = Query(None, pattern="^(draft|published|archived)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    """列出班级公告。

    - 学生只能看到 published 公告，教师可按 status 查看草稿等。
    - 班级不存在返回 404（CLASS_GROUP_NOT_FOUND）。
    """
    cls = container.class_group_repository.get_class(class_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_view_class(cls, user, container)
    # 学生只能看 published
    if user.role == "student":
        status_filter = "published"
    else:
        status_filter = status  # 教师可看草稿等
    rows, total = container.announcement_repository.list_announcements_for_user(
        class_id,
        status=status_filter,
        page=page,
        page_size=page_size,
        student_id=user.id if user.role == "student" else None,
    )
    items: List[AnnouncementOut] = []
    for r, author_name, has_read in rows:
        items.append(_announcement_to_out(r, author_name=author_name, has_read=has_read))
    return Page.from_rows(items, total=total, page=page, page_size=page_size)





@router.get(
    "/announcements/{announcement_id}",
    response_model=AnnouncementOut,
    summary="读取公告详情",
    responses={
        200: {
            "description": "公告详情",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "公告详情",
                            "value": {
                                "id": "ann_001",
                                "class_group_id": "class_001",
                                "author_id": "u_teacher",
                                "author_name": "张老师",
                                "title": "关于期中考试的通知",
                                "content": "期中考试定于第 8 周周三进行。",
                                "require_read": True,
                                "status": "published",
                                "published_at": "2026-09-20T08:00:00+00:00",
                                "created_at": "2026-09-20T07:00:00+00:00",
                                "updated_at": "2026-09-20T08:00:00+00:00",
                                "has_read": False,
                            },
                        }
                    }
                }
            },
        },
    },
)
def get_announcement(
    announcement_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AnnouncementOut:
    """读取单条公告详情。

    - 公告不存在或学生读取非 published 公告返回 404（ANNOUNCEMENT_NOT_FOUND）。
    - 班级不存在返回 404（CLASS_GROUP_NOT_FOUND）。
    """
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





@router.post(
    "/announcements/{announcement_id}/read",
    summary="标记公告已读",
    responses={
        200: {
            "description": "标记结果；first_time 表示本次是否为首次标记已读",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "首次标记已读",
                            "value": {"ok": True, "first_time": True},
                        }
                    }
                }
            },
        },
    },
)
def mark_announcement_read(
    announcement_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> dict:
    """标记公告为已读。

    - 仅学生需要标记；教师调用直接返回 {"ok": true, "message": "无需标记已读"}。
    - 公告不存在或学生标记非 published 公告返回 404（ANNOUNCEMENT_NOT_FOUND）。
    """
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

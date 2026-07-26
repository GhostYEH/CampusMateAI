"""任务路由 — 列表/创建/详情/更新/发布/关闭/统计/学生状态。

权限:
- 列表: 学生只看已发布任务;教师/管理员可看草稿。
- 创建/更新/发布/关闭: 教师(须为本班级负责教师)或管理员。
- 统计/student-status: 教师或管理员。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from ...core.exceptions import (
    AssignmentNotFound,
    ClassGroupNotFound,
    Forbidden,
    InvalidTransition,
)
from ...models.multi_role import AssignmentRow, UserRow
from ...schemas.multi_role import (
    AssignmentCreate,
    AssignmentOut,
    AssignmentStatsOut,
    AssignmentUpdate,
    Page,
    StudentStatusItem,
)
from ...services.container import ServiceContainer, get_container
from ..deps import current_user
from .classes import _assert_can_manage_class, _assert_can_view_class

router = APIRouter(tags=["assignments"])


def _container() -> ServiceContainer:
    return get_container()


def _assignment_to_out(
    a: AssignmentRow,
    *,
    author_name: Optional[str] = None,
) -> AssignmentOut:
    types = []
    if a.submission_types:
        try:
            types = json.loads(a.submission_types)
            if not isinstance(types, list):
                types = []
        except (ValueError, TypeError):
            types = []
    return AssignmentOut(
        id=a.id,
        class_group_id=a.class_group_id,
        author_id=a.author_id,
        author_name=author_name,
        title=a.title,
        description=a.description,
        deadline=a.deadline,
        submission_types=types,
        max_score=a.max_score,
        allow_resubmit=a.allow_resubmit,
        status=a.status,
        published_at=a.published_at,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


def _author_name(container: ServiceContainer, author_id: str) -> Optional[str]:
    u = container.user_repository.get_user_by_id(author_id)
    if u is None:
        return None
    return u.display_name or u.username


@router.get("/classes/{class_id}/assignments", response_model=Page)
def list_assignments(
    class_id: str,
    status: Optional[str] = Query(None, pattern="^(draft|published|closed|archived)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    cls = container.class_group_repository.get_class(class_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_view_class(cls, user, container)
    status_filter = "published" if user.role == "student" else status
    rows, total = container.assignment_repository.list_assignments(
        class_id, status=status_filter, page=page, page_size=page_size,
    )
    items = [_assignment_to_out(r, author_name=_author_name(container, r.author_id)) for r in rows]
    return Page.from_rows(items, total=total, page=page, page_size=page_size)


@router.post("/classes/{class_id}/assignments", response_model=AssignmentOut, status_code=201)
def create_assignment(
    class_id: str,
    req: AssignmentCreate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AssignmentOut:
    cls = container.class_group_repository.get_class(class_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_manage_class(cls, user, container)
    a = container.assignment_repository.create_assignment(
        class_group_id=class_id,
        author_id=user.id,
        title=req.title,
        description=req.description,
        deadline=req.deadline,
        submission_types=req.submission_types,
        max_score=req.max_score,
        allow_resubmit=req.allow_resubmit,
        status=req.status,
    )
    return _assignment_to_out(a, author_name=user.display_name or user.username)


@router.get("/assignments/{assignment_id}", response_model=AssignmentOut)
def get_assignment(
    assignment_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AssignmentOut:
    a = container.assignment_repository.get_assignment(assignment_id)
    if a is None:
        raise AssignmentNotFound()
    cls = container.class_group_repository.get_class(a.class_group_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_view_class(cls, user, container)
    if user.role == "student" and a.status not in ("published", "closed"):
        raise AssignmentNotFound()
    return _assignment_to_out(a, author_name=_author_name(container, a.author_id))


@router.patch("/assignments/{assignment_id}", response_model=AssignmentOut)
def update_assignment(
    assignment_id: str,
    req: AssignmentUpdate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AssignmentOut:
    a = container.assignment_repository.get_assignment(assignment_id)
    if a is None:
        raise AssignmentNotFound()
    cls = container.class_group_repository.get_class(a.class_group_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_manage_class(cls, user, container)
    if a.author_id != user.id and user.role != "admin":
        raise Forbidden("只能修改自己创建的任务")
    fields = req.model_dump(exclude_unset=True)
    updated = container.assignment_repository.update_assignment(assignment_id, fields=fields)
    if updated is None:
        raise AssignmentNotFound()
    return _assignment_to_out(updated, author_name=_author_name(container, updated.author_id))


@router.post("/assignments/{assignment_id}/publish", response_model=AssignmentOut)
def publish_assignment(
    assignment_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AssignmentOut:
    a = container.assignment_repository.get_assignment(assignment_id)
    if a is None:
        raise AssignmentNotFound()
    cls = container.class_group_repository.get_class(a.class_group_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_manage_class(cls, user, container)
    if a.author_id != user.id and user.role != "admin":
        raise Forbidden("只能发布自己创建的任务")
    updated = container.assignment_repository.publish(assignment_id)
    if updated is None:
        raise InvalidTransition("任务当前状态不允许发布")
    return _assignment_to_out(updated, author_name=_author_name(container, updated.author_id))


@router.post("/assignments/{assignment_id}/close", response_model=AssignmentOut)
def close_assignment(
    assignment_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AssignmentOut:
    a = container.assignment_repository.get_assignment(assignment_id)
    if a is None:
        raise AssignmentNotFound()
    cls = container.class_group_repository.get_class(a.class_group_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_manage_class(cls, user, container)
    if a.author_id != user.id and user.role != "admin":
        raise Forbidden("只能关闭自己创建的任务")
    updated = container.assignment_repository.close(assignment_id)
    if updated is None:
        raise InvalidTransition("任务当前状态不允许关闭")
    return _assignment_to_out(updated, author_name=_author_name(container, updated.author_id))


@router.get("/assignments/{assignment_id}/stats", response_model=AssignmentStatsOut)
def assignment_stats(
    assignment_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> AssignmentStatsOut:
    a = container.assignment_repository.get_assignment(assignment_id)
    if a is None:
        raise AssignmentNotFound()
    cls = container.class_group_repository.get_class(a.class_group_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_manage_class(cls, user, container)
    total_students = container.enrollment_repository.count_members(a.class_group_id)
    stats = container.submission_repository.assignment_stats(
        assignment_id, total_students=total_students
    )
    return AssignmentStatsOut(**stats)


@router.get("/assignments/{assignment_id}/student-status", response_model=Page)
def assignment_student_status(
    assignment_id: str,
    submission_status: Optional[str] = Query(
        None,
        description="not_submitted|draft|submitted|resubmitted|late",
    ),
    read_status: Optional[str] = Query(None, pattern="^(read|unread)$"),
    query: Optional[str] = Query(None, description="按姓名/学号搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    a = container.assignment_repository.get_assignment(assignment_id)
    if a is None:
        raise AssignmentNotFound()
    cls = container.class_group_repository.get_class(a.class_group_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_manage_class(cls, user, container)
    rows, total = container.submission_repository.student_status(
        assignment_id=a.id,
        class_group_id=a.class_group_id,
        submission_status=submission_status,
        read_status=read_status,
        query=query,
        page=page,
        page_size=page_size,
    )
    items = [StudentStatusItem(**r) for r in rows]
    return Page.from_rows(items, total=total, page=page, page_size=page_size)


__all__ = ["router"]

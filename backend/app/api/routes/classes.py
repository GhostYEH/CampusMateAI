"""班级列表、详情、加入和成员读取；仅限已加入的班级。"""
from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ...core.exceptions import (
    AlreadyEnrolled,
    ClassGroupFull,
    ClassGroupNotFound,
    Forbidden,
    InvalidInviteCode,
)
from ...models.multi_role import ClassGroupRow, UserRow
from ...schemas.multi_role import (
    ClassJoinRequest,
    ClassMemberOut,
    ClassOut,
    Page,
)
from ...services.container import ServiceContainer, get_container
from ..deps import current_user, require_role

router = APIRouter(tags=["classes"])


def _container() -> ServiceContainer:
    return get_container()


def _class_to_out(c: ClassGroupRow) -> ClassOut:
    return ClassOut(
        id=c.id,
        course_id=c.course_id,
        name=c.name,
        class_code=c.class_code,
        invite_code=c.invite_code,
        description=c.description,
        capacity=c.capacity,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("/classes", response_model=Page)
def list_classes(
    course_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    rows, total = container.enrollment_repository.list_user_class_page(
        user.id, course_id=course_id, page=page, page_size=page_size
    )
    return Page.from_rows([_class_to_out(row) for row in rows], total=total, page=page, page_size=page_size)


@router.get("/classes/{class_id}", response_model=ClassOut)
def get_class(
    class_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> ClassOut:
    cls = container.class_group_repository.get_class(class_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_view_class(cls, user, container)
    return _class_to_out(cls)


@router.post("/classes/{class_id}/join", response_model=ClassOut)
def join_class(
    class_id: str,
    req: ClassJoinRequest,
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> ClassOut:
    cls = container.class_group_repository.get_class(class_id)
    if cls is None:
        raise ClassGroupNotFound()
    # 邀请码必须匹配此班级(防止通过任意班级 id + 邀请码绕过)
    if cls.invite_code != req.invite_code:
        raise InvalidInviteCode()
    existing = container.enrollment_repository.get_enrollment(class_id, user.id)
    if existing is not None and existing.status == "active":
        raise AlreadyEnrolled()
    # 容量校验
    if cls.capacity is not None:
        current = container.enrollment_repository.count_members(class_id)
        if current >= cls.capacity:
            raise ClassGroupFull()
    if existing is not None and existing.status == "removed":
        container.enrollment_repository.reactivate(class_id, user.id)
    else:
        try:
            container.enrollment_repository.enroll(
                class_group_id=class_id,
                user_id=user.id,
                member_role="student",
            )
        except sqlite3.IntegrityError as exc:
            existing = container.enrollment_repository.get_enrollment(class_id, user.id)
            if (
                "unique constraint failed: enrollments.class_group_id, enrollments.user_id"
                not in str(exc).lower()
                or existing is None
                or existing.status != "active"
            ):
                raise
    return _class_to_out(cls)


@router.get("/classes/{class_id}/members", response_model=Page)
def list_members(
    class_id: str,
    query: Optional[str] = Query(None),
    member_role: Optional[str] = Query(None, pattern="^(student|teaching_assistant)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    cls = container.class_group_repository.get_class(class_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_view_class(cls, user, container)
    members, total = container.enrollment_repository.list_members(
        class_id,
        status="active",
        member_role=member_role,
        query=query,
        page=page,
        page_size=page_size,
    )
    items = [ClassMemberOut(**m) for m in members]
    return Page.from_rows(items, total=total, page=page, page_size=page_size)


# ===== 权限辅助 =====


def _assert_can_view_class(
    cls: ClassGroupRow, user: UserRow, container: ServiceContainer
) -> None:
    # 学生: 必须已加入
    enr = container.enrollment_repository.get_enrollment(cls.id, user.id)
    if enr is None or enr.status != "active":
        raise Forbidden("你未加入此班级")



__all__ = ["router"]

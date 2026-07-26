"""班级路由 — 列表/创建/详情/更新/加入/重置邀请码/成员管理。

权限:
- GET /classes: 教师只看自己课程下的班级;学生只看自己已加入的;管理员全部。
- POST /courses/{course_id}/classes: 仅课程教师或管理员。
- GET /classes/{id}: 教师必须为本课程教师;学生必须已加入;管理员任意。
- PATCH /classes/{id}: 仅教师或管理员。
- POST /classes/{id}/join: 学生凭邀请码加入。
- POST /classes/{id}/reset-invite-code: 教师/管理员。
- GET /classes/{id}/members: 教师/管理员可看全部,学生看同班同学。
- DELETE /classes/{id}/members/{user_id}: 教师/管理员。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from ...core.exceptions import (
    AlreadyEnrolled,
    ClassGroupFull,
    ClassGroupNotFound,
    CourseNotFound,
    Forbidden,
    InvalidInviteCode,
)
from ...models.multi_role import ClassGroupRow, UserRow
from ...schemas.multi_role import (
    ClassCreate,
    ClassJoinRequest,
    ClassMemberOut,
    ClassOut,
    ClassUpdate,
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
    teacher_id: Optional[str] = None
    if user.role == "teacher":
        teacher_id = user.id
    elif user.role == "student":
        # 学生只看自己已加入的班级
        enrolls = container.enrollment_repository.list_user_classes(user.id)
        items: List[ClassOut] = []
        for e in enrolls:
            if course_id and e["course_id"] != course_id:
                continue
            c = container.class_group_repository.get_class(e["class_id"])
            if c is None:
                continue
            items.append(_class_to_out(c))
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return Page(
            items=items[start:end],
            total=total,
            page=page,
            page_size=page_size,
            has_more=end < total,
        )
    rows, total = container.class_group_repository.list_classes(
        course_id=course_id,
        teacher_id=teacher_id,
        page=page,
        page_size=page_size,
    )
    items = [_class_to_out(r) for r in rows]
    return Page.from_rows(items, total=total, page=page, page_size=page_size)


@router.post("/courses/{course_id}/classes", response_model=ClassOut, status_code=201)
def create_class_under_course(
    course_id: str,
    req: ClassCreate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> ClassOut:
    course = container.course_repository.get_course(course_id)
    if course is None:
        raise CourseNotFound()
    if user.role != "admin" and course.teacher_id != user.id:
        raise Forbidden("无权在此课程下创建班级")
    cls = container.class_group_repository.create_class(
        course_id=course_id,
        name=req.name,
        class_code=req.class_code,
        description=req.description,
        capacity=req.capacity,
    )
    # 教师自动成为该班级的 teaching_assistant(便于后续权限校验)
    try:
        container.enrollment_repository.enroll(
            class_group_id=cls.id,
            user_id=user.id,
            member_role="teaching_assistant",
        )
    except Exception:
        pass
    return _class_to_out(cls)


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


@router.patch("/classes/{class_id}", response_model=ClassOut)
def update_class(
    class_id: str,
    req: ClassUpdate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> ClassOut:
    cls = container.class_group_repository.get_class(class_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_manage_class(cls, user, container)
    fields = req.model_dump(exclude_unset=True)
    updated = container.class_group_repository.update_class(class_id, fields=fields)
    if updated is None:
        raise ClassGroupNotFound()
    return _class_to_out(updated)


@router.post("/classes/{class_id}/join", response_model=ClassOut)
def join_class(
    class_id: str,
    req: ClassJoinRequest,
    user: UserRow = Depends(require_role("student", "admin")),
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
        except Exception:
            # 重复插入忽略
            pass
    return _class_to_out(cls)


@router.post("/classes/{class_id}/reset-invite-code", response_model=ClassOut)
def reset_invite_code(
    class_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> ClassOut:
    cls = container.class_group_repository.get_class(class_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_manage_class(cls, user, container)
    updated = container.class_group_repository.reset_invite_code(class_id)
    if updated is None:
        raise ClassGroupNotFound()
    return _class_to_out(updated)


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


@router.delete("/classes/{class_id}/members/{user_id}")
def remove_member(
    class_id: str,
    user_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> dict:
    cls = container.class_group_repository.get_class(class_id)
    if cls is None:
        raise ClassGroupNotFound()
    _assert_can_manage_class(cls, user, container)
    ok = container.enrollment_repository.remove_member(class_id, user_id)
    if not ok:
        # 不暴露具体原因(已移除/不存在)
        return {"ok": True, "message": "成员已不在班级中"}
    return {"ok": True, "message": "成员已移除"}


# ===== 权限辅助 =====


def _assert_can_view_class(
    cls: ClassGroupRow, user: UserRow, container: ServiceContainer
) -> None:
    if user.role == "admin":
        return
    if user.role == "teacher":
        course = container.course_repository.get_course(cls.course_id)
        if course is None or course.teacher_id != user.id:
            raise Forbidden("无权查看此班级")
        return
    # 学生: 必须已加入
    enr = container.enrollment_repository.get_enrollment(cls.id, user.id)
    if enr is None or enr.status != "active":
        raise Forbidden("你未加入此班级")


def _assert_can_manage_class(
    cls: ClassGroupRow, user: UserRow, container: ServiceContainer
) -> None:
    if user.role == "admin":
        return
    if user.role == "teacher":
        course = container.course_repository.get_course(cls.course_id)
        if course is None or course.teacher_id != user.id:
            raise Forbidden("无权管理此班级")
        return
    raise Forbidden("学生无权管理班级")


__all__ = ["router"]

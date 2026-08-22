"""课程路由 — 列表/创建/详情/更新。

权限:
- GET /courses: 学生看到自己已加入班级所属的课程;管理员看到全部。
- POST /courses: 仅管理员(CampusMate AI 不存在教师角色,课程由管理员维护)。
- GET /courses/{id}: 学生只看自己班级所属课程;管理员任意。
- PATCH /courses/{id}: 仅管理员。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from ...core.exceptions import CourseNotFound, Forbidden
from ...models.multi_role import CourseRow, UserRow
from ...schemas.multi_role import CourseCreate, CourseOut, CourseUpdate, Page
from ...services.container import ServiceContainer, get_container
from ..deps import current_user, require_role

router = APIRouter(prefix="/courses", tags=["courses"])


def _container() -> ServiceContainer:
    return get_container()


def _course_to_out(
    course: CourseRow,
    teacher_name: Optional[str] = None,
) -> CourseOut:
    return CourseOut(
        id=course.id,
        name=course.name,
        code=course.code,
        semester=course.semester,
        description=course.description,
        teacher_id=course.teacher_id,
        teacher_name=teacher_name,
        provider=course.provider,
        external_id=course.external_id,
        source_url=course.source_url,
        last_synced_at=course.last_synced_at,
        status=course.status,
        created_at=course.created_at,
        updated_at=course.updated_at,
        owner_user_id=course.owner_user_id,
    )


@router.get("", response_model=Page)
def list_courses(
    query: Optional[str] = Query(None, description="按名称/代码/描述模糊搜索"),
    status: Optional[str] = Query(None, pattern="^(draft|active|archived)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    if user.role == "student":
        # 学生只看自己已加入班级所属的课程
        course_ids = set()
        enrolls = container.enrollment_repository.list_user_classes(user.id)
        for e in enrolls:
            course_ids.add(e["course_id"])
        # Learning Tong courses are private imports owned by the student via
        # owner_user_id. They do not have a campus class enrollment, so exposing
        # only enrollment-backed courses made a successful sync invisible to the
        # Android client.
        imported, _ = container.course_repository.list_courses(
            owner_user_id=user.id,
            page=1,
            page_size=1000,
        )
        course_ids.update(course.id for course in imported if course.provider == "chaoxing")
        if not course_ids:
            return Page(items=[], total=0, page=page, page_size=page_size, has_more=False)
        items: List[CourseOut] = []
        for cid in course_ids:
            c = container.course_repository.get_course(cid)
            if c is None:
                continue
            if status and c.status != status:
                continue
            if query and not _course_matches_query(c, query):
                continue
            teacher_name = c.remote_teacher_name or _teacher_name(container, c.teacher_id)
            items.append(_course_to_out(c, teacher_name))
        items.sort(key=lambda x: x.created_at, reverse=True)
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

    # admin: 全部课程
    rows, total = container.course_repository.list_courses(
        teacher_id=None,
        status=status,
        query=query,
        page=page,
        page_size=page_size,
    )
    items = [_course_to_out(r, r.remote_teacher_name or _teacher_name(container, r.teacher_id)) for r in rows]
    return Page.from_rows(items, total=total, page=page, page_size=page_size)


def _course_matches_query(c: CourseRow, q: str) -> bool:
    ql = q.lower()
    if ql in (c.name or "").lower():
        return True
    if c.code and ql in c.code.lower():
        return True
    if c.description and ql in c.description.lower():
        return True
    return False


def _teacher_name(container: ServiceContainer, teacher_id: Optional[str]) -> Optional[str]:
    """查询课程负责人姓名(兼容旧 teacher_id 字段,可能指向已降级用户)。"""
    if not teacher_id:
        return None
    u = container.user_repository.get_user_by_id(teacher_id)
    if u is None:
        return None
    return u.display_name or u.username


@router.post("", response_model=CourseOut, status_code=201)
def create_course(
    req: CourseCreate,
    user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> CourseOut:
    course = container.course_repository.create_course(
        name=req.name,
        teacher_id=user.id,
        code=req.code,
        semester=req.semester,
        description=req.description,
        status=req.status,
    )
    return _course_to_out(course, user.display_name or user.username)


@router.get("/{course_id}", response_model=CourseOut)
def get_course(
    course_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> CourseOut:
    course = container.course_repository.get_course(course_id)
    if course is None:
        raise CourseNotFound()
    _assert_can_view_course(course, user, container)
    return _course_to_out(course, course.remote_teacher_name or _teacher_name(container, course.teacher_id))


@router.patch("/{course_id}", response_model=CourseOut)
def update_course(
    course_id: str,
    req: CourseUpdate,
    user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> CourseOut:
    course = container.course_repository.get_course(course_id)
    if course is None:
        raise CourseNotFound()
    fields = req.model_dump(exclude_unset=True)
    updated = container.course_repository.update_course(course_id, fields=fields)
    if updated is None:
        raise CourseNotFound()
    return _course_to_out(updated, updated.remote_teacher_name or _teacher_name(container, updated.teacher_id))


def _assert_can_view_course(
    course: CourseRow, user: UserRow, container: ServiceContainer
) -> None:
    if user.role == "admin":
        return
    # 学生: 必须已加入该课程下的任一班级
    enrolls = container.enrollment_repository.list_user_classes(user.id)
    if course.provider == "chaoxing" and course.owner_user_id == user.id:
        return
    if not any(e["course_id"] == course.id for e in enrolls):
        raise Forbidden("你未加入此课程下的任何班级")


__all__ = ["router"]

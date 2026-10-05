"""课程只读接口，按已加入班级或本人导入的课程限定访问范围。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from ...core.exceptions import CourseNotFound, Forbidden
from ...models.multi_role import CourseRow, UserRow
from ...schemas.multi_role import CourseOut, Page
from ...services.container import ServiceContainer, get_container
from ...services.course_access import can_view_course
from ..deps import current_user

router = APIRouter(prefix="/courses", tags=["课程"])


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


@router.get(
    "",
    response_model=Page,
    summary="列出课程",
    responses={
        200: {
            "description": "课程分页列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "课程列表",
                            "value": {
                                "items": [
                                    {
                                        "id": "course_001",
                                        "name": "高等数学",
                                        "code": "MATH101",
                                        "semester": "2026-2027-1",
                                        "description": "微积分与线性代数基础",
                                        "teacher_id": "u_teacher",
                                        "teacher_name": "张老师",
                                        "provider": "chaoxing",
                                        "external_id": "cx_1001",
                                        "source_url": "https://mooc.example.com/course/1001",
                                        "last_synced_at": "2026-09-30T01:00:00+00:00",
                                        "status": "active",
                                        "created_at": "2026-09-01T08:00:00+00:00",
                                        "updated_at": "2026-09-30T01:00:00+00:00",
                                        "owner_user_id": "u_teacher",
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
def list_courses(
    query: Optional[str] = Query(None, description="按名称/代码/描述模糊搜索"),
    status: Optional[str] = Query(None, pattern="^(draft|active|archived)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> Page:
    """列出当前用户可见的课程。

    - 学生仅返回已加入班级关联的课程，教师返回自有的全部课程。
    - 支持 query 按名称/代码/描述模糊搜索，status 过滤 draft/active/archived，分页返回。
    """
    rows, total = container.course_repository.list_courses(
        status=status,
        query=query,
        student_id=user.id if user.role == "student" else None,
        page=page,
        page_size=page_size,
    )
    names = container.user_repository.get_display_names(
        [row.teacher_id for row in rows if row.teacher_id and not row.remote_teacher_name]
    )
    items = [
        _course_to_out(row, row.remote_teacher_name or names.get(row.teacher_id))
        for row in rows
    ]
    return Page.from_rows(items, total=total, page=page, page_size=page_size)


def _teacher_name(container: ServiceContainer, teacher_id: Optional[str]) -> Optional[str]:
    """查询课程负责人姓名(兼容旧 teacher_id 字段,可能指向已降级用户)。"""
    if not teacher_id:
        return None
    u = container.user_repository.get_user_by_id(teacher_id)
    if u is None:
        return None
    return u.display_name or u.username


@router.get(
    "/{course_id}",
    response_model=CourseOut,
    summary="读取课程详情",
    responses={
        200: {
            "description": "课程详情",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "课程详情",
                            "value": {
                                "id": "course_001",
                                "name": "高等数学",
                                "code": "MATH101",
                                "semester": "2026-2027-1",
                                "description": "微积分与线性代数基础",
                                "teacher_id": "u_teacher",
                                "teacher_name": "张老师",
                                "provider": "chaoxing",
                                "external_id": "cx_1001",
                                "source_url": "https://mooc.example.com/course/1001",
                                "last_synced_at": "2026-09-30T01:00:00+00:00",
                                "status": "active",
                                "created_at": "2026-09-01T08:00:00+00:00",
                                "updated_at": "2026-09-30T01:00:00+00:00",
                                "owner_user_id": "u_teacher",
                            },
                        }
                    }
                }
            },
        },
    },
)
def get_course(
    course_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> CourseOut:
    """读取单个课程详情。

    - 课程不存在返回 404（COURSE_NOT_FOUND）。
    - 未加入该课程下的任何班级返回 403（FORBIDDEN）。
    """
    course = container.course_repository.get_course(course_id)
    if course is None:
        raise CourseNotFound()
    _assert_can_view_course(course, user, container)
    return _course_to_out(course, course.remote_teacher_name or _teacher_name(container, course.teacher_id))


def _assert_can_view_course(
    course: CourseRow, user: UserRow, container: ServiceContainer
) -> None:
    # 统一策略见 services/course_access.py：已加入班级 / 学生自有的学习通导入课程。
    if not can_view_course(container, user, course):
        raise Forbidden("你未加入此课程下的任何班级")


__all__ = ["router"]

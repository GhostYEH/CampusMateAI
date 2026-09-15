"""课程可见性统一策略。

全后端只有这一份"谁能看这门课"的判断，避免各路由各写一份导致策略漂移：
- `courses._assert_can_view_course`（课程详情/内容/知识图谱）
- `course_content._course`（课程内容与知识图谱）
- `openmaic.course_context.assert_course_access`（互动课堂）
- `counselor._collect_teaching_context`（CPM 课程上下文）

规则（学生）：
1. 已加入该课程下的任一班级（enrollment）；
2. 或者该课程是学生自己导入的外部课程（provider == "chaoxing" 且 owner_user_id == 本人）。

管理员放行。其它角色（历史 teacher 账号已降级为 student）按学生规则处理。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..models.multi_role import CourseRow, UserRow

if TYPE_CHECKING:
    from .container import ServiceContainer


def is_owner_imported_course(course: CourseRow, user: UserRow) -> bool:
    """该课程是否是当前学生自己导入的外部课程（学习通等）。"""
    return bool(course.provider == "chaoxing" and course.owner_user_id == user.id)


def is_enrolled_in_course(container: "ServiceContainer", user: UserRow, course_id: str) -> bool:
    """当前学生是否已加入该课程下的任一班级。"""
    enrollments = container.enrollment_repository.list_user_classes(user.id)
    return any(e.get("course_id") == course_id for e in enrollments)


def can_view_course(
    container: "ServiceContainer", user: UserRow, course: CourseRow
) -> bool:
    """统一课程可见性判定。不抛异常，只回答"能不能看"。"""
    if user.role == "admin":
        return True
    if is_owner_imported_course(course, user):
        return True
    return is_enrolled_in_course(container, user, course.id)


__all__ = [
    "can_view_course",
    "is_owner_imported_course",
    "is_enrolled_in_course",
]

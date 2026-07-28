"""工作台路由 — /student/dashboard 与 /teacher/dashboard。

设计目标: 一次返回必要摘要,不让前端连续请求十几个接口。
所有聚合均使用单条 SQL,避免 N+1。
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ...core.exceptions import Forbidden
from ...models.multi_role import UserRow
from ...repositories.personal_task_repository import _load_materials
from ...schemas.multi_role import StudentDashboard, TeacherDashboard
from ...services.container import ServiceContainer, get_container
from ..deps import current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _container() -> ServiceContainer:
    return get_container()


@router.get("/student", response_model=StudentDashboard)
def student_dashboard(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> StudentDashboard:
    if user.role == "teacher":
        raise Forbidden("教师无学生工作台")
    if user.role == "admin":
        # 管理员返回空摘要(不强制要求查看学生视图)
        return StudentDashboard(
            enrolled_course_count=0,
            unread_announcement_count=0,
            pending_assignment_count=0,
            overdue_assignment_count=0,
            due_soon_assignments=[],
            recent_announcements=[],
            pending_personal_task_count=0,
            overdue_personal_task_count=0,
            due_soon_personal_tasks=[],
        )
    now_iso = datetime.now(timezone.utc).isoformat()
    sub_repo = container.submission_repository
    asg_repo = container.assignment_repository
    ptask_repo = container.personal_task_repository

    enrolled = sub_repo.count_student_enrolled_courses(user.id)
    unread = sub_repo.count_student_unread_announcements(user.id)
    pending = sub_repo.count_student_pending_assignments(user.id, now_iso=now_iso)
    overdue = sub_repo.count_student_overdue_assignments(user.id, now_iso=now_iso)
    due_soon, _ = asg_repo.list_assignments_for_student(
        user.id, due_within_days=7, page=1, page_size=5
    )
    # 过滤出 deadline 在未来 7 天内
    due_soon_filtered = []
    now = datetime.now(timezone.utc)
    for item in due_soon:
        dl = item.get("deadline")
        if not dl:
            continue
        try:
            dl_dt = datetime.fromisoformat(dl.replace("Z", "+00:00"))
        except ValueError:
            continue
        days = (dl_dt - now).total_seconds() / 86400
        if 0 <= days <= 7:
            due_soon_filtered.append(item)
    # recent_student_announcements 实现位于 SubmissionRepository(复用班级/已读聚合查询)
    recent_anns = sub_repo.recent_student_announcements(user.id, limit=5)

    # 个人待办统计(来自 personal_tasks 表,严格按 user_id 隔离)
    pending_ptasks = ptask_repo.count_pending(user.id)
    overdue_ptasks = ptask_repo.count_overdue(user.id, now_iso=now_iso)
    recent_ptasks_rows = ptask_repo.list_recent_pending(user.id, limit=5)
    # 过滤出 deadline 在未来 7 天内(并加上无 deadline 的最近项)
    due_soon_ptasks: list[dict] = []
    no_deadline_ptasks: list[dict] = []
    for row in recent_ptasks_rows:
        item = _personal_task_to_dashboard_dict(row)
        if row.deadline is None:
            no_deadline_ptasks.append(item)
            continue
        try:
            dl_dt = datetime.fromisoformat(row.deadline.replace("Z", "+00:00"))
        except ValueError:
            no_deadline_ptasks.append(item)
            continue
        days = (dl_dt - now).total_seconds() / 86400
        if 0 <= days <= 7:
            due_soon_ptasks.append(item)
    # 若 7 天内任务不足 5 条,用无 deadline 的最近任务补齐
    remaining = 5 - len(due_soon_ptasks)
    if remaining > 0:
        due_soon_ptasks.extend(no_deadline_ptasks[:remaining])

    return StudentDashboard(
        enrolled_course_count=enrolled,
        unread_announcement_count=unread,
        pending_assignment_count=pending,
        overdue_assignment_count=overdue,
        due_soon_assignments=due_soon_filtered,
        recent_announcements=recent_anns,
        pending_personal_task_count=pending_ptasks,
        overdue_personal_task_count=overdue_ptasks,
        due_soon_personal_tasks=due_soon_ptasks,
    )


def _personal_task_to_dashboard_dict(row) -> dict:
    """将 PersonalTaskRow 转为 dashboard 字典(仅暴露必要字段)。"""
    return {
        "id": row.id,
        "title": row.title,
        "deadline": row.deadline,
        "priority": row.priority,
        "source_name": row.source_name,
        "source_notice_id": row.source_notice_id,
        "materials": _load_materials(row.materials),
        "reminder_minutes": row.reminder_minutes,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@router.get("/teacher", response_model=TeacherDashboard)
def teacher_dashboard(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> TeacherDashboard:
    if user.role == "student":
        raise Forbidden("学生无教师工作台")
    if user.role == "admin":
        # 管理员返回空摘要
        return TeacherDashboard(
            course_count=0,
            class_count=0,
            student_count=0,
            active_assignment_count=0,
            pending_submission_count=0,
            unread_announcement_count=0,
            overdue_student_count=0,
            recent_assignments=[],
            recent_activity=[],
        )
    now_iso = datetime.now(timezone.utc).isoformat()
    course_repo = container.course_repository
    class_repo = container.class_group_repository
    sub_repo = container.submission_repository
    asg_repo = container.assignment_repository

    course_count = course_repo.count_courses(teacher_id=user.id)
    class_count = class_repo.count_classes(teacher_id=user.id)
    student_count = sub_repo.count_teacher_students(teacher_id=user.id)
    active_assignments = asg_repo.count_active_assignments(teacher_id=user.id)
    pending_submissions = sub_repo.count_pending_submissions(teacher_id=user.id)
    unread_announcements = sub_repo.count_teacher_unread_announcements(teacher_id=user.id)
    overdue_students = sub_repo.count_teacher_overdue_students(
        teacher_id=user.id, now_iso=now_iso
    )
    recent_assignments = sub_repo.recent_teacher_assignments(teacher_id=user.id, limit=5)
    return TeacherDashboard(
        course_count=course_count,
        class_count=class_count,
        student_count=student_count,
        active_assignment_count=active_assignments,
        pending_submission_count=pending_submissions,
        unread_announcement_count=unread_announcements,
        overdue_student_count=overdue_students,
        recent_assignments=recent_assignments,
        recent_activity=[],  # 暂不实现(可后续扩展: 教师最近评分/发布等)
    )


__all__ = ["router"]

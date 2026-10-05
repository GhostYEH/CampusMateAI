"""Role-specific dashboard endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ...models.multi_role import UserRow
from ...schemas.multi_role import StudentDashboard
from ...services.container import ServiceContainer, get_container
from ..deps import require_role


router = APIRouter(prefix="/dashboard", tags=["工作台"])


def _container() -> ServiceContainer:
    return get_container()


@router.get(
    "/student",
    response_model=StudentDashboard,
    summary="获取学生工作台",
    responses={
        200: {
            "description": "返回当前学生的首页概览统计与最近条目",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "学生工作台概览",
                            "value": {
                                "enrolled_course_count": 6,
                                "unread_announcement_count": 3,
                                "pending_assignment_count": 4,
                                "overdue_assignment_count": 1,
                                "due_soon_assignments": [
                                    {
                                        "id": "assign_math_ch5",
                                        "course_name": "高等数学",
                                        "title": "第五章习题",
                                        "deadline": "2026-10-08T23:59:00+08:00",
                                    }
                                ],
                                "recent_announcements": [
                                    {
                                        "id": "notice_lib_001",
                                        "course_name": "程序设计基础",
                                        "title": "实验课调整通知",
                                        "published_at": "2026-10-05T09:00:00+08:00",
                                    }
                                ],
                                "pending_personal_task_count": 2,
                                "overdue_personal_task_count": 0,
                                "due_soon_personal_tasks": [
                                    {
                                        "id": "task_practice_001",
                                        "title": "提交暑期实践证明材料",
                                        "deadline": "2026-10-10T23:59:00+08:00",
                                        "priority": "high",
                                        "source_name": "信息工程学院通知",
                                        "course_id": None,
                                    }
                                ],
                            },
                        }
                    }
                }
            },
        },
    },
)
def student_dashboard(
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> StudentDashboard:
    """返回当前登录学生的首页概览数据（课程、公告、作业与个人待办统计）。"""
    now_iso = datetime.now(timezone.utc).isoformat()
    dashboard_repo = container.submission_repository
    personal_task_repo = container.personal_task_repository

    assignments = dashboard_repo.recent_student_assignments(
        user.id, now_iso=now_iso, due_within_days=30, limit=6
    )
    for item in assignments:
        item["id"] = item.get("assignment_id")

    personal_tasks = personal_task_repo.list_recent_pending(user.id, limit=6)
    due_soon_personal_tasks = [
        {
            "id": task.id,
            "title": task.title,
            "deadline": task.deadline,
            "priority": task.priority,
            "source_name": task.source_name,
            "course_id": task.course_id,
        }
        for task in personal_tasks
    ]

    return StudentDashboard(
        enrolled_course_count=dashboard_repo.count_student_enrolled_courses(user.id),
        unread_announcement_count=dashboard_repo.count_student_unread_announcements(user.id),
        pending_assignment_count=dashboard_repo.count_student_pending_assignments(
            user.id, now_iso=now_iso
        ),
        overdue_assignment_count=dashboard_repo.count_student_overdue_assignments(
            user.id, now_iso=now_iso
        ),
        due_soon_assignments=assignments,
        recent_announcements=dashboard_repo.recent_student_announcements(user.id, limit=6),
        pending_personal_task_count=personal_task_repo.count_pending(user.id),
        overdue_personal_task_count=personal_task_repo.count_overdue(user.id, now_iso=now_iso),
        due_soon_personal_tasks=due_soon_personal_tasks,
    )


__all__ = ["router"]

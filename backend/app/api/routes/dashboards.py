"""Role-specific dashboard endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ...models.multi_role import UserRow
from ...schemas.multi_role import StudentDashboard
from ...services.container import ServiceContainer, get_container
from ..deps import require_role


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _container() -> ServiceContainer:
    return get_container()


@router.get("/student", response_model=StudentDashboard)
def student_dashboard(
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> StudentDashboard:
    """Return the authenticated student's home-page summary."""
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

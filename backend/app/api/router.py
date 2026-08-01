"""API 路由聚合。"""
from __future__ import annotations

from fastapi import APIRouter

from .routes import (
    activities,
    admin_dashboard,
    admin_system,
    admin_extra,
    announcements,
    assignments,
    auth,
    classes,
    counselor,
    contributions,
    courses,
    dashboard,
    health,
    knowledge,
    notices,
    personal_tasks,
    study,
    submissions,
    student_tools,
    teacher,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(notices.router, tags=["notices"])
api_router.include_router(knowledge.router, tags=["knowledge"])
api_router.include_router(counselor.router, tags=["counselor"])
api_router.include_router(contributions.router, tags=["contributions"])
# 多角色协同平台
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(activities.router, tags=["activities"])
api_router.include_router(admin_dashboard.router)
api_router.include_router(admin_system.router)
api_router.include_router(admin_extra.router)
api_router.include_router(courses.router, tags=["courses"])
api_router.include_router(classes.router, tags=["classes"])
api_router.include_router(announcements.router, tags=["announcements"])
api_router.include_router(assignments.router, tags=["assignments"])
api_router.include_router(submissions.router, tags=["submissions"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(teacher.router, tags=["teacher"])
# 学习陪伴
api_router.include_router(study.router)
# 个人待办(学生从通知抽取)
api_router.include_router(personal_tasks.router)
api_router.include_router(student_tools.router)

__all__ = ["api_router"]

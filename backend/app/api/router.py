"""API 路由聚合。"""
from __future__ import annotations

from fastapi import APIRouter

from .routes import (
    activities,
    announcements,
    assignments,
    auth,
    classes,
    counselor,
    contributions,
    courses,
    dashboards,
    edu,
    health,
    knowledge,
    notices,
    personal_hub,
    personal_tasks,
    qr_auth,
    study,
    submissions,
    student_tools,
    tts,
    chaoxing,
    course_content,
    universities,
    community,
    academic,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(notices.router, tags=["notices"])
api_router.include_router(knowledge.router, tags=["knowledge"])
# AI 校园助手:保留 /counselor 兼容旧客户端,新增 /assistant 别名
api_router.include_router(counselor.router, tags=["counselor"])
api_router.include_router(counselor.router, prefix="/assistant", tags=["assistant"])
api_router.include_router(tts.router, tags=["assistant-tts"])
api_router.include_router(contributions.router, tags=["contributions"])
# 认证与用户管理
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(activities.router, tags=["activities"])
api_router.include_router(qr_auth.router, tags=["auth-qr"])
api_router.include_router(dashboards.router)

api_router.include_router(courses.router, tags=["courses"])
api_router.include_router(classes.router, tags=["classes"])
api_router.include_router(announcements.router, tags=["announcements"])
api_router.include_router(assignments.router, tags=["assignments"])
api_router.include_router(submissions.router, tags=["submissions"])

# 学习陪伴
api_router.include_router(study.router)
# 个人待办(学生从通知抽取)
api_router.include_router(personal_tasks.router)
# 个人中心(我的文件 / 收藏夹)
api_router.include_router(personal_hub.router)
api_router.include_router(student_tools.router)
api_router.include_router(chaoxing.router, tags=["chaoxing"])
api_router.include_router(course_content.router)
api_router.include_router(universities.router)
api_router.include_router(community.router)
api_router.include_router(community.admin_router)
api_router.include_router(academic.router)
# CampusMate EduConnector — 高校教务系统统一连接层
api_router.include_router(edu.router)

__all__ = ["api_router"]

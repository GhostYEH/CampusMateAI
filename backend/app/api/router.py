"""API 路由聚合。"""
from __future__ import annotations

from fastapi import APIRouter

from .routes import (
    agenda,
    announcements,
    assignments,
    auth,
    classes,
    counselor,
    contributions,
    courses,
    dashboards,
    focus_ai,
    focus_realtime_voice,
    edu,
    health,
    home_banners,
    knowledge,
    notices,
    personal_hub,
    personal_tasks,
    qr_auth,
    study,
    submissions,
    student_tools,
    student_goals,
    tts,
    chaoxing,
    course_content,
    universities,
    community,
    academic,
    bing_daily_wallpaper,
    learner_state,
    forecasts,
    simulations,

    learning_plans,
    adaptive_interventions,
    learner_control,
    agent_runtime,
    agent_observability,
    final_review,
    course_research,
    magicclass_classroom,
    magicclass_archive,
    magicclass_discovery,
    magicclass_editor,
    magicclass_fusion,
    magicclass_materials,
    magicclass_workspaces,
    magicclass_generation,
    magicclass_discussion,
    magicclass_provider,
    magicclass_tts,
    magicclass_narration,
    magicclass_quiz,
    magicclass_course_context,
    magicclass_learning_space,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(home_banners.router)
api_router.include_router(home_banners.admin_router)
api_router.include_router(notices.router, tags=["notices"])
api_router.include_router(knowledge.router, tags=["knowledge"])
# AI 校园助手:保留 /counselor 兼容旧客户端,并由 counselor 路由显式提供 /assistant/chat 别名
api_router.include_router(counselor.router, tags=["counselor"])
api_router.include_router(tts.router, tags=["assistant-tts"])
api_router.include_router(contributions.router, tags=["contributions"])
# 认证与用户管理
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(qr_auth.router, tags=["auth-qr"])
api_router.include_router(dashboards.router)

api_router.include_router(courses.router, tags=["courses"])
api_router.include_router(classes.router, tags=["classes"])
api_router.include_router(announcements.router, tags=["announcements"])
api_router.include_router(assignments.router, tags=["assignments"])
api_router.include_router(submissions.router, tags=["submissions"])

# 学习陪伴
api_router.include_router(study.router)
api_router.include_router(focus_ai.router, tags=["focus-ai"])
api_router.include_router(focus_realtime_voice.router, tags=["focus-realtime-voice"])
# 个人待办(学生从通知抽取)
api_router.include_router(personal_tasks.router)
# 全站统一的"今日待办"事实源(首页/学习陪伴/任务总览/全局角标共用)
api_router.include_router(agenda.router)
# 学生通用目标(个人成长/学业/科研/竞赛/证书/求职等)
api_router.include_router(student_goals.router)
# 个人中心(我的文件 / 收藏夹)
api_router.include_router(personal_hub.router)
api_router.include_router(student_tools.router)
api_router.include_router(chaoxing.router, tags=["chaoxing"])
api_router.include_router(course_content.router)
api_router.include_router(universities.router)
api_router.include_router(community.router)
api_router.include_router(community.admin_router)
api_router.include_router(academic.router)
api_router.include_router(bing_daily_wallpaper.router)
api_router.include_router(learner_state.router)
api_router.include_router(forecasts.router)
api_router.include_router(simulations.router)

api_router.include_router(learning_plans.router)
# 状态驱动干预记录(只读)
api_router.include_router(adaptive_interventions.router)
api_router.include_router(learner_control.router)
# CampusAgentRuntime — Agent 运行时 API(§9.1)
api_router.include_router(agent_runtime.router)
api_router.include_router(agent_runtime.jobs_router)
api_router.include_router(agent_runtime.runs_router)
api_router.include_router(agent_runtime.approvals_router)
api_router.include_router(agent_runtime.artifacts_router)
api_router.include_router(agent_runtime.memories_router)
# 管理员只读观测面(§Task 9):仅 admin,聚合优先、脱敏
api_router.include_router(agent_observability.router)
# notices/manual 端点由 notices.py 提供(canonical:返回 notice_id 供 workflow 创建)。
# CampusAgentRuntime 领域路由(§9.3 期末复习 / §9.5 课程研究)
api_router.include_router(final_review.router)
api_router.include_router(course_research.router)
# notice_workflows(§9.4) 已在 notices.py 末尾 include 注册,此处不重复注册,
# 否则会产生重复的 OpenAPI operationId。
# CampusMate EduConnector — 高校教务系统统一连接层
api_router.include_router(edu.router)
# magic class 互动课堂适配层(学生侧课程智能辅导空间)
api_router.include_router(magicclass_classroom.router)
api_router.include_router(magicclass_fusion.router)
# magic class 学习工作台(受管服务的 workspace/stage 持久化)
api_router.include_router(magicclass_workspaces.router)
# magic class 内容发现(文件夹与站内搜索,同样只经 CampusMate 网关)
api_router.include_router(magicclass_discovery.router)
# magic class 编辑器(Stage/Scene 命令,If-Match + Idempotency-Key)
api_router.include_router(magicclass_editor.router)
# magic class 课程资料(上传即解析,正文只在单份读取时返回)
api_router.include_router(magicclass_materials.router)
# magic class 档案(单份 stage 的 .maic.zip 导出 / 导入)
api_router.include_router(magicclass_archive.router)
# magic class 生成任务与产物下载(排队 + 轮询)
api_router.include_router(magicclass_generation.router)
# magic class 语音合成与多智能体圆桌(入队即返回 202,音频/记录经产物下载)
api_router.include_router(magicclass_tts.router)
# magic class 按场景的讲解音频(按需生成;讲稿由服务端从场景正文派生,浏览器只给 scene id)
api_router.include_router(magicclass_narration.router)
api_router.include_router(magicclass_quiz.router)
api_router.include_router(magicclass_discussion.router)
api_router.include_router(magicclass_provider.router)
# magic class 生成前的只读课程上下文(知识点/章节/资料的真实同步状态)
api_router.include_router(magicclass_course_context.router)
# 导航栏「学习空间」的服务可见性与可信公开 Origin(不绑定课程)
api_router.include_router(magicclass_learning_space.router)

__all__ = ["api_router"]

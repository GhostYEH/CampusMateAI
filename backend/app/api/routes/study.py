"""学习陪伴路由 — 真实后端化的学习会话、休息记录、任务拆解。

API:
- POST   /api/v1/study/sessions                 创建会话
- GET    /api/v1/study/sessions                 列出当前用户会话
- GET    /api/v1/study/sessions/active          获取未结束会话(用于应用重启后恢复)
- GET    /api/v1/study/sessions/{id}            会话详情(含休息记录)
- POST   /api/v1/study/sessions/{id}/pause      暂停(开启一条休息记录)
- POST   /api/v1/study/sessions/{id}/resume     恢复(关闭最近休息记录)
- POST   /api/v1/study/sessions/{id}/finish     结束(填写文字感受,关闭所有未结束休息)
- PATCH  /api/v1/study/sessions/{id}            部分更新(goal/related_task_id/self_report/...)
- POST   /api/v1/study/task-breakdown           任务拆解(LLM + 规则降级 + 知识库)

权限与隔离:
- 所有路由必须登录(current_user)。
- 所有记录绑定当前登录用户,跨用户访问返回 404(StudySessionNotFound)。
- 任务拆解的 task_id 只接受当前用户的个人待办 PersonalTask ID,不接受教师
  Assignment ID(详见 TaskBreakdownService)。

科学边界:
- self_report 仅由用户主动输入,不根据表情自动填写。
- 不进行心理疾病诊断,expression_signal 仅作为预留字段透传存储。
"""
from __future__ import annotations

from datetime import date as date_type, datetime, timedelta, timezone
from typing import Annotated, List, Optional

from fastapi import APIRouter, Body, Depends, Query, Response

from ...core.exceptions import (
    StudySessionNotFound,
    ValidationFailed,
)
from ...core.logging import logger
from ...models.multi_role import UserRow
from ...models.study import StudyBreakRow, StudySessionRow
from ...repositories.study_session_repository import StudySessionRepository
from ...repositories.study_checkin_repository import StudyCheckinRepository
from ...schemas.study import (
    StudyCheckinCreate,
    StudyCheckinOut,
    StudyCheckinResponse,
    StudyCheckinSummary,
    StudyGoalOut,
    StudyGoalUpdate,
    StudyBreakOut,
    StudySessionCreate,
    StudySessionFinish,
    StudySessionOut,
    StudySessionUpdate,
    TaskBreakdownRequest,
    TaskBreakdownResponse,
)
from ...repositories.study_goal_repository import StudyGoalRepository
from ...services.container import ServiceContainer, get_container
from ...services.learner_event_service import LearnerEventService
from ...services.task_breakdown_service import TaskBreakdownService
from ..deps import current_user

router = APIRouter(prefix="/study", tags=["学习陪伴"])


def _container() -> ServiceContainer:
    return get_container()


def _repo(c: ServiceContainer = Depends(_container)) -> StudySessionRepository:
    return c.study_session_repository


def _learner_event_service(
    c: ServiceContainer = Depends(_container),
) -> LearnerEventService:
    return c.learner_event_service


def _goal_repo(c: ServiceContainer = Depends(_container)) -> StudyGoalRepository:
    return c.study_goal_repository


def _checkin_repo(c: ServiceContainer = Depends(_container)) -> StudyCheckinRepository:
    return c.study_checkin_repository


def _breakdown_service(
    c: ServiceContainer = Depends(_container),
) -> TaskBreakdownService:
    return c.task_breakdown_service


# ===== 转换辅助 =====


def _break_to_out(b: StudyBreakRow) -> StudyBreakOut:
    return StudyBreakOut(
        id=b.id,
        session_id=b.session_id,
        started_at=b.started_at,
        ended_at=b.ended_at,
        reason=b.reason,
        created_at=b.created_at,
    )


def _session_to_out(
    s: StudySessionRow,
    *,
    breaks: Optional[List[StudyBreakRow]] = None,
) -> StudySessionOut:
    return StudySessionOut(
        id=s.id,
        user_id=s.user_id,
        mode=s.mode,
        experience_mode=s.experience_mode,
        goal=s.goal,
        related_task_id=s.related_task_id,
        started_at=s.started_at,
        paused_at=s.paused_at,
        ended_at=s.ended_at,
        planned_duration_seconds=s.planned_duration_seconds,
        duration_seconds=s.duration_seconds,
        pause_seconds=s.pause_seconds,
        status=s.status,
        self_report=s.self_report,
        self_report_tags=list(s.self_report_tags or []),
        expression_signal=s.expression_signal,
        behavior_summary=s.behavior_summary,
        created_at=s.created_at,
        updated_at=s.updated_at,
        breaks=[_break_to_out(b) for b in (breaks or [])],
    )


@router.get(
    "/goals/daily",
    response_model=StudyGoalOut,
    summary="读取每日学习目标",
    responses={
        200: {
            "description": "读取成功，返回每日学习目标",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取成功",
                            "value": {
                                "target_minutes": 120,
                                "updated_at": "2026-10-06T09:00:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def get_daily_goal(
    user: UserRow = Depends(current_user),
    repo: StudyGoalRepository = Depends(_goal_repo),
) -> StudyGoalOut:
    """读取当前登录用户的每日学习目标；尚未设置时按默认值创建后返回。"""
    goal = repo.get_or_create(user.id)
    return StudyGoalOut(target_minutes=goal.target_minutes, updated_at=goal.updated_at)


@router.put(
    "/goals/daily",
    response_model=StudyGoalOut,
    summary="更新每日学习目标",
    responses={
        200: {
            "description": "更新成功，返回新的每日学习目标",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "更新成功",
                            "value": {
                                "target_minutes": 120,
                                "updated_at": "2026-10-06T09:00:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def update_daily_goal(
    req: Annotated[
        StudyGoalUpdate,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "设置每日目标 120 分钟",
                    "value": {"target_minutes": 120},
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    repo: StudyGoalRepository = Depends(_goal_repo),
) -> StudyGoalOut:
    """更新每日学习目标分钟数；取值范围 15~480。"""
    goal = repo.set_target(user.id, req.target_minutes)
    return StudyGoalOut(target_minutes=goal.target_minutes, updated_at=goal.updated_at)


def _checkin_to_out(row) -> StudyCheckinOut:
    return StudyCheckinOut(
        id=row.id,
        user_id=row.user_id,
        date=row.date,
        scene=row.scene,
        mood=row.mood,
        created_at=row.created_at,
    )


def _checkin_stats(rows) -> tuple[int, int, int, bool]:
    dates = {date_type.fromisoformat(row.date) for row in rows}
    today = datetime.now(timezone.utc).date()
    today_checked = today in dates
    cursor = today if today_checked else today - timedelta(days=1)
    streak = 0
    while cursor in dates:
        streak += 1
        cursor -= timedelta(days=1)

    longest = 0
    run = 0
    previous = None
    for current in sorted(dates):
        if previous is not None and current == previous + timedelta(days=1):
            run += 1
        else:
            run = 1
        longest = max(longest, run)
        previous = current

    monday = today - timedelta(days=today.weekday())
    week_count = sum(monday <= item <= today for item in dates)
    return streak, longest, week_count, today_checked


@router.post(
    "/checkins",
    response_model=StudyCheckinResponse,
    status_code=201,
    summary="创建今日签到",
    responses={
        201: {
            "description": "本日首次签到成功",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "本日首次签到",
                            "value": {
                                "checkin": {
                                    "id": "checkin_20261006_demo",
                                    "user_id": "u_demo",
                                    "date": "2026-10-06",
                                    "scene": "rain",
                                    "mood": "今天状态不错",
                                    "created_at": "2026-10-06T08:30:00+00:00",
                                },
                                "created": True,
                            },
                        }
                    }
                }
            },
        }
    },
)
def create_checkin(
    req: Annotated[
        StudyCheckinCreate,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "雨天场景签到",
                    "value": {"scene": "rain", "mood": "今天状态不错"},
                }
            }
        ),
    ],
    response: Response,
    user: UserRow = Depends(current_user),
    repo: StudyCheckinRepository = Depends(_checkin_repo),
) -> StudyCheckinResponse:
    """创建今日签到；本日首次签到返回 201，重复签到返回 200（created=false）。"""
    row, created = repo.create_today(user.id, scene=req.scene, mood=req.mood)
    if not created:
        response.status_code = 200
    return StudyCheckinResponse(checkin=_checkin_to_out(row), created=created)


@router.get(
    "/checkins",
    response_model=StudyCheckinSummary,
    summary="列出签到记录",
    responses={
        200: {
            "description": "读取成功，返回签到列表与统计",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取成功",
                            "value": {
                                "items": [
                                    {
                                        "id": "checkin_20261006_demo",
                                        "user_id": "u_demo",
                                        "date": "2026-10-06",
                                        "scene": "rain",
                                        "mood": "今天状态不错",
                                        "created_at": "2026-10-06T08:30:00+00:00",
                                    }
                                ],
                                "total": 1,
                                "streak": 3,
                                "longest_streak": 7,
                                "week_count": 3,
                                "today_checked": True,
                            },
                        }
                    }
                }
            },
        }
    },
)
def list_checkins(
    user: UserRow = Depends(current_user),
    repo: StudyCheckinRepository = Depends(_checkin_repo),
) -> StudyCheckinSummary:
    """列出当前用户全部签到记录，并统计连续签到天数与本周签到次数。"""
    rows = repo.list_checkins(user.id)
    streak, longest, week_count, today_checked = _checkin_stats(rows)
    return StudyCheckinSummary(
        items=[_checkin_to_out(row) for row in rows],
        total=len(rows),
        streak=streak,
        longest_streak=longest,
        week_count=week_count,
        today_checked=today_checked,
    )


# ===== 会话 CRUD =====


@router.post(
    "/sessions",
    response_model=StudySessionOut,
    status_code=201,
    summary="创建学习会话",
    responses={
        201: {
            "description": "创建成功，返回新会话",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "创建专注会话",
                            "value": {
                                "id": "sess_20261006_demo",
                                "user_id": "u_demo",
                                "mode": "focus",
                                "experience_mode": "QUIET",
                                "goal": "完成考研数学第三章习题",
                                "started_at": "2026-10-06T09:00:00+00:00",
                                "ended_at": None,
                                "planned_duration_seconds": 3600,
                                "duration_seconds": 0,
                                "pause_seconds": 0,
                                "status": "active",
                                "self_report": None,
                                "self_report_tags": [],
                                "breaks": [],
                            },
                        }
                    }
                }
            },
        }
    },
)
def create_session(
    req: Annotated[
        StudySessionCreate,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "开始一次专注学习",
                    "value": {
                        "mode": "focus",
                        "experience_mode": "QUIET",
                        "planned_duration_seconds": 3600,
                        "goal": "完成考研数学第三章习题",
                        "related_task_id": "task_20261006_math",
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    repo: StudySessionRepository = Depends(_repo),
) -> StudySessionOut:
    """创建学习会话。开始时间为服务端时间,不接受客户端传入。

    若用户已存在未结束会话(active 或 paused),仍允许新建 — 由前端提示用户。
    """
    # goal 与 related_task_id 都可为空
    if req.goal is not None and not req.goal.strip():
        raise ValidationFailed("goal 不能为空白字符串")
    session = repo.create_session(
        user_id=user.id,
        mode=req.mode,
        experience_mode=req.experience_mode,
        goal=req.goal.strip() if req.goal else None,
        related_task_id=req.related_task_id,
        planned_duration_seconds=req.planned_duration_seconds,
    )
    return _session_to_out(session, breaks=[])


@router.get(
    "/sessions",
    response_model=List[StudySessionOut],
    summary="列出学习会话",
    responses={
        200: {
            "description": "读取成功，返回会话列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取成功",
                            "value": [
                                {
                                    "id": "sess_20261006_demo",
                                    "user_id": "u_demo",
                                    "mode": "focus",
                                    "experience_mode": "QUIET",
                                    "goal": "完成考研数学第三章习题",
                                    "started_at": "2026-10-06T09:00:00+00:00",
                                    "ended_at": None,
                                    "planned_duration_seconds": 3600,
                                    "duration_seconds": 0,
                                    "pause_seconds": 0,
                                    "status": "active",
                                    "self_report": None,
                                    "self_report_tags": [],
                                    "breaks": [],
                                }
                            ],
                        }
                    }
                }
            },
        }
    },
)
def list_sessions(
    status: Optional[str] = Query(
        None, pattern="^(active|paused|completed)$"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserRow = Depends(current_user),
    repo: StudySessionRepository = Depends(_repo),
) -> List[StudySessionOut]:
    """列出当前用户的会话(按开始时间倒序)。"""
    rows, _ = repo.list_sessions(
        user.id, status=status, page=page, page_size=page_size
    )
    return [_session_to_out(r, breaks=[]) for r in rows]


@router.get(
    "/sessions/active",
    response_model=Optional[StudySessionOut],
    summary="获取未结束会话",
    responses={
        200: {
            "description": "读取成功；无未结束会话时返回 null",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "存在未结束会话",
                            "value": {
                                "id": "sess_20261006_demo",
                                "user_id": "u_demo",
                                "mode": "focus",
                                "experience_mode": "QUIET",
                                "goal": "完成考研数学第三章习题",
                                "started_at": "2026-10-06T09:00:00+00:00",
                                "paused_at": "2026-10-06T09:40:00+00:00",
                                "ended_at": None,
                                "planned_duration_seconds": 3600,
                                "duration_seconds": 0,
                                "pause_seconds": 180,
                                "status": "paused",
                                "self_report": None,
                                "self_report_tags": [],
                                "breaks": [
                                    {
                                        "id": "brk_20261006_demo",
                                        "session_id": "sess_20261006_demo",
                                        "started_at": "2026-10-06T09:40:00+00:00",
                                        "ended_at": None,
                                        "reason": "接水休息",
                                        "created_at": "2026-10-06T09:40:00+00:00",
                                    }
                                ],
                            },
                        }
                    }
                }
            },
        }
    },
)
def get_active_session(
    user: UserRow = Depends(current_user),
    repo: StudySessionRepository = Depends(_repo),
) -> Optional[StudySessionOut]:
    """获取当前未结束会话(active 或 paused)。

    应用重启后调用此接口恢复未结束会话。若无则返回 null。
    """
    session = repo.get_active_session(user.id)
    if session is None:
        return None
    breaks = repo.list_breaks(session.id, user_id=user.id)
    return _session_to_out(session, breaks=breaks)


@router.get(
    "/sessions/{session_id}",
    response_model=StudySessionOut,
    summary="获取会话详情",
    responses={
        200: {
            "description": "读取成功，返回会话详情及休息记录",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取成功",
                            "value": {
                                "id": "sess_20261006_demo",
                                "user_id": "u_demo",
                                "mode": "focus",
                                "experience_mode": "QUIET",
                                "goal": "完成考研数学第三章习题",
                                "started_at": "2026-10-06T09:00:00+00:00",
                                "ended_at": None,
                                "planned_duration_seconds": 3600,
                                "duration_seconds": 0,
                                "pause_seconds": 0,
                                "status": "active",
                                "self_report": None,
                                "self_report_tags": [],
                                "breaks": [],
                            },
                        }
                    }
                }
            },
        }
    },
)
def get_session(
    session_id: str,
    user: UserRow = Depends(current_user),
    repo: StudySessionRepository = Depends(_repo),
) -> StudySessionOut:
    """获取会话详情(含休息记录)；会话不存在或不属于当前用户时返回 404（STUDY_SESSION_NOT_FOUND）。"""
    session = repo.get_session(session_id, user_id=user.id)
    if session is None:
        raise StudySessionNotFound()
    breaks = repo.list_breaks(session_id, user_id=user.id)
    return _session_to_out(session, breaks=breaks)


# ===== 状态机动作 =====


@router.post(
    "/sessions/{session_id}/pause",
    response_model=StudySessionOut,
    summary="暂停学习会话",
    responses={
        200: {
            "description": "暂停成功，会话进入 paused 并开启一条休息记录",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "暂停成功",
                            "value": {
                                "id": "sess_20261006_demo",
                                "user_id": "u_demo",
                                "mode": "focus",
                                "experience_mode": "QUIET",
                                "goal": "完成考研数学第三章习题",
                                "started_at": "2026-10-06T09:00:00+00:00",
                                "paused_at": "2026-10-06T09:40:00+00:00",
                                "ended_at": None,
                                "planned_duration_seconds": 3600,
                                "duration_seconds": 0,
                                "pause_seconds": 0,
                                "status": "paused",
                                "self_report": None,
                                "self_report_tags": [],
                                "breaks": [
                                    {
                                        "id": "brk_20261006_demo",
                                        "session_id": "sess_20261006_demo",
                                        "started_at": "2026-10-06T09:40:00+00:00",
                                        "ended_at": None,
                                        "reason": "接水休息",
                                        "created_at": "2026-10-06T09:40:00+00:00",
                                    }
                                ],
                            },
                        }
                    }
                }
            },
        }
    },
)
def pause_session(
    session_id: str,
    user: UserRow = Depends(current_user),
    repo: StudySessionRepository = Depends(_repo),
    reason: Optional[str] = Query(None, max_length=200),
) -> StudySessionOut:
    """暂停会话(开启一条休息记录)。

    Query 参数:
        reason: 休息原因(可选,最长 200 字)。
    """
    session = repo.pause(session_id, user_id=user.id, reason=reason)
    breaks = repo.list_breaks(session_id, user_id=user.id)
    return _session_to_out(session, breaks=breaks)


@router.post(
    "/sessions/{session_id}/resume",
    response_model=StudySessionOut,
    summary="恢复学习会话",
    responses={
        200: {
            "description": "恢复成功，会话回到 active 并累加休息时长",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "恢复成功",
                            "value": {
                                "id": "sess_20261006_demo",
                                "user_id": "u_demo",
                                "mode": "focus",
                                "experience_mode": "QUIET",
                                "goal": "完成考研数学第三章习题",
                                "started_at": "2026-10-06T09:00:00+00:00",
                                "ended_at": None,
                                "planned_duration_seconds": 3600,
                                "duration_seconds": 0,
                                "pause_seconds": 180,
                                "status": "active",
                                "self_report": None,
                                "self_report_tags": [],
                                "breaks": [],
                            },
                        }
                    }
                }
            },
        }
    },
)
def resume_session(
    session_id: str,
    user: UserRow = Depends(current_user),
    repo: StudySessionRepository = Depends(_repo),
) -> StudySessionOut:
    """恢复会话(关闭最近一条休息记录,累加 pause_seconds)。"""
    session = repo.resume(session_id, user_id=user.id)
    breaks = repo.list_breaks(session_id, user_id=user.id)
    return _session_to_out(session, breaks=breaks)


@router.post(
    "/sessions/{session_id}/finish",
    response_model=StudySessionOut,
    summary="结束学习会话",
    responses={
        200: {
            "description": "结束成功，会话进入 completed 并返回统计后的时长",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "结束成功",
                            "value": {
                                "id": "sess_20261006_demo",
                                "user_id": "u_demo",
                                "mode": "focus",
                                "experience_mode": "QUIET",
                                "goal": "完成考研数学第三章习题",
                                "started_at": "2026-10-06T09:00:00+00:00",
                                "ended_at": "2026-10-06T10:00:00+00:00",
                                "planned_duration_seconds": 3600,
                                "duration_seconds": 3420,
                                "pause_seconds": 180,
                                "status": "completed",
                                "self_report": "专注度不错，完成了大部分习题",
                                "self_report_tags": ["专注", "有收获"],
                                "breaks": [],
                            },
                        }
                    }
                }
            },
        }
    },
)
def finish_session(
    session_id: str,
    req: Annotated[
        StudySessionFinish,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "填写结束感受",
                    "value": {
                        "self_report": "专注度不错，完成了大部分习题",
                        "self_report_tags": ["专注", "有收获"],
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    repo: StudySessionRepository = Depends(_repo),
    event_service: LearnerEventService = Depends(_learner_event_service),
) -> StudySessionOut:
    """结束会话。

    self_report 必须由用户主动输入,后端不会根据 expression_signal 替用户填写。
    服务端计算 duration_seconds = (ended_at - started_at) - pause_seconds,
    不接受客户端传入的结束时间。
    """
    if req.self_report is not None and not req.self_report.strip():
        raise ValidationFailed("self_report 不能为空白字符串(若填写需有内容)")
    tags = list(req.self_report_tags) if req.self_report_tags else None
    session = repo.finish(
        session_id,
        user_id=user.id,
        self_report=req.self_report.strip() if req.self_report else None,
        self_report_tags=tags,
        behavior_summary=(
            req.behavior_summary.model_dump(mode="json")
            if req.behavior_summary is not None
            else None
        ),
    )
    event_actions = [("study_session_finished", lambda: event_service.record_study_session_finished(session))]
    if session.self_report is not None:
        event_actions.append(
            (
                "self_report_submitted",
                lambda: event_service.record_self_report_submitted(
                    user_id=user.id,
                    report_id=session.id,
                    report_kind="study_session_reflection",
                    occurred_at=datetime.fromisoformat(session.ended_at.replace("Z", "+00:00")),
                    duration_minutes=max(0, session.duration_seconds // 60),
                ),
            )
        )
    for action, append_event in event_actions:
        try:
            append_event()
        except Exception as exc:
            logger.warning(
                "learner_event_append_failed action={} user_id={} subject_type={} subject_id={} exception_type={}",
                action,
                user.id,
                "study_session",
                session.id,
                type(exc).__name__,
            )
    breaks = repo.list_breaks(session_id, user_id=user.id)
    return _session_to_out(session, breaks=breaks)


@router.patch(
    "/sessions/{session_id}",
    response_model=StudySessionOut,
    summary="部分更新学习会话",
    responses={
        200: {
            "description": "更新成功，返回更新后的会话",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "更新成功",
                            "value": {
                                "id": "sess_20261006_demo",
                                "user_id": "u_demo",
                                "mode": "focus",
                                "experience_mode": "QUIET",
                                "goal": "完成考研数学第三章习题",
                                "started_at": "2026-10-06T09:00:00+00:00",
                                "ended_at": None,
                                "planned_duration_seconds": 3600,
                                "duration_seconds": 0,
                                "pause_seconds": 0,
                                "status": "active",
                                "self_report": "今天效率较高",
                                "self_report_tags": [],
                                "breaks": [],
                            },
                        }
                    }
                }
            },
        }
    },
)
def update_session(
    session_id: str,
    req: Annotated[
        StudySessionUpdate,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "更新目标与感受",
                    "value": {
                        "goal": "完成考研数学第三章习题",
                        "self_report": "今天效率较高",
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    repo: StudySessionRepository = Depends(_repo),
) -> StudySessionOut:
    """部分更新会话。

    - goal / related_task_id: 仅未结束会话可改(repo 层校验)。
    - self_report / self_report_tags / expression_signal: 任意状态可改。
    - 未传字段(None)不更新。
    """
    if req.goal is not None and not req.goal.strip():
        raise ValidationFailed("goal 不能为空白字符串")
    if req.self_report is not None and not req.self_report.strip():
        raise ValidationFailed("self_report 不能为空白字符串")
    session = repo.update_session(
        session_id,
        user_id=user.id,
        goal=req.goal.strip() if req.goal is not None else None,
        related_task_id=req.related_task_id,
        self_report=(
            req.self_report.strip() if req.self_report is not None else None
        ),
        self_report_tags=(
            list(req.self_report_tags)
            if req.self_report_tags is not None
            else None
        ),
        expression_signal=req.expression_signal,
    )
    breaks = repo.list_breaks(session_id, user_id=user.id)
    return _session_to_out(session, breaks=breaks)


# ===== 任务拆解 =====


@router.post(
    "/task-breakdown",
    response_model=TaskBreakdownResponse,
    summary="拆解学习任务",
    responses={
        200: {
            "description": "拆解成功；mode 标注 llm 或 rule_fallback",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "拆解成功（模型生成）",
                            "value": {
                                "mode": "llm",
                                "steps": [
                                    {
                                        "step_number": 1,
                                        "title": "梳理考研数学第三章知识点",
                                        "description": "整理章节公式与典型例题",
                                        "estimated_minutes": 30,
                                        "dependencies": [],
                                        "completion_criteria": "能独立写出本章核心公式",
                                        "is_policy_step": False,
                                        "knowledge_status": "not_applicable",
                                    }
                                ],
                                "goal": "完成考研数学第三章复习",
                                "related_task_id": None,
                                "related_task_title": None,
                                "warnings": [],
                            },
                        }
                    }
                }
            },
        }
    },
)
async def task_breakdown(
    req: Annotated[
        TaskBreakdownRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "按任务与目标拆解",
                    "value": {
                        "task_id": "task_20261006_math",
                        "goal": "完成考研数学第三章复习",
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    service: TaskBreakdownService = Depends(_breakdown_service),
) -> TaskBreakdownResponse:
    """任务拆解。

    输入 task_id(个人待办 PersonalTask ID,必须是当前用户所有且未软删除;
    不接受教师 Assignment ID) 或自由文本 goal,可同时提供。

    输出结构化步骤,mode 标注 llm | rule_fallback。响应的 goal 只返回展示用目标,
    不包含任务说明、通知原文等内部生成上下文。
    """
    return await service.breakdown(req, user=user)


__all__ = ["router"]

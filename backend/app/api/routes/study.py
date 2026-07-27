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
- 任务拆解的 task_id 若为后端 assignment ID,需通过权限校验(详见 TaskBreakdownService)。

科学边界:
- self_report 仅由用户主动输入,不根据表情自动填写。
- 不进行心理疾病诊断,expression_signal 仅作为预留字段透传存储。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from ...core.exceptions import (
    StudySessionNotFound,
    ValidationFailed,
)
from ...models.multi_role import UserRow
from ...models.study import StudyBreakRow, StudySessionRow
from ...repositories.study_session_repository import StudySessionRepository
from ...schemas.study import (
    StudyBreakOut,
    StudySessionCreate,
    StudySessionFinish,
    StudySessionOut,
    StudySessionUpdate,
    TaskBreakdownRequest,
    TaskBreakdownResponse,
)
from ...services.container import ServiceContainer, get_container
from ...services.task_breakdown_service import TaskBreakdownService
from ..deps import current_user

router = APIRouter(prefix="/study", tags=["study"])


def _container() -> ServiceContainer:
    return get_container()


def _repo(c: ServiceContainer = Depends(_container)) -> StudySessionRepository:
    return c.study_session_repository


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
        goal=s.goal,
        related_task_id=s.related_task_id,
        started_at=s.started_at,
        paused_at=s.paused_at,
        ended_at=s.ended_at,
        duration_seconds=s.duration_seconds,
        pause_seconds=s.pause_seconds,
        status=s.status,
        self_report=s.self_report,
        self_report_tags=list(s.self_report_tags or []),
        expression_signal=s.expression_signal,
        created_at=s.created_at,
        updated_at=s.updated_at,
        breaks=[_break_to_out(b) for b in (breaks or [])],
    )


# ===== 会话 CRUD =====


@router.post("/sessions", response_model=StudySessionOut, status_code=201)
def create_session(
    req: StudySessionCreate,
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
        goal=req.goal.strip() if req.goal else None,
        related_task_id=req.related_task_id,
    )
    return _session_to_out(session, breaks=[])


@router.get("/sessions", response_model=List[StudySessionOut])
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


@router.get("/sessions/active", response_model=Optional[StudySessionOut])
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


@router.get("/sessions/{session_id}", response_model=StudySessionOut)
def get_session(
    session_id: str,
    user: UserRow = Depends(current_user),
    repo: StudySessionRepository = Depends(_repo),
) -> StudySessionOut:
    """获取会话详情(含休息记录)。"""
    session = repo.get_session(session_id, user_id=user.id)
    if session is None:
        raise StudySessionNotFound()
    breaks = repo.list_breaks(session_id, user_id=user.id)
    return _session_to_out(session, breaks=breaks)


# ===== 状态机动作 =====


@router.post("/sessions/{session_id}/pause", response_model=StudySessionOut)
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


@router.post("/sessions/{session_id}/resume", response_model=StudySessionOut)
def resume_session(
    session_id: str,
    user: UserRow = Depends(current_user),
    repo: StudySessionRepository = Depends(_repo),
) -> StudySessionOut:
    """恢复会话(关闭最近一条休息记录,累加 pause_seconds)。"""
    session = repo.resume(session_id, user_id=user.id)
    breaks = repo.list_breaks(session_id, user_id=user.id)
    return _session_to_out(session, breaks=breaks)


@router.post("/sessions/{session_id}/finish", response_model=StudySessionOut)
def finish_session(
    session_id: str,
    req: StudySessionFinish,
    user: UserRow = Depends(current_user),
    repo: StudySessionRepository = Depends(_repo),
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
    )
    breaks = repo.list_breaks(session_id, user_id=user.id)
    return _session_to_out(session, breaks=breaks)


@router.patch("/sessions/{session_id}", response_model=StudySessionOut)
def update_session(
    session_id: str,
    req: StudySessionUpdate,
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


@router.post("/task-breakdown", response_model=TaskBreakdownResponse)
def task_breakdown(
    req: TaskBreakdownRequest,
    user: UserRow = Depends(current_user),
    service: TaskBreakdownService = Depends(_breakdown_service),
) -> TaskBreakdownResponse:
    """任务拆解。

    输入 task_id(后端 assignment ID,需权限校验) 或自由文本 goal,可同时提供。
    输出结构化步骤,mode 标注 llm | rule_fallback。
    """
    return service.breakdown(req, user=user)


__all__ = ["router"]

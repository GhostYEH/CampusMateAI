"""学生通用目标路由 — /api/v1/student-goals。

面向通用个人成长目标(学业/科研/竞赛/证书/求职/实习/校园事务/健康习惯/个人成长)。
- 所有接口必须 JWT 认证，目标按 user_id 隔离。
- 创建与进度更新支持幂等键。
- 自由文本目标名称保存在业务表中，不复制到 learner event payload。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ...core.exceptions import StudentGoalConflict, StudentGoalNotFound
from ...models.multi_role import UserRow
from ...schemas.student_goal import (
    StudentGoalCreate,
    StudentGoalCreateResult,
    StudentGoalOut,
    StudentGoalPage,
    StudentGoalProgressCreate,
    StudentGoalProgressOut,
    StudentGoalProgressResult,
    StudentGoalUpdate,
)
from ...services.container import ServiceContainer, get_container
from ...services.learner_event_service import LearnerEventService
from ..deps import current_user

router = APIRouter(prefix="/student-goals", tags=["student-goals"])


def _container() -> ServiceContainer:
    return get_container()


def _learner_event_service(
    c: ServiceContainer = Depends(_container),
) -> LearnerEventService:
    return c.learner_event_service


def _to_out(row) -> StudentGoalOut:
    return StudentGoalOut(
        goal_id=row.goal_id,
        user_id=row.user_id,
        name=row.name if hasattr(row, "name") else "",
        category=row.category,
        status=row.status,
        target_date=row.target_date,
        archived_at=row.archived_at,
        progress_percent=row.progress_percent,
        milestone_count=row.milestone_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("", response_model=StudentGoalCreateResult)
def create_goal(
    payload: StudentGoalCreate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    event_service: LearnerEventService = Depends(_learner_event_service),
) -> StudentGoalCreateResult:
    row, created = container.student_goal_repository.create_goal(
        user_id=user.id,
        name=payload.name,
        category=payload.category,
        target_date=payload.target_date,
        idempotency_key=payload.idempotency_key,
        initial_progress_percent=payload.initial_progress_percent,
        milestone_count=payload.milestone_count,
    )
    if created:
        event_service.record_personal_goal_created(
            user_id=user.id,
            goal_id=row.goal_id,
            category=row.category,
            has_target_date=row.target_date is not None,
            milestone_count=row.milestone_count,
            occurred_at=datetime.now(timezone.utc),
        )
    return StudentGoalCreateResult(goal=_to_out(row), created=created)


@router.get("", response_model=StudentGoalPage)
def list_goals(
    status: Optional[str] = Query(None, pattern="^(active|archived)$"),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> StudentGoalPage:
    rows, total = container.student_goal_repository.list_goals(
        user_id=user.id, status=status, category=category,
        page=page, page_size=page_size,
    )
    return StudentGoalPage(
        items=[_to_out(row) for row in rows],
        total=total, page=page, page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/{goal_id}", response_model=StudentGoalOut)
def get_goal(
    goal_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> StudentGoalOut:
    row = container.student_goal_repository.get_goal(user_id=user.id, goal_id=goal_id)
    if row is None:
        raise StudentGoalNotFound()
    return _to_out(row)


@router.patch("/{goal_id}", response_model=StudentGoalOut)
def update_goal(
    goal_id: str,
    payload: StudentGoalUpdate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    event_service: LearnerEventService = Depends(_learner_event_service),
) -> StudentGoalOut:
    existing = container.student_goal_repository.get_goal(user_id=user.id, goal_id=goal_id)
    if existing is None:
        raise StudentGoalNotFound()
    row = container.student_goal_repository.update_goal(
        user_id=user.id, goal_id=goal_id,
        name=payload.name, category=payload.category,
        target_date=payload.target_date, milestone_count=payload.milestone_count,
    )
    if row is None:
        raise StudentGoalNotFound()
    event_service.record_personal_goal_updated(
        user_id=user.id,
        goal_id=row.goal_id,
        category=row.category,
        has_target_date=row.target_date is not None,
        milestone_count=row.milestone_count,
        occurred_at=datetime.now(timezone.utc),
    )
    return _to_out(row)


@router.post("/{goal_id}/progress", response_model=StudentGoalProgressResult)
def add_progress(
    goal_id: str,
    payload: StudentGoalProgressCreate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    event_service: LearnerEventService = Depends(_learner_event_service),
) -> StudentGoalProgressResult:
    existing = container.student_goal_repository.get_goal(user_id=user.id, goal_id=goal_id)
    if existing is None:
        raise StudentGoalNotFound()
    if existing.status != "active":
        raise StudentGoalConflict()
    now = datetime.now(timezone.utc)
    progress_row, created = container.student_goal_repository.add_progress(
        user_id=user.id, goal_id=goal_id,
        progress_percent=payload.progress_percent,
        milestone_reached=payload.milestone_reached,
        idempotency_key=payload.idempotency_key,
        occurred_at=now.isoformat(),
    )
    updated_goal = container.student_goal_repository.get_goal(user_id=user.id, goal_id=goal_id)
    if updated_goal is None:
        raise StudentGoalNotFound()
    if created:
        event_service.record_goal_progress_reported(
            user_id=user.id,
            goal_id=goal_id,
            progress_percent=payload.progress_percent,
            has_milestone=payload.milestone_reached is not None,
            occurred_at=now,
        )
    return StudentGoalProgressResult(
        goal=_to_out(updated_goal),
        progress=StudentGoalProgressOut(
            progress_id=progress_row.progress_id,
            goal_id=progress_row.goal_id,
            progress_percent=progress_row.progress_percent,
            milestone_reached=progress_row.milestone_reached,
            occurred_at=progress_row.occurred_at,
            created_at=progress_row.created_at,
        ),
        created=created,
    )


@router.post("/{goal_id}/archive", response_model=StudentGoalOut)
def archive_goal(
    goal_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    event_service: LearnerEventService = Depends(_learner_event_service),
) -> StudentGoalOut:
    existing = container.student_goal_repository.get_goal(user_id=user.id, goal_id=goal_id)
    if existing is None:
        raise StudentGoalNotFound()
    if existing.status != "active":
        raise StudentGoalConflict()
    row = container.student_goal_repository.archive_goal(user_id=user.id, goal_id=goal_id)
    if row is None:
        raise StudentGoalNotFound()
    event_service.record_personal_goal_updated(
        user_id=user.id,
        goal_id=row.goal_id,
        category=row.category,
        has_target_date=row.target_date is not None,
        milestone_count=row.milestone_count,
        occurred_at=datetime.now(timezone.utc),
    )
    return _to_out(row)
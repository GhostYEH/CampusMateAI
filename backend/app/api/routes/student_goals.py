"""学生通用目标路由 — /api/v1/student-goals。

面向通用个人成长目标(学业/科研/竞赛/证书/求职/实习/校园事务/健康习惯/个人成长)。
- 所有接口必须 JWT 认证，目标按 user_id 隔离。
- 创建与进度更新支持幂等键。
- 自由文本目标名称保存在业务表中，不复制到 learner event payload。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, Query

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

router = APIRouter(prefix="/student-goals", tags=["学习目标"])


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


@router.post(
    "",
    response_model=StudentGoalCreateResult,
    summary="创建学生目标",
    responses={
        200: {
            "description": "创建目标结果，created 表示是否新建（幂等重放为 false）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "新建一个证书类目标",
                            "value": {
                                "goal": {
                                    "goal_id": "goal_demo_1",
                                    "user_id": "u_demo",
                                    "name": "通过英语六级",
                                    "category": "certificate",
                                    "status": "active",
                                    "target_date": "2026-12-20",
                                    "archived_at": None,
                                    "progress_percent": 0.0,
                                    "milestone_count": 0,
                                    "created_at": "2026-10-06T08:00:00+00:00",
                                    "updated_at": "2026-10-06T08:00:00+00:00",
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
def create_goal(
    payload: Annotated[
        StudentGoalCreate,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "创建一个证书类目标",
                    "value": {
                        "name": "通过英语六级",
                        "category": "certificate",
                        "target_date": "2026-12-20",
                        "idempotency_key": "goal-demo-1",
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    event_service: LearnerEventService = Depends(_learner_event_service),
) -> StudentGoalCreateResult:
    """创建学生的通用个人成长目标。

    - 同一 idempotency_key 重放返回既有目标且 created=false。
    - 名称必填（1–200 字），category 取固定枚举；仅本人可见。
    """
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


@router.get(
    "",
    response_model=StudentGoalPage,
    summary="列出学生目标",
    responses={
        200: {
            "description": "当前学生的目标分页列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "目标列表",
                            "value": {
                                "items": [
                                    {
                                        "goal_id": "goal_demo_1",
                                        "user_id": "u_demo",
                                        "name": "通过英语六级",
                                        "category": "certificate",
                                        "status": "active",
                                        "target_date": "2026-12-20",
                                        "archived_at": None,
                                        "progress_percent": 40.0,
                                        "milestone_count": 3,
                                        "created_at": "2026-10-06T08:00:00+00:00",
                                        "updated_at": "2026-10-06T09:30:00+00:00",
                                    }
                                ],
                                "total": 1,
                                "page": 1,
                                "page_size": 50,
                                "has_more": False,
                            },
                        }
                    }
                }
            },
        }
    },
)
def list_goals(
    status: Optional[str] = Query(None, pattern="^(active|archived)$"),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> StudentGoalPage:
    """按状态与分类列出当前学生的目标。

    - status 可选 active/archived，category 为可选分类过滤。
    - 仅返回本人目标。
    """
    rows, total = container.student_goal_repository.list_goals(
        user_id=user.id, status=status, category=category,
        page=page, page_size=page_size,
    )
    return StudentGoalPage(
        items=[_to_out(row) for row in rows],
        total=total, page=page, page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get(
    "/{goal_id}",
    response_model=StudentGoalOut,
    summary="读取学生目标",
    responses={
        200: {
            "description": "指定目标的详情",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "目标详情",
                            "value": {
                                "goal_id": "goal_demo_1",
                                "user_id": "u_demo",
                                "name": "通过英语六级",
                                "category": "certificate",
                                "status": "active",
                                "target_date": "2026-12-20",
                                "archived_at": None,
                                "progress_percent": 40.0,
                                "milestone_count": 3,
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "updated_at": "2026-10-06T09:30:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def get_goal(
    goal_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> StudentGoalOut:
    """读取指定目标的详情。

    - 目标不存在或不属于当前用户返回 404（STUDENT_GOAL_NOT_FOUND）。
    """
    row = container.student_goal_repository.get_goal(user_id=user.id, goal_id=goal_id)
    if row is None:
        raise StudentGoalNotFound()
    return _to_out(row)


@router.patch(
    "/{goal_id}",
    response_model=StudentGoalOut,
    summary="更新学生目标",
    responses={
        200: {
            "description": "更新后的目标详情",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "更新目标名称与里程碑",
                            "value": {
                                "goal_id": "goal_demo_1",
                                "user_id": "u_demo",
                                "name": "通过英语六级并取得口语证书",
                                "category": "certificate",
                                "status": "active",
                                "target_date": "2026-12-25",
                                "archived_at": None,
                                "progress_percent": 40.0,
                                "milestone_count": 4,
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "updated_at": "2026-10-06T10:00:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def update_goal(
    goal_id: str,
    payload: Annotated[
        StudentGoalUpdate,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "调整目标名称、日期与里程碑",
                    "value": {
                        "name": "通过英语六级并取得口语证书",
                        "target_date": "2026-12-25",
                        "milestone_count": 4,
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    event_service: LearnerEventService = Depends(_learner_event_service),
) -> StudentGoalOut:
    """部分更新目标字段，未提供的字段保持不变。

    - 目标不存在返回 404（STUDENT_GOAL_NOT_FOUND）。
    - 更新成功会记录个人目标更新事件。
    """
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


@router.post(
    "/{goal_id}/progress",
    response_model=StudentGoalProgressResult,
    summary="添加目标进度",
    responses={
        200: {
            "description": "目标进度记录结果，created 表示是否新建（幂等重放为 false）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "上报一次目标进度",
                            "value": {
                                "goal": {
                                    "goal_id": "goal_demo_1",
                                    "user_id": "u_demo",
                                    "name": "通过英语六级",
                                    "category": "certificate",
                                    "status": "active",
                                    "target_date": "2026-12-20",
                                    "archived_at": None,
                                    "progress_percent": 40.0,
                                    "milestone_count": 3,
                                    "created_at": "2026-10-06T08:00:00+00:00",
                                    "updated_at": "2026-10-06T10:00:00+00:00",
                                },
                                "progress": {
                                    "progress_id": "gp_demo_1",
                                    "goal_id": "goal_demo_1",
                                    "progress_percent": 40.0,
                                    "milestone_reached": "完成词汇第一轮",
                                    "occurred_at": "2026-10-06T10:00:00+00:00",
                                    "created_at": "2026-10-06T10:00:00+00:00",
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
def add_progress(
    goal_id: str,
    payload: Annotated[
        StudentGoalProgressCreate,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "上报一次目标进度",
                    "value": {
                        "progress_percent": 40.0,
                        "milestone_reached": "完成词汇第一轮",
                        "idempotency_key": "goal-progress-1",
                    },
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    event_service: LearnerEventService = Depends(_learner_event_service),
) -> StudentGoalProgressResult:
    """为目标上报一次进度。

    - 目标不存在返回 404（STUDENT_GOAL_NOT_FOUND）。
    - 目标非 active 状态返回 409（STUDENT_GOAL_CONFLICT）。
    - 同一 idempotency_key 重放返回既有进度且 created=false。
    """
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


@router.post(
    "/{goal_id}/archive",
    response_model=StudentGoalOut,
    summary="归档学生目标",
    responses={
        200: {
            "description": "归档后的目标详情，status 变为 archived",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "归档目标",
                            "value": {
                                "goal_id": "goal_demo_1",
                                "user_id": "u_demo",
                                "name": "通过英语六级",
                                "category": "certificate",
                                "status": "archived",
                                "target_date": "2026-12-20",
                                "archived_at": "2026-10-06T11:00:00+00:00",
                                "progress_percent": 40.0,
                                "milestone_count": 3,
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "updated_at": "2026-10-06T11:00:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def archive_goal(
    goal_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
    event_service: LearnerEventService = Depends(_learner_event_service),
) -> StudentGoalOut:
    """归档指定的 active 目标。

    - 目标不存在返回 404（STUDENT_GOAL_NOT_FOUND）。
    - 目标非 active 状态返回 409（STUDENT_GOAL_CONFLICT）。
    """
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
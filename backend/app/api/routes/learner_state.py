from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from ...models.learner_state import StateEvidenceRow
from ...models.multi_role import UserRow
from ...schemas.learner_state import (
    STATE_TYPE_PATTERN,
    LearnerStateChangePage,
    LearnerStateEvidenceOut,
    LearnerStateEvidencePage,
    LearnerStateRunOut,
    LearnerStateRunPage,
    LearnerStateSnapshotOut,
    LearnerStateSnapshotPage,
)
from ...services.container import ServiceContainer, get_container
from ..deps import require_role
from ...core.exceptions import NotFoundError

router = APIRouter(prefix="/learner-state", tags=["学习状态"])


def _container() -> ServiceContainer:
    return get_container()


def _snapshot_out(snapshot, *, run=None, evidence_count: int = 0) -> LearnerStateSnapshotOut:
    return LearnerStateSnapshotOut(
        snapshot_id=snapshot.snapshot_id,
        run_id=snapshot.run_id,
        scope_type=snapshot.scope_type,
        scope_id=snapshot.scope_id,
        state_type=snapshot.state_type,
        value=snapshot.value,
        confidence=snapshot.confidence,
        data_quality=snapshot.data_quality,
        observed_from=snapshot.observed_from,
        observed_through=snapshot.observed_through,
        valid_until=snapshot.valid_until,
        computed_at=snapshot.computed_at,
        estimator_version=getattr(run, "estimator_version", "") if run is not None else "",
        projection_kind=getattr(snapshot, "projection_kind", "CORE") or "CORE",
        projection_scope=getattr(snapshot, "projection_scope", "__user__") or "__user__",
        input_digest=getattr(run, "input_digest", "") if run is not None else "",
        as_of=datetime.fromisoformat(run.as_of) if run is not None else None,
        warning_codes=list(
            getattr(run, "warnings", getattr(run, "warning_codes", [])) or []
        ) if run is not None else [],
        evidence_count=evidence_count,
    )


def _project_projection(container: ServiceContainer, *, user_id: str, projection_kind: str, as_of: datetime):
    if projection_kind == "WORLD":
        return container.learner_state_service.project_world(user_id, as_of=as_of, trigger="api_world")
    if projection_kind == "ACADEMIC":
        return container.learner_state_service.project_academic(user_id, as_of=as_of, trigger="api_academic")
    return container.learner_state_service.project_user(user_id, as_of=as_of, trigger="api_read")


def _snapshot_page(container: ServiceContainer, *, user_id: str, items, total: int,
                   page: int, page_size: int) -> LearnerStateSnapshotPage:
    runs = {
        run_id: container.learner_state_repository.get_run(run_id, user_id=user_id)
        for run_id in {item.run_id for item in items}
    }
    return LearnerStateSnapshotPage(
        items=[_snapshot_out(
            item,
            run=runs.get(item.run_id),
            evidence_count=container.learner_state_repository.count_evidence(
                user_id=user_id, snapshot_id=item.snapshot_id
            ),
        ) for item in items],
        total=total, page=page, page_size=page_size,
        has_more=page * page_size < total,
    )


def _evidence_out(row: StateEvidenceRow) -> LearnerStateEvidenceOut:
    return LearnerStateEvidenceOut(
        evidence_kind=row.evidence_kind,
        source_category=row.source_category or "unknown",
        event_id=row.event_id,
        event_type=row.event_type if row.evidence_kind == "EVENT" else None,
        occurred_at=row.occurred_at,
        data_quality=row.data_quality,
        role=row.role,
        explanation_code=row.explanation_code,
    )


@router.get(
    "/runs",
    response_model=LearnerStateRunPage,
    summary="列出状态运行",
    responses={
        200: {
            "description": "状态运行分页列表，查询前会刷新当前投影",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "状态运行列表",
                            "value": {
                                "items": [
                                    {
                                        "run_id": "run_demo_core_1",
                                        "as_of": "2026-10-06T08:00:00+00:00",
                                        "computed_at": "2026-10-06T08:00:01+00:00",
                                        "estimator_version": "core-1.0.0",
                                        "trigger": "api_read",
                                        "is_current": True,
                                        "snapshot_count": 3,
                                        "projection_kind": "CORE",
                                        "projection_scope": "__user__",
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
def list_runs(
    projection_kind: str = Query("CORE", pattern="^(CORE|ACADEMIC|WORLD)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> LearnerStateRunPage:
    """列出当前学生的状态运行历史。

    - projection_kind 选择 CORE/ACADEMIC/WORLD 投影，查询前会刷新当前投影。
    - 仅返回本人数据；未认证或非 student 角色返回 401/403。
    """
    _project_projection(
        container, user_id=user.id, projection_kind=projection_kind,
        as_of=datetime.now(timezone.utc),
    )
    rows, total = container.learner_state_service.list_run_summaries(
        user_id=user.id, page=page, page_size=page_size, projection_kind=projection_kind,
    )
    return LearnerStateRunPage(
        items=[LearnerStateRunOut(
            run_id=row.run_id, as_of=row.as_of, computed_at=row.computed_at,
            estimator_version=row.estimator_version, trigger=row.trigger,
            is_current=row.is_current, warning_codes=row.warnings,
            snapshot_count=row.snapshot_count, projection_kind=row.projection_kind,
            projection_scope=row.projection_scope,
        ) for row in rows],
        total=total, page=page, page_size=page_size,
        has_more=page * page_size < total,
    )


@router.get(
    "/changes",
    response_model=LearnerStateChangePage,
    summary="列出状态变化",
    responses={
        200: {
            "description": "两个状态运行之间的快照变化分页列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "状态变化列表",
                            "value": {
                                "from_run_id": "run_demo_core_0",
                                "to_run_id": "run_demo_core_1",
                                "estimator_changed": False,
                                "changes": [
                                    {
                                        "scope_type": "USER",
                                        "scope_id": "u_demo",
                                        "state_type": "goal_progress",
                                        "change_type": "UPDATED",
                                        "previous_value": {
                                            "active_goal_count": 1,
                                            "archived_goal_count": 0,
                                            "goals_with_milestones": 1,
                                            "average_progress_percent": 20.0,
                                            "data_completeness": "verified",
                                        },
                                        "current_value": {
                                            "active_goal_count": 1,
                                            "archived_goal_count": 0,
                                            "goals_with_milestones": 1,
                                            "average_progress_percent": 35.0,
                                            "data_completeness": "verified",
                                        },
                                        "previous_quality": "verified",
                                        "current_quality": "verified",
                                        "explanation_codes": ["observed_value_changed"],
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
def list_changes(
    from_run_id: str | None = Query(None, min_length=1, max_length=128),
    to_run_id: str | None = Query(None, min_length=1, max_length=128),
    projection_kind: str = Query("CORE", pattern="^(CORE|ACADEMIC|WORLD)$"),
    scope_type: str | None = Query(None, pattern="^(USER|COURSE|TASK|SOURCE|KNOWLEDGE_COMPONENT|SEMESTER)$"),
    state_type: str | None = Query(None, pattern=STATE_TYPE_PATTERN),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    include_unchanged: bool = Query(False),
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> LearnerStateChangePage:
    """比较两个状态运行之间的快照变化。

    - 未传 to_run_id 时使用该 projection_kind 的当前投影；比较双方须为本人同一投影。
    - 运行不存在或跨用户返回 404（NOT_FOUND）。
    """
    if to_run_id is None:
        projected = _project_projection(
            container, user_id=user.id, projection_kind=projection_kind,
            as_of=datetime.now(timezone.utc),
        )
        to_run_id = projected.run_id
    if not to_run_id:
        raise NotFoundError()
    try:
        from_id, to_id, estimator_changed, changes, total = container.learner_state_service.compare_runs(
            user_id=user.id, to_run_id=to_run_id, from_run_id=from_run_id,
            page=page, page_size=page_size, scope_type=scope_type,
            state_type=state_type, include_unchanged=include_unchanged,
        )
    except LookupError as exc:
        raise NotFoundError() from exc
    return LearnerStateChangePage(
        from_run_id=from_id, to_run_id=to_id, estimator_changed=estimator_changed,
        changes=changes, total=total, page=page, page_size=page_size,
        has_more=page * page_size < total,
    )


@router.get(
    "/snapshots",
    response_model=LearnerStateSnapshotPage,
    summary="列出状态快照",
    responses={
        200: {
            "description": "当前学生的状态快照分页列表，查询前会刷新当前投影",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "状态快照列表",
                            "value": {
                                "items": [
                                    {
                                        "snapshot_id": "snap_demo_1",
                                        "run_id": "run_demo_core_1",
                                        "scope_type": "USER",
                                        "scope_id": "u_demo",
                                        "state_type": "goal_progress",
                                        "value": {
                                            "active_goal_count": 1,
                                            "archived_goal_count": 0,
                                            "goals_with_milestones": 1,
                                            "average_progress_percent": 35.0,
                                            "data_completeness": "verified",
                                        },
                                        "confidence": 0.8,
                                        "data_quality": "verified",
                                        "computed_at": "2026-10-06T08:00:01+00:00",
                                        "estimator_version": "core-1.0.0",
                                        "projection_kind": "CORE",
                                        "projection_scope": "__user__",
                                        "evidence_count": 2,
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
def list_snapshots(
    scope_type: str | None = Query(None, pattern="^(USER|COURSE|TASK|SOURCE|KNOWLEDGE_COMPONENT|SEMESTER)$"),
    state_type: str | None = Query(None, pattern=STATE_TYPE_PATTERN),
    course_id: str | None = Query(None, min_length=1, max_length=128),
    projection_kind: str = Query("CORE", pattern="^(CORE|ACADEMIC|WORLD)$"),
    projection_scope: str = Query("__user__", pattern="^__user__$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> LearnerStateSnapshotPage:
    """按 scope/state 类型列出状态快照。

    - projection_kind 选择 CORE/ACADEMIC/WORLD 投影，查询前会刷新当前投影。
    - 仅返回本人数据；未认证或非 student 角色返回 401/403。
    """
    as_of = datetime.now(timezone.utc)
    _project_projection(
        container, user_id=user.id, projection_kind=projection_kind, as_of=as_of
    )
    items, total = container.learner_state_repository.list_snapshots(
        user_id=user.id, page=page, page_size=page_size, scope_type=scope_type,
        state_type=state_type, course_id=course_id,
        projection_kind=projection_kind, projection_scope=projection_scope,
    )
    return _snapshot_page(
        container, user_id=user.id, items=items, total=total,
        page=page, page_size=page_size,
    )


@router.get(
    "/snapshots/{snapshot_id}/evidence",
    response_model=LearnerStateEvidencePage,
    summary="列出快照证据",
    responses={
        200: {
            "description": "支撑指定快照的事件、来源行与同步状态证据分页列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "快照证据列表",
                            "value": {
                                "items": [
                                    {
                                        "evidence_kind": "EVENT",
                                        "source_category": "personal_task",
                                        "event_id": "evt_demo_1",
                                        "event_type": "personal_goal_progress_reported",
                                        "occurred_at": "2026-10-05T12:00:00+00:00",
                                        "data_quality": "verified",
                                        "role": "SUPPORTS",
                                        "explanation_code": "state_observed",
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
def list_snapshot_evidence(
    snapshot_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> LearnerStateEvidencePage:
    """列出支撑指定快照的证据。

    - 快照不存在时先刷新本人投影再重试；仍不存在返回 404（NOT_FOUND）。
    - 逐条给出证据类别、来源分类、发生时间与角色（SUPPORTS/LIMITS/INVALIDATES）。
    """
    family = container.learner_state_repository.get_snapshot_projection_family(
        user_id=user.id, snapshot_id=snapshot_id
    )
    if family is None:
        container.learner_state_service.project_user(
            user.id, as_of=datetime.now(timezone.utc), trigger="api_read"
        )
        family = container.learner_state_repository.get_snapshot_projection_family(
            user_id=user.id, snapshot_id=snapshot_id
        )
    if family is None:
        raise NotFoundError()
    projection_kind, projection_scope = family
    snapshot = container.learner_state_repository.get_snapshot(
        user_id=user.id,
        snapshot_id=snapshot_id,
        projection_kind=projection_kind,
        projection_scope=projection_scope,
    )
    if snapshot is None or not snapshot.run_id:
        raise NotFoundError()
    rows, total = container.learner_state_repository.list_evidence(
        user_id=user.id,
        snapshot_id=snapshot_id,
        page=page,
        page_size=page_size,
        projection_kind=projection_kind,
        projection_scope=projection_scope,
    )
    return LearnerStateEvidencePage(
        items=[_evidence_out(row) for row in rows], total=total,
        page=page, page_size=page_size, has_more=page * page_size < total,
    )


@router.get(
    "/academic",
    response_model=LearnerStateSnapshotPage,
    summary="获取学业投影快照",
    responses={
        200: {
            "description": "ACADEMIC 投影快照分页列表，写入教务事实的安全投影",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "学业投影快照列表",
                            "value": {
                                "items": [
                                    {
                                        "snapshot_id": "snap_demo_academic_1",
                                        "run_id": "run_demo_academic_1",
                                        "scope_type": "USER",
                                        "scope_id": "u_demo",
                                        "state_type": "academic_course_load",
                                        "value": {
                                            "current_semester_course_count": 6,
                                            "effective_credit_load": 18.5,
                                            "data_completeness": "verified",
                                        },
                                        "confidence": 0.85,
                                        "data_quality": "verified",
                                        "computed_at": "2026-10-06T08:00:01+00:00",
                                        "projection_kind": "ACADEMIC",
                                        "projection_scope": "__user__",
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
def get_academic_state(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> LearnerStateSnapshotPage:
    """获取 ACADEMIC 投影快照：教务事实安全投影到学生状态世界模型。"""
    as_of = datetime.now(timezone.utc)
    container.learner_state_service.project_academic(
        user.id, as_of=as_of, trigger="api_academic"
    )
    items, total = container.learner_state_repository.list_snapshots(
        user_id=user.id, page=page, page_size=page_size,
        scope_type=None, state_type=None, course_id=None,
        projection_kind="ACADEMIC", projection_scope="__user__",
    )
    return _snapshot_page(
        container, user_id=user.id, items=items, total=total,
        page=page, page_size=page_size,
    )



__all__ = ["router"]

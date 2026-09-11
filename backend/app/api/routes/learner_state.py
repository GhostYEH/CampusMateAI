from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from ...models.learner_state import StateEvidenceRow
from ...models.multi_role import UserRow
from ...schemas.learner_state import (
    LearnerStateEvidenceOut,
    LearnerStateEvidencePage,
    LearnerStateSnapshotOut,
    LearnerStateSnapshotPage,
)
from ...services.container import ServiceContainer, get_container
from ..deps import require_role
from ...core.exceptions import NotFoundError

router = APIRouter(prefix="/learner-state", tags=["learner-state"])


def _container() -> ServiceContainer:
    return get_container()


def _snapshot_out(snapshot) -> LearnerStateSnapshotOut:
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
    )


def _evidence_out(row: StateEvidenceRow) -> LearnerStateEvidenceOut:
    return LearnerStateEvidenceOut(
        event_id=row.event_id,
        source=row.source,
        event_type=row.event_type,
        occurred_at=row.occurred_at,
        data_quality=row.data_quality,
        role=row.role,
    )


@router.get("/snapshots", response_model=LearnerStateSnapshotPage)
def list_snapshots(
    scope_type: str | None = Query(None, pattern="^(USER|COURSE|TASK|SOURCE)$"),
    state_type: str | None = Query(None, pattern="^(observed_learning_activity|task_workload|deadline_exposure|course_participation|data_source_health)$"),
    course_id: str | None = Query(None, min_length=1, max_length=128),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> LearnerStateSnapshotPage:
    as_of = datetime.now(timezone.utc).replace(microsecond=0)
    result = container.learner_state_service.project_user(
        user.id, as_of=as_of, trigger="api_read"
    )
    filtered = [
        snapshot for snapshot in result.snapshots
        if (scope_type is None or snapshot.scope_type == scope_type)
        and (state_type is None or snapshot.state_type == state_type)
        and (course_id is None or (snapshot.scope_type == "COURSE" and snapshot.scope_id == course_id))
    ]
    offset = (page - 1) * page_size
    items = filtered[offset:offset + page_size]
    return LearnerStateSnapshotPage(
        items=[_snapshot_out(item) for item in items],
        total=len(filtered), page=page, page_size=page_size,
        has_more=offset + len(items) < len(filtered),
    )


@router.get("/snapshots/{snapshot_id}/evidence", response_model=LearnerStateEvidencePage)
def list_snapshot_evidence(
    snapshot_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> LearnerStateEvidencePage:
    existing_snapshot = container.learner_state_repository.get_snapshot(
        user_id=user.id, snapshot_id=snapshot_id
    )
    if existing_snapshot is not None:
        snapshot = existing_snapshot
    else:
        result = container.learner_state_service.project_user(
            user.id, as_of=datetime.now(timezone.utc).replace(microsecond=0), trigger="api_read"
        )
        snapshot = next((item for item in result.snapshots if item.snapshot_id == snapshot_id), None)
    if snapshot is None or not snapshot.run_id:
        raise NotFoundError()
    rows, total = container.learner_state_repository.list_evidence(
        user_id=user.id, snapshot_id=snapshot_id, page=page, page_size=page_size
    )
    return LearnerStateEvidencePage(
        items=[_evidence_out(row) for row in rows], total=total,
        page=page, page_size=page_size, has_more=page * page_size < total,
    )


__all__ = ["router"]

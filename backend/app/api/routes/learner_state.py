from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from ...models.learner_state import StateEvidenceRow
from ...models.multi_role import UserRow
from ...schemas.learner_state import (
    CounterfactualSimulateRequest,
    CounterfactualSimulateResponse,
    LearnerStateChangePage,
    LearnerStateEvidenceOut,
    LearnerStateEvidencePage,
    LearnerStateRunOut,
    LearnerStateRunPage,
    LearnerStateSnapshotOut,
    LearnerStateSnapshotPage,
    PredictionEvaluationResult,
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
        projection_kind=getattr(snapshot, "projection_kind", "CORE") or "CORE",
        projection_scope=getattr(snapshot, "projection_scope", "__user__") or "__user__",
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


@router.get("/runs", response_model=LearnerStateRunPage)
def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> LearnerStateRunPage:
    container.learner_state_service.project_user(
        user.id, as_of=datetime.now(timezone.utc).replace(microsecond=0), trigger="api_runs"
    )
    rows, total = container.learner_state_service.list_run_summaries(
        user_id=user.id, page=page, page_size=page_size
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


@router.get("/changes", response_model=LearnerStateChangePage)
def list_changes(
    from_run_id: str | None = Query(None, min_length=1, max_length=128),
    to_run_id: str | None = Query(None, min_length=1, max_length=128),
    scope_type: str | None = Query(None, pattern="^(USER|COURSE|TASK|SOURCE|KNOWLEDGE_COMPONENT|SEMESTER)$"),
    state_type: str | None = Query(None, pattern="^(observed_learning_activity|task_workload|deadline_exposure|course_participation|data_source_health|knowledge_mastery_estimate|academic_course_load|grade_observation|credit_progress|exam_exposure|schedule_load|goal_state|knowledge_mastery_forecast|performance_prediction|learning_velocity)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    include_unchanged: bool = Query(False),
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> LearnerStateChangePage:
    if to_run_id is None:
        projected = container.learner_state_service.project_user(
            user.id, as_of=datetime.now(timezone.utc).replace(microsecond=0), trigger="api_changes"
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


@router.get("/snapshots", response_model=LearnerStateSnapshotPage)
def list_snapshots(
    scope_type: str | None = Query(None, pattern="^(USER|COURSE|TASK|SOURCE|KNOWLEDGE_COMPONENT|SEMESTER)$"),
    state_type: str | None = Query(None, pattern="^(observed_learning_activity|task_workload|deadline_exposure|course_participation|data_source_health|knowledge_mastery_estimate|academic_course_load|grade_observation|credit_progress|exam_exposure|schedule_load|goal_state|knowledge_mastery_forecast|performance_prediction|learning_velocity)$"),
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
    items, total = container.learner_state_repository.list_snapshots(
        user_id=user.id, page=page, page_size=page_size, scope_type=scope_type,
        state_type=state_type, course_id=course_id,
    )
    return LearnerStateSnapshotPage(
        items=[_snapshot_out(item) for item in items],
        total=total, page=page, page_size=page_size,
        has_more=page * page_size < total,
    )


@router.get("/snapshots/{snapshot_id}/evidence", response_model=LearnerStateEvidencePage)
def list_snapshot_evidence(
    snapshot_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> LearnerStateEvidencePage:
    family = container.learner_state_repository.get_snapshot_projection_family(
        user_id=user.id, snapshot_id=snapshot_id
    )
    if family is None:
        result = container.learner_state_service.project_user(
            user.id, as_of=datetime.now(timezone.utc).replace(microsecond=0), trigger="api_read"
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


@router.get("/academic", response_model=LearnerStateSnapshotPage)
def get_academic_state(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> LearnerStateSnapshotPage:
    """获取 ACADEMIC 投影快照：教务事实安全投影到学生状态世界模型。"""
    as_of = datetime.now(timezone.utc).replace(microsecond=0)
    container.learner_state_service.project_academic(
        user.id, as_of=as_of, trigger="api_academic"
    )
    academic_types = (
        "academic_course_load", "grade_observation", "credit_progress",
        "exam_exposure", "schedule_load", "goal_state",
    )
    items, total = container.learner_state_repository.list_snapshots(
        user_id=user.id, page=page, page_size=page_size,
        scope_type=None, state_type=None, course_id=None,
    )
    academic_items = [item for item in items if item.state_type in academic_types]
    return LearnerStateSnapshotPage(
        items=[_snapshot_out(item) for item in academic_items],
        total=len(academic_items), page=page, page_size=page_size,
        has_more=False,
    )


@router.get("/predictions/{course_id}", response_model=LearnerStateSnapshotPage)
def get_prediction_state(
    course_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> LearnerStateSnapshotPage:
    """获取 PREDICTION 投影快照：基于学习证据的确定性预测。"""
    as_of = datetime.now(timezone.utc).replace(microsecond=0)
    container.learner_state_service.project_prediction(
        user.id, course_id=course_id, as_of=as_of, trigger="api_prediction"
    )
    prediction_types = (
        "knowledge_mastery_forecast",
        "performance_prediction",
        "learning_velocity",
    )
    items, total = container.learner_state_repository.list_snapshots(
        user_id=user.id, page=page, page_size=page_size,
        scope_type=None, state_type=None, course_id=None,
    )
    prediction_items = [item for item in items if item.state_type in prediction_types]
    return LearnerStateSnapshotPage(
        items=[_snapshot_out(item) for item in prediction_items],
        total=len(prediction_items), page=page, page_size=page_size,
        has_more=False,
    )


@router.post("/simulate", response_model=CounterfactualSimulateResponse)
def simulate_counterfactual(
    request: CounterfactualSimulateRequest,
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> CounterfactualSimulateResponse:
    """安全反事实模拟：假设干预后的预测变化，不修改实际状态。"""
    as_of = datetime.now(timezone.utc).replace(microsecond=0)
    result = container.learner_state_service.simulate_counterfactual(
        user.id,
        course_id=request.course_id,
        as_of=as_of,
        intervention=request.intervention.model_dump(),
    )
    return CounterfactualSimulateResponse(
        course_id=result["course_id"],
        intervention=CounterfactualSimulateRequest.__fields__["intervention"].type_(
            **result["intervention"],
        ),
        deltas=result["deltas"],
        baseline_snapshot_count=result["baseline_snapshot_count"],
        counterfactual_snapshot_count=result["counterfactual_snapshot_count"],
        warning_codes=result["warning_codes"],
        explanation_codes=result["explanation_codes"],
    )


@router.get("/predictions/{course_id}/evaluation", response_model=PredictionEvaluationResult)
def evaluate_prediction_quality(
    course_id: str,
    test_ratio: float = Query(0.3, ge=0.1, le=0.5),
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> PredictionEvaluationResult:
    """时序评测：chronological split 度量预测质量，真实性门禁检查。"""
    as_of = datetime.now(timezone.utc).replace(microsecond=0)
    result = container.learner_state_service.evaluate_predictions(
        user.id, course_id=course_id, as_of=as_of, test_ratio=test_ratio,
    )
    return PredictionEvaluationResult(**result)


__all__ = ["router"]

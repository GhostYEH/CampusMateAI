from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from ...core.exceptions import Forbidden
from ...models.multi_role import UserRow
from ...schemas.c_knowledge import (
    HypothesisDecision, KnowledgeComponentOut, KnowledgeStateOut,
    MisconceptionHypothesisOut, PracticeAttemptCreate, PracticeAttemptOut,
)
from ...services.container import ServiceContainer, get_container
from ..deps import require_role


router = APIRouter(tags=["learner-knowledge"])


def _container() -> ServiceContainer:
    return get_container()


def _assert_course(container: ServiceContainer, user: UserRow, course_id: str) -> None:
    if not container.knowledge_repository.user_can_access_course(user_id=user.id, course_id=course_id):
        raise Forbidden("无权访问该课程")


def _component_out(row) -> KnowledgeComponentOut:
    return KnowledgeComponentOut(
        knowledge_component_id=row.knowledge_component_id, code=row.code, name=row.name,
        category=row.category, description=row.description, domain=row.domain,
        taxonomy_version=row.taxonomy_version, sort_order=row.sort_order, active=row.active,
        parent_code=row.parent_code, prerequisite_codes=row.prerequisite_codes,
    )


def _hypothesis_out(row) -> MisconceptionHypothesisOut:
    return MisconceptionHypothesisOut(
        hypothesis_id=row.hypothesis_id, course_id=row.course_id,
        knowledge_component_code=row.knowledge_component_code, misconception_code=row.misconception_code,
        confidence=row.confidence, supporting_attempt_count=row.supporting_attempt_count,
        supporting_error_count=row.supporting_error_count,
        supporting_evidence_count=row.supporting_evidence_count, status=row.status,
        generated_at=datetime.fromisoformat(row.generated_at), valid_until=datetime.fromisoformat(row.valid_until),
        estimator_version=row.estimator_version,
        decided_at=datetime.fromisoformat(row.decided_at) if row.decided_at else None,
    )


@router.get("/learner-state/taxonomy", response_model=list[KnowledgeComponentOut])
def list_taxonomy(user: UserRow = Depends(require_role("student")), container: ServiceContainer = Depends(_container)):
    return [_component_out(row) for row in container.knowledge_service.seed_c_taxonomy()]


@router.post("/practice/attempts", response_model=PracticeAttemptOut)
def record_attempt(
    attempt: PracticeAttemptCreate,
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> PracticeAttemptOut:
    return container.knowledge_service.record_practice_attempt(user_id=user.id, attempt=attempt)


@router.get("/learner-state/knowledge", response_model=list[KnowledgeStateOut])
def list_knowledge_states(
    course_id: str = Query(..., min_length=1, max_length=128),
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> list[KnowledgeStateOut]:
    _assert_course(container, user, course_id)
    result = container.knowledge_service.project_knowledge(
        user_id=user.id, course_id=course_id,
        as_of=datetime.now(timezone.utc).replace(microsecond=0), trigger="api_knowledge_read",
    )
    components = {row.code: row for row in container.knowledge_service.seed_c_taxonomy()}
    return [KnowledgeStateOut(
        snapshot_id=row.snapshot_id, run_id=row.run_id, course_id=course_id,
        knowledge_component=_component_out(components[row.scope_id]), value=row.value,
        confidence=row.confidence, data_quality=row.data_quality,
        observed_from=datetime.fromisoformat(row.observed_from) if row.observed_from else None,
        observed_through=datetime.fromisoformat(row.observed_through) if row.observed_through else None,
        valid_until=datetime.fromisoformat(row.valid_until) if row.valid_until else None,
        computed_at=datetime.fromisoformat(row.computed_at),
    ) for row in result.snapshots]


@router.get("/learner-state/hypotheses", response_model=list[MisconceptionHypothesisOut])
def list_hypotheses(
    course_id: str = Query(..., min_length=1, max_length=128),
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> list[MisconceptionHypothesisOut]:
    _assert_course(container, user, course_id)
    container.knowledge_service.project_knowledge(
        user_id=user.id, course_id=course_id,
        as_of=datetime.now(timezone.utc).replace(microsecond=0), trigger="api_hypotheses_read",
    )
    return [_hypothesis_out(row) for row in container.knowledge_service.list_hypotheses(user_id=user.id, course_id=course_id)]


@router.post("/learner-state/hypotheses/{hypothesis_id}/decision", response_model=MisconceptionHypothesisOut)
def decide_hypothesis(
    hypothesis_id: str,
    decision: HypothesisDecision,
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> MisconceptionHypothesisOut:
    return _hypothesis_out(container.knowledge_service.decide_hypothesis(
        user_id=user.id, hypothesis_id=hypothesis_id, decision=decision.decision,
    ))


__all__ = ["router"]

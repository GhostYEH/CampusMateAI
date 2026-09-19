from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query

from ...core.exceptions import InvalidTransition, ValidationFailed
from ...core.logging import logger
from ...models.learning_plan import LearningPlanRow
from ...models.multi_role import UserRow
from ...schemas.learning_plan import (
    LearningPlanDecisionRequest,
    LearningPlanEvaluationOut,
    LearningPlanSummaryOut,
    LearningPlanEvidenceOut,
    LearningPlanFeedbackOut,
    LearningPlanFeedbackRequest,
    LearningPlanGenerateRequest,
    LearningPlanItemOut,
    LearningPlanOut,
    LearningPlanPage,
)
from ...services.container import ServiceContainer, get_container
from ..deps import student_only

router = APIRouter(prefix="/learning-plans", tags=["learning-plans"])


def _container() -> ServiceContainer:
    return get_container()


def _out(plan: LearningPlanRow) -> LearningPlanOut:
    return LearningPlanOut(
        plan_id=plan.plan_id, goal_id=plan.run.goal_id, planner_version=plan.run.planner_version, input_digest=plan.run.input_digest,
        status=plan.status, as_of=plan.run.as_of, valid_until=plan.run.valid_until,
        available_minutes=plan.run.available_minutes, allocated_minutes=plan.run.allocated_minutes,
        warning_codes=plan.run.warning_codes, created_at=plan.created_at,
        llm_summary=plan.llm_summary,
        supersedes_plan_id=plan.supersedes_plan_id,
        superseded_by_plan_id=plan.superseded_by_plan_id,
        items=[LearningPlanItemOut(
            item_id=item.item_id, item_type=item.item_type, course_id=item.course_id, task_id=item.task_id,
            estimated_minutes=item.estimated_minutes,
            priority_score=item.priority_score, priority_components=item.priority_components,
            explanation_codes=item.explanation_codes,
            evidence=[LearningPlanEvidenceOut(
                evidence_type=e["evidence_type"], relation=str(e.get("metadata", {}).get("relation", "SUPPORTS")),
                relevance_score=e.get("relevance_score"),
            ) for e in item.evidence], execution_status=item.execution_status,
        ) for item in plan.items],
    )


@router.post("/generate", response_model=LearningPlanOut)
async def generate_learning_plan(
    req: LearningPlanGenerateRequest,
    idempotency_header: str | None = Header(None, alias="Idempotency-Key", max_length=128),
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanOut:
    try:
        plan = container.learning_planner_service.generate(
            user_id=user.id, available_minutes=req.available_minutes, course_id=req.course_id, goal_id=req.goal_id,
            window_start=req.window_start, window_end=req.window_end,
            idempotency_key=idempotency_header or req.idempotency_key,
        )
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc
    if req.enhance_with_llm:
        plan = await container.learning_planner_service.enhance_with_llm(plan)
    return _out(plan)


@router.get("", response_model=LearningPlanPage)
def list_learning_plans(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanPage:
    rows, total = container.learning_plan_repository.list_plans(user_id=user.id, page=page, page_size=page_size)
    return LearningPlanPage(items=[_out(row) for row in rows], total=total, page=page, page_size=page_size,
                             has_more=page * page_size < total)


@router.get("/{plan_id}", response_model=LearningPlanOut)
def get_learning_plan(
    plan_id: str, user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanOut:
    plan = container.learning_plan_repository.get_plan(plan_id, user_id=user.id)
    if plan is None:
        from ...core.exceptions import NotFoundError
        raise NotFoundError()
    return _out(plan)


@router.post("/{plan_id}/decision", response_model=LearningPlanOut)
def decide_learning_plan(
    plan_id: str, req: LearningPlanDecisionRequest,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanOut:
    return _out(container.learning_planner_service.decide(user_id=user.id, plan_id=plan_id, decision=req.decision))


@router.post("/{plan_id}/execute", response_model=LearningPlanOut)
def execute_learning_plan(
    plan_id: str, user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanOut:
    return _out(container.learning_planner_service.execute(user_id=user.id, plan_id=plan_id))


@router.post("/{plan_id}/undo", response_model=LearningPlanOut)
def undo_learning_plan(
    plan_id: str, user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanOut:
    return _out(container.learning_planner_service.undo(user_id=user.id, plan_id=plan_id))


@router.post("/{plan_id}/replan", response_model=LearningPlanOut)
def replan_learning_plan(
    plan_id: str,
    idempotency_header: str | None = Header(None, alias="Idempotency-Key", max_length=128),
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanOut:
    return _out(container.learning_planner_service.replan(user_id=user.id, plan_id=plan_id,
                                                           idempotency_key=idempotency_header))


@router.post("/{plan_id}/feedback", response_model=LearningPlanFeedbackOut)
def feedback_learning_plan(
    plan_id: str, req: LearningPlanFeedbackRequest,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanFeedbackOut:
    feedback_id = container.learning_planner_service.record_feedback(
        user_id=user.id, plan_id=plan_id, feedback=req.feedback
    )
    plan = container.learning_plan_repository.get_plan(plan_id, user_id=user.id)
    try:
        container.learner_event_service.record_ai_learning_feedback_recorded(
            user_id=user.id,
            feedback_id=feedback_id,
            feedback_kind=req.feedback,
            course_id=plan.run.course_scope if plan is not None else None,
            occurred_at=datetime.now(timezone.utc),
        )
    except Exception as exc:
        logger.warning(
            "learner_event_append_failed action={} user_id={} subject_type={} subject_id={} exception_type={}",
            "ai_learning_feedback_recorded",
            user.id,
            "learning_plan_feedback",
            feedback_id,
            type(exc).__name__,
        )
    try:
        intervention = container.adaptive_intervention_repository.find_by_plan(user_id=user.id, plan_id=plan_id)
        if intervention is not None:
            container.learner_event_service.record_intervention_event(
                user_id=user.id, event_type="intervention_feedback_received",
                intervention_id=intervention.intervention_id, goal_id=intervention.goal_id,
                evaluation_id=intervention.evaluation_id, occurred_at=datetime.now(timezone.utc),
                evidence_refs=[feedback_id], outcome="reported",
            )
    except Exception:
        logger.warning("adaptive_feedback_event_failed user_id={} plan_id={}", user.id, plan_id)
    return LearningPlanFeedbackOut(plan_id=plan_id, feedback=req.feedback)


@router.get("/{plan_id}/evaluation", response_model=LearningPlanEvaluationOut)
def evaluate_learning_plan(
    plan_id: str,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanEvaluationOut:
    return LearningPlanEvaluationOut(**container.learning_planner_service.evaluate(user_id=user.id, plan_id=plan_id))


@router.get("/{plan_id}/summary", response_model=LearningPlanSummaryOut)
def summarize_learning_plan(
    plan_id: str,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanSummaryOut:
    return LearningPlanSummaryOut(**container.learning_planner_service.summarize(user_id=user.id, plan_id=plan_id))


__all__ = ["router"]

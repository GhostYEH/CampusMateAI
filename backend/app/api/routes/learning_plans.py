from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query

from ...core.exceptions import InvalidTransition, ValidationFailed
from ...core.logging import logger
from ...models.learning_plan import LearningPlanRow
from ...models.multi_role import UserRow
from ...schemas.learning_plan import (
    CandidateAnnotationOut,
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


def _adopt_plan_into_intervention(container: ServiceContainer, *, user_id: str, plan_id: str) -> None:
    """学生**采纳**计划后，把这份计划纳入可观测闭环。

    触发点是"用户确认/执行"，而不是"计划被生成"：`/generate` 只产出草案，
    未被采纳的计划永远不会创建干预，也就永远不会被后台自动重规划。
    对 Agent `learning_goal` 路径生成的计划，干预已由 Handler 建好并绑定，
    `adopt_plan` 会按 `find_by_plan` 复用，不会产生第二条记录。

    闭环是增强项而非前置条件：任何失败都只记警告，确认/执行计划本身必须成功。
    """
    try:
        container.adaptive_intervention_service.adopt_plan(user_id=user_id, plan_id=plan_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "adaptive_plan_adoption_failed user_id={} plan_id={} exception_type={}",
            user_id, plan_id, type(exc).__name__,
        )


@router.post("/{plan_id}/decision", response_model=LearningPlanOut)
def decide_learning_plan(
    plan_id: str, req: LearningPlanDecisionRequest,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanOut:
    plan = container.learning_planner_service.decide(user_id=user.id, plan_id=plan_id, decision=req.decision)
    if req.decision == "ACCEPT":
        _adopt_plan_into_intervention(container, user_id=user.id, plan_id=plan_id)
    return _out(plan)


@router.post("/{plan_id}/execute", response_model=LearningPlanOut)
def execute_learning_plan(
    plan_id: str, user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanOut:
    plan = container.learning_planner_service.execute(user_id=user.id, plan_id=plan_id)
    # 幂等兜底：在"确认"特性上线前已接受的计划，会在第一次执行时补上干预记录。
    _adopt_plan_into_intervention(container, user_id=user.id, plan_id=plan_id)
    return _out(plan)


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
async def summarize_learning_plan(
    plan_id: str,
    background_tasks: BackgroundTasks,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanSummaryOut:
    """阶段总结 + 候选模型只读金丝雀注解。

    这是候选模型在生产链路上的**唯一业务接线点**：

    - 门禁全过时，`candidate_annotation` 携带可识别、可降级、可追溯的只读结果；
    - 其余任何情形（未启用/未配置/采样未命中/熔断/超时/非法输出/策略违规），
      注解降级为 `available=false` + 稳定 reason，并改走纯影子观测
      （`BackgroundTasks`，结果只落影子表），本响应继续返回确定性结果。
    """
    data = container.learning_planner_service.summarize(user_id=user.id, plan_id=plan_id)
    plan = container.learning_plan_repository.get_plan(plan_id, user_id=user.id)
    annotation: CandidateAnnotationOut | None = None
    if plan is not None:
        raw = await container.model_assist_service.candidate_annotation(
            user_id=user.id, plan=plan, summary=data
        )
        annotation = CandidateAnnotationOut(**raw)
        if not annotation.available:
            background_tasks.add_task(
                container.model_assist_service.observe_plan_summary,
                user_id=user.id, plan=plan, summary=data,
            )
    return LearningPlanSummaryOut(**data, candidate_annotation=annotation)


__all__ = ["router"]

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Header, Query
from starlette.concurrency import run_in_threadpool

from ...core.exceptions import ValidationFailed
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

router = APIRouter(prefix="/learning-plans", tags=["学习计划"])


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
            execution_task_id=item.execution_task_id,
            estimated_minutes=item.estimated_minutes,
            priority_score=item.priority_score, priority_components=item.priority_components,
            explanation_codes=item.explanation_codes,
            evidence=[LearningPlanEvidenceOut(
                evidence_type=e["evidence_type"], relation=str(e.get("metadata", {}).get("relation", "SUPPORTS")),
                relevance_score=e.get("relevance_score"),
            ) for e in item.evidence], execution_status=item.execution_status,
        ) for item in plan.items],
    )


@router.post(
    "/generate",
    response_model=LearningPlanOut,
    summary="生成学习计划",
    responses={
        200: {
            "description": "生成成功，返回草案计划（含条目、证据与执行待办关联）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "生成学习计划草案",
                            "value": {
                                "plan_id": "plan_2026w40_001",
                                "goal_id": "goal_math_2025",
                                "planner_version": "planner-v3",
                                "input_digest": "sha256:9f2c1a7b",
                                "status": "PROPOSED",
                                "as_of": "2026-10-06T08:00:00+00:00",
                                "valid_until": "2026-10-07T08:00:00+00:00",
                                "available_minutes": 120,
                                "allocated_minutes": 95,
                                "warning_codes": ["WINDOW_TRUNCATED"],
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "llm_summary": None,
                                "supersedes_plan_id": None,
                                "superseded_by_plan_id": None,
                                "items": [
                                    {
                                        "item_id": "item_001",
                                        "item_type": "TASK_FOCUS",
                                        "course_id": "course_db_2025",
                                        "task_id": "task_hw3",
                                        "execution_task_id": None,
                                        "estimated_minutes": 45,
                                        "priority_score": 82.5,
                                        "priority_components": {"deadline": 40.0, "mastery": 42.5},
                                        "explanation_codes": ["DEADLINE_URGENT"],
                                        "evidence": [
                                            {
                                                "evidence_type": "task_deadline",
                                                "relation": "SUPPORTS",
                                                "relevance_score": 0.9,
                                            }
                                        ],
                                        "execution_status": "PENDING",
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
async def generate_learning_plan(
    req: Annotated[
        LearningPlanGenerateRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "生成学习计划",
                    "value": {
                        "available_minutes": 120,
                        "course_id": "course_db_2025",
                        "goal_id": "goal_math_2025",
                        "window_start": "2026-10-06T08:00:00+00:00",
                        "window_end": "2026-10-06T22:00:00+00:00",
                        "enhance_with_llm": True,
                    },
                }
            }
        ),
    ],
    idempotency_header: str | None = Header(None, alias="Idempotency-Key", max_length=128),
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanOut:
    """生成一份学习计划草案。

    - 依据可用分钟数、目标、课程与时间窗，结合待办与证据排序产出条目。
    - 输入不合法（如窗口缺失、时间窗越界）返回 422（VALIDATION_FAILED）；同用户同幂等键并发生成同一份计划。
    """
    try:
        plan = await run_in_threadpool(container.learning_planner_service.generate,
            user_id=user.id, available_minutes=req.available_minutes, course_id=req.course_id, goal_id=req.goal_id,
            window_start=req.window_start, window_end=req.window_end,
            idempotency_key=idempotency_header or req.idempotency_key,
        )
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc
    if req.enhance_with_llm:
        plan = await container.learning_planner_service.enhance_with_llm(plan)
    return _out(plan)


@router.get(
    "",
    response_model=LearningPlanPage,
    summary="列出学习计划",
    responses={
        200: {
            "description": "返回当前用户的学习计划分页列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "分页列出学习计划",
                            "value": {
                                "items": [
                                    {
                                        "plan_id": "plan_2026w40_001",
                                        "goal_id": "goal_math_2025",
                                        "planner_version": "planner-v3",
                                        "input_digest": "sha256:9f2c1a7b",
                                        "status": "PROPOSED",
                                        "as_of": "2026-10-06T08:00:00+00:00",
                                        "valid_until": "2026-10-07T08:00:00+00:00",
                                        "available_minutes": 120,
                                        "allocated_minutes": 95,
                                        "warning_codes": [],
                                        "created_at": "2026-10-06T08:00:00+00:00",
                                        "items": [],
                                        "llm_summary": None,
                                        "supersedes_plan_id": None,
                                        "superseded_by_plan_id": None,
                                    }
                                ],
                                "total": 1,
                                "page": 1,
                                "page_size": 20,
                                "has_more": False,
                            },
                        }
                    }
                }
            },
        }
    },
)
def list_learning_plans(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanPage:
    """列出当前用户的学习计划，按页返回。

    - page 从 1 开始，page_size 取值 1–100；has_more 表示是否还有下一页。
    """
    rows, total = container.learning_plan_repository.list_plans(user_id=user.id, page=page, page_size=page_size)
    return LearningPlanPage(items=[_out(row) for row in rows], total=total, page=page, page_size=page_size,
                             has_more=page * page_size < total)


@router.get(
    "/{plan_id}",
    response_model=LearningPlanOut,
    summary="读取学习计划",
    responses={
        200: {
            "description": "返回指定学习计划的完整内容",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取学习计划详情",
                            "value": {
                                "plan_id": "plan_2026w40_001",
                                "goal_id": "goal_math_2025",
                                "planner_version": "planner-v3",
                                "input_digest": "sha256:9f2c1a7b",
                                "status": "PROPOSED",
                                "as_of": "2026-10-06T08:00:00+00:00",
                                "valid_until": "2026-10-07T08:00:00+00:00",
                                "available_minutes": 120,
                                "allocated_minutes": 95,
                                "warning_codes": [],
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "items": [
                                    {
                                        "item_id": "item_001",
                                        "item_type": "TASK_FOCUS",
                                        "course_id": "course_db_2025",
                                        "task_id": "task_hw3",
                                        "execution_task_id": "todo_7788",
                                        "estimated_minutes": 45,
                                        "priority_score": 82.5,
                                        "priority_components": {"deadline": 40.0, "mastery": 42.5},
                                        "explanation_codes": ["DEADLINE_URGENT"],
                                        "evidence": [
                                            {
                                                "evidence_type": "task_deadline",
                                                "relation": "SUPPORTS",
                                                "relevance_score": 0.9,
                                            }
                                        ],
                                        "execution_status": "EXECUTED",
                                    }
                                ],
                                "llm_summary": None,
                                "supersedes_plan_id": None,
                                "superseded_by_plan_id": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
def get_learning_plan(
    plan_id: str, user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanOut:
    """读取指定学习计划的完整内容。

    - 计划不存在或不属于当前用户时返回 404（NOT_FOUND）。
    """
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


@router.post(
    "/{plan_id}/decision",
    response_model=LearningPlanOut,
    summary="决定学习计划",
    responses={
        200: {
            "description": "决定已记录，返回更新后的计划（ACCEPT 后进入可执行状态）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "采纳学习计划",
                            "value": {
                                "plan_id": "plan_2026w40_001",
                                "goal_id": "goal_math_2025",
                                "planner_version": "planner-v3",
                                "input_digest": "sha256:9f2c1a7b",
                                "status": "ACCEPTED",
                                "as_of": "2026-10-06T08:00:00+00:00",
                                "valid_until": "2026-10-07T08:00:00+00:00",
                                "available_minutes": 120,
                                "allocated_minutes": 95,
                                "warning_codes": [],
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "items": [],
                                "llm_summary": None,
                                "supersedes_plan_id": None,
                                "superseded_by_plan_id": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
def decide_learning_plan(
    plan_id: str,
    req: Annotated[
        LearningPlanDecisionRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "采纳计划",
                    "value": {"decision": "ACCEPT"},
                }
            }
        ),
    ],
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanOut:
    """记录学生对计划的决定（ACCEPT 采纳 / REJECT 拒绝）。

    - ACCEPT 会把计划纳入自适应干预闭环；decision 必须严格匹配枚举大小写。
    - 计划不存在或不属于当前用户返回 404；非法 decision 返回 422。
    """
    plan = container.learning_planner_service.decide(user_id=user.id, plan_id=plan_id, decision=req.decision)
    if req.decision == "ACCEPT":
        _adopt_plan_into_intervention(container, user_id=user.id, plan_id=plan_id)
    return _out(plan)


@router.post(
    "/{plan_id}/execute",
    response_model=LearningPlanOut,
    summary="执行学习计划",
    responses={
        200: {
            "description": "执行成功，返回完整计划；创建待办的条目通过 items[].execution_task_id 返回新待办 ID",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "执行计划并创建待办",
                            "value": {
                                "plan_id": "plan_2026w40_001",
                                "goal_id": "goal_math_2025",
                                "planner_version": "planner-v3",
                                "input_digest": "sha256:9f2c1a7b",
                                "status": "EXECUTED",
                                "as_of": "2026-10-06T08:00:00+00:00",
                                "valid_until": "2026-10-07T08:00:00+00:00",
                                "available_minutes": 120,
                                "allocated_minutes": 95,
                                "warning_codes": [],
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "items": [
                                    {
                                        "item_id": "item_001",
                                        "item_type": "TASK_FOCUS",
                                        "course_id": "course_db_2025",
                                        "task_id": "task_hw3",
                                        "execution_task_id": "todo_7788",
                                        "estimated_minutes": 45,
                                        "priority_score": 82.5,
                                        "priority_components": {"deadline": 40.0, "mastery": 42.5},
                                        "explanation_codes": ["DEADLINE_URGENT"],
                                        "evidence": [],
                                        "execution_status": "EXECUTED",
                                    }
                                ],
                                "llm_summary": None,
                                "supersedes_plan_id": None,
                                "superseded_by_plan_id": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
def execute_learning_plan(
    plan_id: str, user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanOut:
    """执行已采纳的计划，按条目创建个人待办。

    - 重复执行不重复创建；休息与反思条目不创建待办，未创建时 execution_task_id 为 null。
    - 计划不存在或不属于当前用户返回 404；状态不允许执行返回 409。
    """
    plan = container.learning_planner_service.execute(user_id=user.id, plan_id=plan_id)
    # 幂等兜底：在"确认"特性上线前已接受的计划，会在第一次执行时补上干预记录。
    _adopt_plan_into_intervention(container, user_id=user.id, plan_id=plan_id)
    return _out(plan)


@router.post(
    "/{plan_id}/undo",
    response_model=LearningPlanOut,
    summary="撤回计划执行",
    responses={
        200: {
            "description": "撤回成功，返回计划；已创建待办的条目 execution_status 变为 UNDONE",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "撤回计划执行",
                            "value": {
                                "plan_id": "plan_2026w40_001",
                                "goal_id": "goal_math_2025",
                                "planner_version": "planner-v3",
                                "input_digest": "sha256:9f2c1a7b",
                                "status": "ACCEPTED",
                                "as_of": "2026-10-06T08:00:00+00:00",
                                "valid_until": "2026-10-07T08:00:00+00:00",
                                "available_minutes": 120,
                                "allocated_minutes": 95,
                                "warning_codes": [],
                                "created_at": "2026-10-06T08:00:00+00:00",
                                "items": [
                                    {
                                        "item_id": "item_001",
                                        "item_type": "TASK_FOCUS",
                                        "course_id": "course_db_2025",
                                        "task_id": "task_hw3",
                                        "execution_task_id": "todo_7788",
                                        "estimated_minutes": 45,
                                        "priority_score": 82.5,
                                        "priority_components": {"deadline": 40.0, "mastery": 42.5},
                                        "explanation_codes": ["DEADLINE_URGENT"],
                                        "evidence": [],
                                        "execution_status": "UNDONE",
                                    }
                                ],
                                "llm_summary": None,
                                "supersedes_plan_id": None,
                                "superseded_by_plan_id": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
def undo_learning_plan(
    plan_id: str, user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanOut:
    """撤回计划执行，回退已创建的待办关联。

    - 撤销后保留 execution_task_id，须结合 execution_status=UNDONE 判断历史关联。
    - 计划不存在或不属于当前用户返回 404；状态不允许撤回返回 409。
    """
    return _out(container.learning_planner_service.undo(user_id=user.id, plan_id=plan_id))


@router.post(
    "/{plan_id}/replan",
    response_model=LearningPlanOut,
    summary="重新规划学习计划",
    responses={
        200: {
            "description": "重新规划成功，返回新计划并建立替代关系",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "基于原计划重规划",
                            "value": {
                                "plan_id": "plan_2026w40_002",
                                "goal_id": "goal_math_2025",
                                "planner_version": "planner-v3",
                                "input_digest": "sha256:7c1d4e88",
                                "status": "PROPOSED",
                                "as_of": "2026-10-06T20:00:00+00:00",
                                "valid_until": "2026-10-07T20:00:00+00:00",
                                "available_minutes": 90,
                                "allocated_minutes": 75,
                                "warning_codes": [],
                                "created_at": "2026-10-06T20:00:00+00:00",
                                "items": [],
                                "llm_summary": None,
                                "supersedes_plan_id": "plan_2026w40_001",
                                "superseded_by_plan_id": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
def replan_learning_plan(
    plan_id: str,
    idempotency_header: str | None = Header(None, alias="Idempotency-Key", max_length=128),
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanOut:
    """基于原计划重新规划，产出一份替代计划。

    - 新计划的 supersedes_plan_id 指向原计划，原计划 superseded_by_plan_id 指向新计划。
    - 计划不存在或不属于当前用户返回 404；相同幂等键重放返回同一新计划。
    """
    return _out(container.learning_planner_service.replan(user_id=user.id, plan_id=plan_id,
                                                           idempotency_key=idempotency_header))


@router.post(
    "/{plan_id}/feedback",
    response_model=LearningPlanFeedbackOut,
    summary="记录计划反馈",
    responses={
        200: {
            "description": "反馈已记录，返回反馈摘要",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "记录计划反馈",
                            "value": {
                                "plan_id": "plan_2026w40_001",
                                "feedback": "HELPFUL",
                                "recorded": True,
                            },
                        }
                    }
                }
            },
        }
    },
)
def feedback_learning_plan(
    plan_id: str,
    req: Annotated[
        LearningPlanFeedbackRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "反馈计划很有帮助",
                    "value": {"feedback": "HELPFUL"},
                }
            }
        ),
    ],
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanFeedbackOut:
    """记录学生对计划的反馈，并作为学习证据。

    - feedback 必须严格匹配枚举（HELPFUL/NOT_HELPFUL/TOO_LONG 等），非法值返回 422。
    - 计划不存在或不属于当前用户返回 404。
    """
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


@router.get(
    "/{plan_id}/evaluation",
    response_model=LearningPlanEvaluationOut,
    summary="评估学习计划",
    responses={
        200: {
            "description": "返回计划的执行与完成度评估",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "评估执行完成度",
                            "value": {
                                "plan_id": "plan_2026w40_001",
                                "evaluation_status": "EVALUATED",
                                "baseline_as_of": "2026-10-06T08:00:00+00:00",
                                "evaluated_as_of": "2026-10-06T22:00:00+00:00",
                                "planned_item_count": 3,
                                "executed_item_count": 2,
                                "completed_plan_task_count": 1,
                                "evidence_coverage": 0.66,
                                "warning_codes": [],
                                "evaluator_version": "evaluator-v1",
                            },
                        }
                    }
                }
            },
        }
    },
)
def evaluate_learning_plan(
    plan_id: str,
    user: UserRow = Depends(student_only),
    container: ServiceContainer = Depends(_container),
) -> LearningPlanEvaluationOut:
    """评估计划的执行情况与完成度。

    - completed_plan_task_count 为真实完成数量；EXECUTED 仅表示执行动作成功。
    - 计划不存在或不属于当前用户返回 404。
    """
    return LearningPlanEvaluationOut(**container.learning_planner_service.evaluate(user_id=user.id, plan_id=plan_id))


@router.get(
    "/{plan_id}/summary",
    response_model=LearningPlanSummaryOut,
    summary="生成阶段总结",
    responses={
        200: {
            "description": "返回计划的阶段总结，含候选模型只读金丝雀注解（可降级）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "生成阶段总结",
                            "value": {
                                "plan_id": "plan_2026w40_001",
                                "goal_id": "goal_math_2025",
                                "status": "ACCEPTED",
                                "stage": "IN_PROGRESS",
                                "headline": "本周已完成 1/3 个计划条目",
                                "completion_percent": 33,
                                "planned_item_count": 3,
                                "executed_item_count": 2,
                                "planned_minutes": 120,
                                "next_action": "继续完成剩余 2 个条目",
                                "recommendations": ["优先处理临近截止的任务"],
                                "warning_codes": [],
                                "generated_at": "2026-10-06T22:00:00+00:00",
                                "candidate_annotation": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
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
    data = await run_in_threadpool(container.learning_planner_service.summarize, user_id=user.id, plan_id=plan_id)
    plan = await run_in_threadpool(container.learning_plan_repository.get_plan, plan_id, user_id=user.id)
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

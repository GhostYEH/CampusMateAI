"""结果反馈与评估的编排：状态推进、幂等复用与边界收口。

这里验证的是"真实结果信号"确实被接上了：计划项物化、学生真的完成计划任务，
都会改变结论；而拿不到观测、没有计划、已取消的干预都不会被伪造成结论。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from adaptive_intervention_helpers import StubStateService
from app.core.config import Settings
from app.core.security import hash_password
from app.services.adaptive_agent.intervention_service import AdaptiveInterventionService
from app.services.adaptive_agent.state_analyzer import StudentStateAnalyzer
from app.services.adaptive_agent.strategy_policy import StrategyPolicy
from app.services.container import reset_container_for_tests

# 效果观测窗口独立于计划有效期，测试从持久化 due_at 推进时间。
AFTER_WINDOW = timedelta(days=8)


def _setup():
    container = reset_container_for_tests(Settings(app_env="test", database_url="sqlite:///:memory:"))
    student = container.user_repository.create_user(
        username="outcome_student", password_hash=hash_password("Demo123456"), role="student"
    )
    other = container.user_repository.create_user(
        username="outcome_other", password_hash=hash_password("Demo123456"), role="student"
    )
    for index, (title, hours) in enumerate(
        [("复习极限与连续", 8), ("整理错题本", 48), ("完成课后习题", 72)], start=1
    ):
        container.personal_task_repository.create_task(
            user_id=student.id, title=title,
            deadline=(datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(),
        )
    goal = container.student_goal_repository.create_goal(
        user_id=student.id, name="完成高等数学期末复习", category="ACADEMIC",
        target_date=(datetime.now(timezone.utc) + timedelta(days=20)).date().isoformat(),
        idempotency_key="outcome-goal-1",
    )[0]
    return container, student, other, goal


def _plan(container, student, goal, *, letter: str = "a", key: str = "run:outcome_1"):
    service = AdaptiveInterventionService(
        repository=container.adaptive_intervention_repository,
        analyzer=StudentStateAnalyzer(),
        policy=StrategyPolicy(),
        planner=container.learning_planner_service,
        state_service=StubStateService(letter),
        student_goal_repository=container.student_goal_repository,
    )
    return service.plan_for_goal(
        user_id=student.id, goal_id=goal.goal_id, available_minutes=120, idempotency_key=key,
    )


def _complete_plan_tasks(container, student, plan_id: str) -> int:
    """把计划创建的个人待办标记为完成——这是"学生真的做了"的唯一真实信号。"""
    actions = container.learning_plan_repository.list_actions(plan_id=plan_id, user_id=student.id)
    completed = 0
    for action in actions:
        if action.target_task_id and container.personal_task_repository.complete(
            action.target_task_id, user_id=student.id
        ) is not None:
            completed += 1
    return completed


def test_observing_then_evaluated_follows_real_execution() -> None:
    container, student, other, goal = _setup()
    outcome = _plan(container, student, goal)
    service = container.adaptive_intervention_service
    repository = container.adaptive_intervention_repository
    intervention_id = outcome.intervention.intervention_id
    plan_id = outcome.plan.plan_id

    # 1. 计划刚生成，还没有任何执行记录：不落库、不推进状态。
    first = service.observe_and_evaluate(user_id=student.id, intervention_id=intervention_id)
    assert first is not None
    assert first.persisted is False and first.reused_evaluation is False
    assert first.evaluation.verdict == "INCONCLUSIVE"
    assert first.evaluation.execution_signal == "NOT_STARTED"
    assert first.intervention.status == "PLAN_GENERATED"
    assert repository.get_evaluation(user_id=student.id, intervention_id=intervention_id) is None

    # 2. 接受并执行计划：待办被物化，但学生还没完成任何一条 -> 进入观测期。
    container.learning_planner_service.decide(user_id=student.id, plan_id=plan_id, decision="ACCEPT")
    container.learning_planner_service.execute(user_id=student.id, plan_id=plan_id)
    second = service.observe_and_evaluate(user_id=student.id, intervention_id=intervention_id)
    assert second is not None and second.persisted is True
    assert second.evaluation.execution_signal == "IN_PROGRESS"
    assert second.evaluation.observation_status == "IN_PROGRESS"
    assert second.intervention.status == "OBSERVING"
    assert second.intervention.observation_started_at is not None
    assert second.intervention.evaluated_at is None
    assert second.intervention.outcome_verdict == second.evaluation.verdict
    assert second.intervention.evaluation_id == second.evaluation.evaluation_id

    # 3. 同一份观测再请求一次：复用，不重复写库。
    third = service.observe_and_evaluate(user_id=student.id, intervention_id=intervention_id)
    assert third is not None
    assert third.persisted is False and third.reused_evaluation is True
    assert third.intervention.status == "OBSERVING"
    assert len(repository.list_evaluations(user_id=student.id, intervention_id=intervention_id)) == 1

    # 4. 学生完成计划任务：新观测 -> 观测完整 -> 评估完成。
    assert _complete_plan_tasks(container, student, plan_id) > 0
    fourth = service.observe_and_evaluate(user_id=student.id, intervention_id=intervention_id)
    assert fourth is not None and fourth.persisted is True
    assert fourth.evaluation.execution_signal == "COMPLETED"
    assert fourth.evaluation.observation_status == "COMPLETE"
    assert fourth.evaluation.verdict == "INCONCLUSIVE"
    assert fourth.evaluation.observed_outcome == "INSUFFICIENT_EVIDENCE"
    assert fourth.intervention.status == "OBSERVING"
    assert fourth.intervention.evaluated_at is None
    assert len(repository.list_evaluations(user_id=student.id, intervention_id=intervention_id)) == 2

    # 5. 已经是终态：同一份观测继续复用，不产生第三份评估。
    fifth = service.observe_and_evaluate(user_id=student.id, intervention_id=intervention_id)
    assert fifth is not None and fifth.reused_evaluation is True
    assert fifth.intervention.status == "OBSERVING"
    assert len(repository.list_evaluations(user_id=student.id, intervention_id=intervention_id)) == 2


def test_window_passed_without_adoption_is_evaluated_without_claiming_ineffectiveness() -> None:
    container, student, _other, goal = _setup()
    outcome = _plan(container, student, goal)
    service = container.adaptive_intervention_service
    intervention_id = outcome.intervention.intervention_id

    result = service.observe_and_evaluate(
        user_id=student.id, intervention_id=intervention_id,
        as_of=datetime.now(timezone.utc) + AFTER_WINDOW,
    )
    assert result is not None and result.persisted is True
    assert result.evaluation.execution_signal == "NOT_STARTED"
    assert result.evaluation.adoption == "NOT_STARTED"
    assert result.evaluation.observed_outcome == "INSUFFICIENT_EVIDENCE"
    assert result.evaluation.verdict == "INCONCLUSIVE"
    assert result.intervention.status == "EVALUATED"
    # 计划结构本身没问题：是没人执行，不是策略没落地。
    assert result.evaluation.plan_fidelity == "MATCHED"


def test_cancelled_intervention_is_not_resurrected() -> None:
    container, student, _other, goal = _setup()
    outcome = _plan(container, student, goal)
    service = container.adaptive_intervention_service
    repository = container.adaptive_intervention_repository
    intervention_id = outcome.intervention.intervention_id
    repository.update_status(user_id=student.id, intervention_id=intervention_id, status="CANCELLED")

    result = service.observe_and_evaluate(
        user_id=student.id, intervention_id=intervention_id,
        as_of=datetime.now(timezone.utc) + AFTER_WINDOW,
    )
    assert result is not None and result.persisted is False
    assert result.intervention.status == "CANCELLED"
    assert repository.get_evaluation(user_id=student.id, intervention_id=intervention_id) is None


def test_intervention_without_a_plan_is_inconclusive_and_not_persisted() -> None:
    """没有计划的干预没有可评估的对象：返回结论但不落库，避免留下无法解释的评估。"""
    container, student, _other, goal = _setup()
    repository = container.adaptive_intervention_repository
    from adaptive_intervention_helpers import sample_strategy

    assessment, strategy = sample_strategy("a")
    row = repository.create(
        user_id=student.id, goal_id=goal.goal_id, assessment=assessment, strategy=strategy,
        baseline_state_digest="digest", idempotency_key="run:no_plan",
    )
    assert row.plan_id is None

    result = container.adaptive_intervention_service.observe_and_evaluate(
        user_id=student.id, intervention_id=row.intervention_id
    )
    assert result is not None and result.persisted is False
    assert result.evaluation.verdict == "INCONCLUSIVE"
    assert result.evaluation.execution_signal == "UNAVAILABLE"
    assert result.intervention.status == "PROPOSED"
    assert repository.get_evaluation(user_id=student.id, intervention_id=row.intervention_id) is None


def test_missing_and_cross_user_interventions_return_none() -> None:
    container, student, other, goal = _setup()
    outcome = _plan(container, student, goal)
    service = container.adaptive_intervention_service
    assert service.observe_and_evaluate(user_id=student.id, intervention_id="intv_missing") is None
    # 非本人访问与不存在同样返回 None，由路由映射成 404，不泄露记录是否存在。
    assert service.observe_and_evaluate(
        user_id=other.id, intervention_id=outcome.intervention.intervention_id
    ) is None
    assert container.adaptive_intervention_repository.get_evaluation(
        user_id=other.id, intervention_id=outcome.intervention.intervention_id
    ) is None


def test_plan_level_observation_failure_degrades_instead_of_claiming_no_adoption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """计划级观测失败时必须降级为"判不了"，不能把取不到数据当成"学生没做"。"""
    container, student, _other, goal = _setup()
    outcome = _plan(container, student, goal)
    service = container.adaptive_intervention_service
    intervention_id = outcome.intervention.intervention_id

    def _boom(**_kwargs):
        raise RuntimeError("计划级观测不可用")

    monkeypatch.setattr(container.learning_planner_service, "evaluate", _boom)
    result = service.observe_and_evaluate(
        user_id=student.id, intervention_id=intervention_id,
        as_of=datetime.now(timezone.utc) + AFTER_WINDOW,
    )
    assert result is not None
    assert "plan_metrics_unavailable" in result.evaluation.warning_codes
    # 拿不到计划级观测时执行信号不能是 COMPLETED。
    assert result.evaluation.execution_signal != "COMPLETED"
    assert result.evaluation.execution_signals["completed_plan_task_count"] == 0


def test_injected_plan_metrics_are_used_verbatim() -> None:
    """`plan_metrics` 是测试注入点：注入的指标必须真的参与判定。"""
    container, student, _other, goal = _setup()
    outcome = _plan(container, student, goal)
    service = container.adaptive_intervention_service
    plan = container.learning_plan_repository.get_plan(outcome.plan.plan_id, user_id=student.id)
    planned = len(plan.items)

    result = service.observe_and_evaluate(
        user_id=student.id, intervention_id=outcome.intervention.intervention_id,
        plan_metrics={
            "planned_item_count": planned, "executed_item_count": planned,
            "completed_plan_task_count": planned, "evidence_coverage": 1.0,
        },
    )
    assert result is not None
    assert result.evaluation.execution_signal == "COMPLETED"
    assert result.evaluation.execution_signals["completed_plan_task_count"] == planned
    assert result.intervention.status == "OBSERVING"


def test_evaluation_is_readable_through_the_intervention_list() -> None:
    """评估结论要能被列表接口直接读到，不需要额外查询。"""
    container, student, _other, goal = _setup()
    outcome = _plan(container, student, goal)
    plan = container.learning_plan_repository.get_plan(outcome.plan.plan_id, user_id=student.id)
    container.adaptive_intervention_service.observe_and_evaluate(
        user_id=student.id, intervention_id=outcome.intervention.intervention_id,
        plan_metrics={
            "planned_item_count": len(plan.items), "executed_item_count": len(plan.items),
            "completed_plan_task_count": len(plan.items), "evidence_coverage": 1.0,
        },
    )
    rows, total = container.adaptive_intervention_repository.list_interventions(
        user_id=student.id, page=1, page_size=10
    )
    assert total == 1
    row = rows[0]
    assert row.status == "OBSERVING"
    assert row.outcome_verdict == "INCONCLUSIVE"
    assert row.evaluation_id and row.evaluation_id.startswith("inteval_")
    assert row.observation_started_at is not None and row.evaluated_at is None

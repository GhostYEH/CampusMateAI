"""场景 A/B/C 对照：同一个目标、不同的服务端状态，必须选出不同策略并生成不同计划。

这是本轮纵向切片的核心验收：状态分析 → 策略选择 → 干预记录 → 差异化计划，
四步在同一个 `AdaptiveInterventionService` 调用里串起来，且决策可追溯到具体证据。

状态用真实的 `ComputedSnapshot` 结构注入（见 `adaptive_intervention_helpers`），
规划器本身仍读取真实状态，因此 A/B/C 之间计划形态的差异只可能来自策略上下文。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from adaptive_intervention_helpers import StubStateService, scenario_a, scenario_b, scenario_c
from app.core.config import Settings
from app.core.security import hash_password
from app.services.adaptive_agent.intervention_service import AdaptiveInterventionService
from app.services.adaptive_agent.state_analyzer import StudentStateAnalyzer
from app.services.adaptive_agent.strategy_policy import StrategyPolicy
from app.services.container import reset_container_for_tests


def _setup():
    container = reset_container_for_tests(Settings(app_env="test", database_url="sqlite:///:memory:"))
    student = container.user_repository.create_user(
        username="scenario_student", password_hash=hash_password("Demo123456"), role="student"
    )
    container.personal_task_repository.create_task(
        user_id=student.id, title="复习极限与连续",
        deadline=(datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
    )
    container.personal_task_repository.create_task(
        user_id=student.id, title="整理错题本",
        deadline=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
    )
    container.personal_task_repository.create_task(
        user_id=student.id, title="完成课后习题",
        deadline=(datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
    )
    goal = container.student_goal_repository.create_goal(
        user_id=student.id, name="完成高等数学期末复习", category="ACADEMIC",
        target_date=(datetime.now(timezone.utc) + timedelta(days=20)).date().isoformat(),
        idempotency_key="scenario-goal-1",
    )[0]
    return container, student, goal


def _run(container, student, goal, letter: str, *, key: str | None = None):
    service = AdaptiveInterventionService(
        repository=container.adaptive_intervention_repository,
        analyzer=StudentStateAnalyzer(),
        policy=StrategyPolicy(),
        planner=container.learning_planner_service,
        state_service=StubStateService(letter),
        student_goal_repository=container.student_goal_repository,
    )
    return service.plan_for_goal(
        user_id=student.id, goal_id=goal.goal_id, available_minutes=120,
        idempotency_key=key or f"run:scenario_{letter}",
    )


def test_same_goal_different_state_selects_different_strategy_and_plan() -> None:
    container, student, goal = _setup()
    a = _run(container, student, goal, "a")
    b = _run(container, student, goal, "b")
    c = _run(container, student, goal, "c")

    # 同一个目标：策略差异只可能来自状态。
    assert a.intervention.goal_id == b.intervention.goal_id == c.intervention.goal_id == goal.goal_id
    codes = {a.strategy.strategy_code, b.strategy.strategy_code, c.strategy.strategy_code}
    assert len(codes) == 3, codes

    # A：知识偏低 + 执行低 + 压力高 —— 绝不能挑战升级。
    assert a.strategy.strategy_code != "CHALLENGE_UPSHIFT"
    assert a.strategy.strategy_code in {"WORKLOAD_REDUCTION", "PACE_RECOVERY"}
    assert a.strategy.priority == 2
    assert {
        "workload_pressure_high", "execution_consistency_low", "knowledge_mastery_low",
    } <= set(a.strategy.rationale_codes)
    assert "WORKLOAD_PRESSURE_HIGH" in a.assessment.problem_types
    assert "EXECUTION_CONSISTENCY_LOW" in a.assessment.problem_types
    assert "KNOWLEDGE_FOUNDATION_WEAK" in a.assessment.problem_types

    # B：知识好 + 执行高 + 压力低 —— 挑战升级，且参数明显不同。
    assert b.strategy.strategy_code == "CHALLENGE_UPSHIFT"
    assert "READY_FOR_CHALLENGE" in b.assessment.problem_types
    assert b.strategy.confidence >= 0.7
    assert b.strategy.planning_parameters.workload_scale > a.strategy.planning_parameters.workload_scale
    assert b.strategy.planning_parameters.pacing_mode == "AMBITIOUS"
    assert a.strategy.planning_parameters.pacing_mode == "COMPRESSED"

    # C：大部分状态不可用 —— 回退到保守策略，低置信度，且不做任何能力断言。
    assert c.strategy.strategy_code == "BALANCED_PROGRESS"
    assert c.strategy.priority == 1
    assert c.strategy.confidence <= 0.4
    assert "INSUFFICIENT_EVIDENCE" in c.assessment.problem_types
    assert "insufficient_evidence" in c.strategy.warning_codes
    assert "KNOWLEDGE_FOUNDATION_WEAK" not in c.assessment.problem_types
    assert "READY_FOR_CHALLENGE" not in c.assessment.problem_types


def test_scenario_a_plan_is_smaller_and_shorter_than_scenario_b() -> None:
    container, student, goal = _setup()
    a = _run(container, student, goal, "a")
    b = _run(container, student, goal, "b")

    assert a.plan.items and b.plan.items
    assert len(a.plan.items) < len(b.plan.items)
    assert a.plan.run.allocated_minutes < b.plan.run.allocated_minutes
    assert a.plan.run.allocated_minutes <= 120 and b.plan.run.allocated_minutes <= 120
    assert max(item.estimated_minutes for item in a.plan.items) < max(
        item.estimated_minutes for item in b.plan.items
    )
    assert "strategy_workload_reduction" in {
        code for item in a.plan.items for code in item.explanation_codes
    }
    assert "strategy_challenge_upshift" in {
        code for item in b.plan.items for code in item.explanation_codes
    }


def test_each_scenario_records_a_traceable_intervention() -> None:
    container, student, goal = _setup()
    outcomes = [_run(container, student, goal, letter) for letter in ("a", "b", "c")]
    rows, total = container.adaptive_intervention_repository.list_interventions(
        user_id=student.id, page=1, page_size=10
    )
    assert total == 3
    by_id = {row.intervention_id: row for row in rows}
    for outcome in outcomes:
        row = by_id[outcome.intervention.intervention_id]
        assert row.status == "PLAN_GENERATED"
        assert row.plan_id == outcome.plan.plan_id
        assert row.strategy_code == outcome.strategy.strategy_code
        # 每个问题类型都能追溯到证据：problem_types 与 evidence_refs 一一对应。
        codes = {ref.code for ref in outcome.assessment.evidence_refs}
        assert set(outcome.assessment.problem_types) <= codes
        # 保存的是生成决策那一刻的基线状态 run 引用。
        assert row.baseline_core_run_id == outcome.assessment.core_run_id
        assert row.baseline_academic_run_id == outcome.assessment.academic_run_id
        assert row.baseline_world_run_id == outcome.assessment.world_run_id
        assert row.baseline_state_digest

    # 计划里保存了安全绑定，可以反查到干预记录。
    for outcome in outcomes:
        bindings = outcome.plan.run.knowledge_bindings or {}
        assert bindings["intervention_id"] == outcome.intervention.intervention_id
        assert bindings["strategy_code"] == outcome.strategy.strategy_code


def test_replaying_the_same_run_reuses_the_frozen_decision() -> None:
    """同 Run 重放：复用已固化的策略，不重新决策、不产生第二条记录。"""
    container, student, goal = _setup()
    first = _run(container, student, goal, "a", key="run:replay")
    replay = _run(container, student, goal, "b", key="run:replay")  # 不同状态、同一幂等键

    assert replay.reused_intervention is True
    assert replay.intervention.intervention_id == first.intervention.intervention_id
    # 状态变了也不重新决策：策略冻结在记录里，保证重放结果稳定。
    assert replay.strategy.strategy_code == first.strategy.strategy_code
    assert replay.plan.plan_id == first.plan.plan_id
    assert container.adaptive_intervention_repository.count_for_user(user_id=student.id) == 1


def test_each_scenario_declaration_reconciles_against_its_real_plan() -> None:
    """策略声明的 `expected_outcomes` 必须能在真实生成的计划上对账，不能是空话。

    这是"策略 → 计划"落地性的验收：如果规划器没按策略参数收紧条目数或单项时长，
    对账会判成 NOT_REALIZED，整条策略就只是写在记录里的漂亮话。
    """
    container, student, goal = _setup()
    for letter in ("a", "b", "c"):
        outcome = _run(container, student, goal, letter)
        result = container.adaptive_intervention_service.observe_and_evaluate(
            user_id=student.id, intervention_id=outcome.intervention.intervention_id
        )
        assert result is not None
        evaluation = result.evaluation
        assert [check.code for check in evaluation.outcome_checks] == list(
            outcome.strategy.expected_outcomes
        )
        assert evaluation.plan_fidelity == "MATCHED", (
            letter, [(c.code, c.verdict, c.reason_code) for c in evaluation.outcome_checks]
        )
        # 计划刚生成、还没有执行记录：能对账但不能下"有效"的结论。
        assert evaluation.execution_signal == "NOT_STARTED"
        assert evaluation.verdict == "INCONCLUSIVE"
        assert result.persisted is False
        for check in evaluation.outcome_checks:
            assert check.evidence_refs, (letter, check.code)


def test_plan_shape_difference_between_scenarios_is_visible_in_the_evaluation() -> None:
    """A（减负）与 B（加难）的对账结论必须反映真实的计划差异，而不是同一份模板。"""
    container, student, goal = _setup()
    a = _run(container, student, goal, "a")
    b = _run(container, student, goal, "b")
    evaluations = {}
    for letter, outcome in (("a", a), ("b", b)):
        result = container.adaptive_intervention_service.observe_and_evaluate(
            user_id=student.id, intervention_id=outcome.intervention.intervention_id
        )
        assert result is not None
        evaluations[letter] = result.evaluation

    a_signals = evaluations["a"].execution_signals
    b_signals = evaluations["b"].execution_signals
    assert a_signals["planned_item_count"] < b_signals["planned_item_count"]
    assert a_signals["allocated_minutes"] < b_signals["allocated_minutes"]
    assert a_signals["available_minutes"] == b_signals["available_minutes"] == 120

    a_reasons = {c.code: c.reason_code for c in evaluations["a"].outcome_checks}
    b_reasons = {c.code: c.reason_code for c in evaluations["b"].outcome_checks}
    assert a_reasons["TOTAL_WORKLOAD_REDUCED"] == "allocated_below_available"
    assert b_reasons["CHALLENGE_INCREASED"] == "challenge_parameters_elevated"
    # 两者的期望结果集合不同：减负与加难不可能对账出同一组结论。
    assert set(a_reasons) != set(b_reasons)

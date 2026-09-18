"""StrategyPolicy —— 有限策略目录、稳定优先级与场景对照。"""
from __future__ import annotations

import pytest

from adaptive_intervention_helpers import (
    AS_OF,
    USER_SCOPE_ID,
    GoalStub,
    analyze_scenario,
    sample_strategy,
    scenario_a,
    scenario_b,
    select_for,
)
from app.schemas.adaptive_intervention import (
    CHALLENGE_CONFIDENCE_FLOOR,
    ReasonCode,
    StrategyDecision,
    StrategyPlanningParameters,
)
from app.services.adaptive_agent.state_analyzer import StudentStateAnalyzer
from app.services.adaptive_agent.strategy_policy import (
    BASELINE_ITEM_MINUTES,
    FOUNDATION_EMPHASIS_ITEM_THRESHOLD,
    StrategyPolicy,
)


def test_scenario_a_never_upshifts_challenge() -> None:
    """知识薄弱 + 执行低 + 压力高：不能选挑战升级，必须减负或恢复节奏。"""
    assessment, decision = sample_strategy("a")
    assert decision.strategy_code != "CHALLENGE_UPSHIFT"
    assert decision.strategy_code in {"WORKLOAD_REDUCTION", "PACE_RECOVERY"}
    assert decision.priority == 2  # 压力规则优先于挑战升级(5)
    # 理由同时保留压力与执行问题，以及知识薄弱信号。
    assert "workload_pressure_high" in decision.rationale_codes
    assert "execution_consistency_low" in decision.rationale_codes
    assert "knowledge_mastery_low" in decision.rationale_codes
    # 减负：更少的项、更短的单项、更小的总时长。
    balanced = StrategyPlanningParameters(
        max_plan_items=50, target_item_minutes=30, workload_scale=1.0,
        foundation_emphasis=0.2, challenge_level="BASELINE", pacing_mode="STEADY",
    )
    assert decision.planning_parameters.max_plan_items < balanced.max_plan_items
    assert decision.planning_parameters.target_item_minutes < BASELINE_ITEM_MINUTES
    assert decision.planning_parameters.workload_scale < 1.0
    assert decision.planning_parameters.challenge_level == "REDUCED"
    # 不能靠"多练"解决：不新增基础复习项。
    assert decision.planning_parameters.foundation_emphasis < FOUNDATION_EMPHASIS_ITEM_THRESHOLD
    assert assessment.goal_id == GoalStub().goal_id


def test_scenario_b_upshifts_challenge_with_identical_goal() -> None:
    _, a = sample_strategy("a")
    _, b = sample_strategy("b")
    assert a.strategy_code != b.strategy_code
    assert b.strategy_code == "CHALLENGE_UPSHIFT"
    assert b.priority == 5
    assert b.confidence >= CHALLENGE_CONFIDENCE_FLOOR
    assert b.planning_parameters.target_item_minutes > a.planning_parameters.target_item_minutes
    assert b.planning_parameters.max_plan_items > a.planning_parameters.max_plan_items
    assert b.planning_parameters.workload_scale > a.planning_parameters.workload_scale
    assert b.planning_parameters.challenge_level == "ELEVATED"
    assert b.planning_parameters.pacing_mode == "AMBITIOUS"
    assert a.planning_parameters.pacing_mode == "COMPRESSED"
    # 同一目标，不同状态 → 不同策略与不同参数。
    assert analyze_scenario("a").goal_id == analyze_scenario("b").goal_id == GoalStub().goal_id


def test_scenario_c_falls_back_to_balanced_progress() -> None:
    assessment, decision = sample_strategy("c")
    assert decision.strategy_code == "BALANCED_PROGRESS"
    assert decision.priority == 1
    assert decision.confidence <= 0.4
    assert "insufficient_evidence" in decision.warning_codes
    assert "strategy_from_degraded_state" in decision.warning_codes
    # 不做知识薄弱/高能力断言，也不做激进判断。
    assert "knowledge_mastery_low" not in decision.rationale_codes
    assert "knowledge_mastery_strong" not in decision.rationale_codes
    assert decision.planning_parameters.challenge_level == "BASELINE"
    assert "INSUFFICIENT_EVIDENCE" in assessment.problem_types


def test_high_pressure_beats_challenge_upshift() -> None:
    core, academic, world, goal = scenario_b()
    # 在"完全准备好挑战"的状态上叠加高压力，必须让位给减负。
    world.snapshots[0] = world.snapshots[0].__class__(
        **{**world.snapshots[0].__dict__, "value": {
            "pressure_band": "VERY_HIGH", "task_count": 12, "exam_count": 3,
            "concentrated_dates": ["2026-09-19", "2026-09-20"], "data_completeness": "verified",
        }}
    )
    assessment = StudentStateAnalyzer().analyze(
        user_id=USER_SCOPE_ID, as_of=AS_OF, core=core, academic=academic, world=world, goal=goal,
    )
    assert "READY_FOR_CHALLENGE" not in assessment.problem_types
    assert "WORKLOAD_PRESSURE_HIGH" in assessment.problem_types
    decision = select_for(assessment, goal=goal, available_minutes=60)
    assert decision.strategy_code == "WORKLOAD_REDUCTION"


def test_knowledge_weak_alone_triggers_foundation_reinforcement() -> None:
    core, academic, world, goal = scenario_b()
    weak = academic.snapshots[1].__class__(
        **{**academic.snapshots[1].__dict__, "value": {
            "knowledge_point_count": 40, "own_mastery_rate": 42.0,
            "mastery_gap_vs_class": -9.0, "data_completeness": "verified",
        }}
    )
    academic = academic.__class__(academic.run_id, [academic.snapshots[0], weak])
    assessment = StudentStateAnalyzer().analyze(
        user_id=USER_SCOPE_ID, as_of=AS_OF, core=core, academic=academic, world=world, goal=goal,
    )
    assert "KNOWLEDGE_FOUNDATION_WEAK" in assessment.problem_types
    decision = select_for(assessment, goal=goal, available_minutes=60)
    assert decision.strategy_code == "FOUNDATION_REINFORCEMENT"
    assert decision.priority == 4
    assert decision.planning_parameters.foundation_emphasis >= FOUNDATION_EMPHASIS_ITEM_THRESHOLD
    assert "FOUNDATION_REVIEW_INCREASED" in decision.expected_outcomes


def test_pace_recovery_for_execution_and_routine_signals() -> None:
    core, academic, world, goal = scenario_b()
    world = world.__class__(world.run_id, [
        world.snapshots[0],
        world.snapshots[1].__class__(**{**world.snapshots[1].__dict__, "value": {
            "planned_task_count": 10, "executed_task_count": 1,
            "consistency_ratio": 0.1, "consistency_band": "low", "data_completeness": "verified",
        }}),
        *world.snapshots[2:],
    ])
    assessment = StudentStateAnalyzer().analyze(
        user_id=USER_SCOPE_ID, as_of=AS_OF, core=core, academic=academic, world=world, goal=goal,
    )
    decision = select_for(assessment, goal=goal, available_minutes=60)
    assert decision.strategy_code == "PACE_RECOVERY"
    assert decision.priority == 3
    assert decision.planning_parameters.target_item_minutes < BASELINE_ITEM_MINUTES
    assert "SHORT_ITEM_PRIORITIZED" in decision.expected_outcomes


def test_selection_is_deterministic() -> None:
    assessment, first = sample_strategy("a")
    policy = StrategyPolicy()
    second = policy.select(assessment=assessment, goal=GoalStub(), available_minutes=60)
    third = policy.select(assessment=assessment, goal=GoalStub(), available_minutes=60)
    assert first.model_dump(mode="json") == second.model_dump(mode="json") == third.model_dump(mode="json")


def test_rationale_codes_come_from_assessment_only() -> None:
    for letter in ("a", "b", "c"):
        assessment = analyze_scenario(letter)
        decision = select_for(assessment, available_minutes=60)
        allowed = set()
        for codes in assessment.reason_codes.values():
            allowed.update(codes)
        for signal in assessment.risk_signals:
            allowed.update(signal.reason_codes)
        assert set(decision.rationale_codes) <= allowed
        assert set(decision.rationale_codes) <= set(ReasonCode.__args__)  # type: ignore[attr-defined]


@pytest.mark.parametrize("minutes", [1, 5, 15, 30, 45, 60, 120, 600, 1440])
@pytest.mark.parametrize("letter", ["a", "b", "c"])
def test_planning_parameters_are_bounded_and_self_consistent(letter: str, minutes: int) -> None:
    assessment = analyze_scenario(letter)
    decision = select_for(assessment, available_minutes=minutes)
    params = decision.planning_parameters
    StrategyPlanningParameters(**params.model_dump())  # 上下界必须成立
    assert 1 <= params.max_plan_items <= 50
    assert 5 <= params.target_item_minutes <= 120
    assert 0.2 <= params.workload_scale <= 1.5
    if minutes >= 5:
        # 单项时长不能超过本次可用总时长。
        assert params.target_item_minutes <= minutes


def test_strategy_decision_schema_rejects_unsupported_semantics() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        # 挑战升级不允许在低置信度下出现。
        StrategyDecision(
            strategy_code="CHALLENGE_UPSHIFT", priority=5, rationale_codes=["workload_manageable"],
            confidence=0.2, expected_outcomes=["CHALLENGE_INCREASED"],
            planning_parameters=StrategyPlanningParameters(
                max_plan_items=5, target_item_minutes=30, workload_scale=1.0,
                foundation_emphasis=0.1, challenge_level="ELEVATED", pacing_mode="AMBITIOUS",
            ),
        )
    with pytest.raises(ValidationError):
        # 减负策略必须由压力或冲突信号支撑。
        StrategyDecision(
            strategy_code="WORKLOAD_REDUCTION", priority=2, rationale_codes=["rhythm_stable"],
            confidence=0.9, expected_outcomes=["TOTAL_WORKLOAD_REDUCED"],
            planning_parameters=StrategyPlanningParameters(
                max_plan_items=3, target_item_minutes=20, workload_scale=0.75,
                foundation_emphasis=0.4, challenge_level="REDUCED", pacing_mode="COMPRESSED",
            ),
        )

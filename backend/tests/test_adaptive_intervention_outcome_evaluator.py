"""InterventionOutcomeEvaluator —— 期望结果对账与执行信号的确定性判定。

这里断言的是**判定规则本身**：哪些声明可以直接在计划结构上对账、哪些必须等真实
执行信号、哪些在证据不足时必须判成"判不了"而不是"没做到"。评估器不碰数据库，
所以全部用纯输入输出验证。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.models.adaptive_intervention import AdaptiveInterventionRow
from app.schemas.adaptive_intervention import (
    EXECUTION_SIGNAL_KEYS,
    InterventionEvaluation,
    StrategyDecision,
    StrategyPlanningParameters,
)
from app.services.adaptive_agent.outcome_evaluator import (
    WARNING_PLAN_METRICS_UNAVAILABLE,
    WARNING_WINDOW_UNPARSABLE,
    InterventionOutcomeEvaluator,
    PlanObservation,
)

USER = "user_outcome_1"
AS_OF = datetime(2026, 9, 18, 2, 0, tzinfo=timezone.utc)
WINDOW_END_FUTURE = (AS_OF + timedelta(days=7)).isoformat()
WINDOW_END_PAST = (AS_OF - timedelta(days=1)).isoformat()


def _strategy(code: str, *, expected_outcomes, rationale_codes=("workload_pressure_high",), **params):
    base = dict(
        max_plan_items=3, target_item_minutes=20, workload_scale=0.75,
        foundation_emphasis=0.4, challenge_level="REDUCED", pacing_mode="COMPRESSED",
    )
    base.update(params)
    return StrategyDecision(
        strategy_code=code, priority=2, rationale_codes=list(rationale_codes), confidence=0.8,
        expected_outcomes=list(expected_outcomes),
        planning_parameters=StrategyPlanningParameters(**base),
    )


def _intervention(strategy: StrategyDecision, *, plan_id: str | None = "plan_1",
                  data_quality: str = "verified") -> AdaptiveInterventionRow:
    assessment_json = json.dumps({"data_quality": data_quality, "problem_types": []})
    return AdaptiveInterventionRow(
        intervention_id="intv_test_1", user_id=USER, goal_id="goal_1", plan_id=plan_id,
        agent_job_id=None, agent_run_id=None, status="PLAN_GENERATED",
        strategy_code=strategy.strategy_code, strategy_version=strategy.strategy_version,
        assessment_id="as_1", assessment_json=assessment_json,
        strategy_json=json.dumps(strategy.model_dump(mode="json")),
        rationale_codes_json=json.dumps(list(strategy.rationale_codes)),
        expected_outcomes_json=json.dumps(list(strategy.expected_outcomes)),
        baseline_core_run_id="lrun_core", baseline_academic_run_id="lrun_academic",
        baseline_world_run_id="lrun_world", baseline_state_digest="digest", confidence=0.8,
        warning_codes_json="[]", idempotency_key="key",
        observation_started_at=None, evaluated_at=None, outcome_verdict=None, evaluation_id=None,
        created_at="t", updated_at="t",
    )


def _item(item_id: str, item_type: str, minutes: int, *, status: str = "PENDING", codes=()) -> dict:
    return {
        "item_id": item_id, "item_type": item_type, "estimated_minutes": minutes,
        "execution_status": status, "explanation_codes": tuple(codes),
    }


def _observation(*, items=(), metrics=None, allocated=60, available=120,
                 window_end: str | None = WINDOW_END_FUTURE) -> PlanObservation:
    return PlanObservation(
        plan_id="plan_1", run_id="lprun_1", allocated_minutes=allocated, available_minutes=available,
        window_start=AS_OF.isoformat(), window_end=window_end,
        items=tuple(items), metrics=metrics,
    )


def _metrics(*, executed=0, completed_tasks=0, coverage=0.0) -> dict:
    return {
        "evaluation_status": "OUTCOME_OBSERVED" if executed else "INSUFFICIENT_EVIDENCE",
        "planned_item_count": executed, "executed_item_count": executed,
        "completed_plan_task_count": completed_tasks, "evidence_coverage": coverage,
    }


def _checks(evaluation: InterventionEvaluation) -> dict[str, str]:
    return {check.code: check.verdict for check in evaluation.outcome_checks}


def _reasons(evaluation: InterventionEvaluation) -> dict[str, str]:
    return {check.code: check.reason_code for check in evaluation.outcome_checks}


# --------------------------------------------------------------- 计划结构对账


def test_reduced_workload_plan_reconciles_every_claim() -> None:
    """减负策略的三条声明都能在计划结构上直接对账。"""
    strategy = _strategy(
        "WORKLOAD_REDUCTION",
        expected_outcomes=["TOTAL_WORKLOAD_REDUCED", "ITEM_COUNT_REDUCED", "DEADLINE_PRIORITY_PRESERVED"],
        rationale_codes=("workload_pressure_high", "deadline_concentration_observed"),
    )
    observation = _observation(
        items=[
            _item("i1", "TASK_FOCUS", 20, codes=["deadline_urgent"]),
            _item("i2", "GOAL_PROGRESS", 20),
            _item("i3", "REVIEW_AND_REFLECT", 20),
        ],
        metrics=_metrics(),
    )
    result = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(strategy), observation=observation, as_of=AS_OF
    )
    evaluation = result.evaluation
    assert _checks(evaluation) == {
        "TOTAL_WORKLOAD_REDUCED": "REALIZED",
        "ITEM_COUNT_REDUCED": "REALIZED",
        "DEADLINE_PRIORITY_PRESERVED": "REALIZED",
    }
    assert _reasons(evaluation)["TOTAL_WORKLOAD_REDUCED"] == "allocated_below_available"
    assert evaluation.plan_fidelity == "MATCHED"
    # 一条执行记录都没有且窗口未结束：还不能下结论。
    assert evaluation.verdict == "INCONCLUSIVE"
    assert evaluation.execution_signal == "NOT_STARTED"
    assert evaluation.observation_status == "NOT_STARTED"
    # 每条判定都必须带证据引用，且只指向既有结构化对象。
    for check in evaluation.outcome_checks:
        assert check.evidence_refs
        assert {ref.kind for ref in check.evidence_refs} <= {
            "INTERVENTION", "PLAN_RUN", "PLAN_ITEM", "PLAN_EVALUATION", "STRATEGY_DECISION",
        }


def test_reduction_claim_fails_when_plan_uses_the_whole_budget() -> None:
    """策略声明减负，但计划把预算用满了：策略没落地，必须判成未通过。"""
    strategy = _strategy(
        "WORKLOAD_REDUCTION",
        expected_outcomes=["TOTAL_WORKLOAD_REDUCED", "ITEM_COUNT_REDUCED"],
    )
    observation = _observation(items=[_item("i1", "TASK_FOCUS", 30)], allocated=120, available=120)
    evaluation = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(strategy), observation=observation, as_of=AS_OF
    ).evaluation
    assert _checks(evaluation) == {
        "TOTAL_WORKLOAD_REDUCED": "NOT_REALIZED",
        "ITEM_COUNT_REDUCED": "REALIZED",
    }
    assert _reasons(evaluation)["TOTAL_WORKLOAD_REDUCED"] == "allocated_equals_available"
    assert evaluation.plan_fidelity == "MISMATCHED"
    # 有通过也有未通过 -> 部分有效（窗口未结束也不能说"没观测到"，因为已经有对账结果）。
    assert evaluation.verdict == "INCONCLUSIVE"


def test_item_count_cap_and_short_item_target_are_both_enforced() -> None:
    strategy = _strategy(
        "PACE_RECOVERY",
        expected_outcomes=["ITEM_COUNT_REDUCED", "SHORT_ITEM_PRIORITIZED"],
        max_plan_items=3, target_item_minutes=15, workload_scale=0.7,
        foundation_emphasis=0.3, pacing_mode="COMPRESSED",
    )
    observation = _observation(items=[
        _item("i1", "TASK_FOCUS", 15), _item("i2", "GOAL_PROGRESS", 15),
        _item("i3", "CAMPUS_AFFAIRS", 15), _item("i4", "GOAL_PROGRESS", 15),
    ])
    evaluation = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(strategy), observation=observation, as_of=AS_OF
    ).evaluation
    assert _checks(evaluation) == {
        "ITEM_COUNT_REDUCED": "NOT_REALIZED",
        "SHORT_ITEM_PRIORITIZED": "REALIZED",
    }
    assert _reasons(evaluation)["ITEM_COUNT_REDUCED"] == "item_count_exceeds_strategy_cap"


def test_foundation_reinforcement_needs_review_items_to_be_realized() -> None:
    strategy = _strategy(
        "FOUNDATION_REINFORCEMENT",
        expected_outcomes=["FOUNDATION_REVIEW_INCREASED"],
        foundation_emphasis=0.7, challenge_level="REDUCED", pacing_mode="STEADY",
    )
    with_review = _observation(items=[
        _item("i1", "TASK_FOCUS", 25),
        _item("i2", "REVIEW_AND_REFLECT", 25, codes=["knowledge_mastery_observation_supports_review"]),
    ])
    realized = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(strategy), observation=with_review, as_of=AS_OF
    ).evaluation
    assert _checks(realized) == {"FOUNDATION_REVIEW_INCREASED": "REALIZED"}
    assert _reasons(realized)["FOUNDATION_REVIEW_INCREASED"] == "foundation_review_items_present"
    assert {ref.kind for ref in realized.outcome_checks[0].evidence_refs} == {"PLAN_ITEM"}

    without_review = _observation(items=[_item("i1", "TASK_FOCUS", 25)])
    missing = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(strategy), observation=without_review, as_of=AS_OF
    ).evaluation
    assert _checks(missing) == {"FOUNDATION_REVIEW_INCREASED": "NOT_REALIZED"}
    assert _reasons(missing)["FOUNDATION_REVIEW_INCREASED"] == "foundation_review_items_missing"


def test_challenge_upshift_claim_is_reconciled_from_declared_parameters() -> None:
    upshift = _strategy(
        "CHALLENGE_UPSHIFT", expected_outcomes=["CHALLENGE_INCREASED"],
        max_plan_items=10, target_item_minutes=30, workload_scale=1.15,
        foundation_emphasis=0.1, challenge_level="ELEVATED", pacing_mode="AMBITIOUS",
    )
    observation = _observation(items=[_item("i1", "EXAM_PREPARATION", 30)], allocated=120, available=120)
    realized = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(upshift), observation=observation, as_of=AS_OF
    ).evaluation
    assert _checks(realized) == {"CHALLENGE_INCREASED": "REALIZED"}
    assert _reasons(realized)["CHALLENGE_INCREASED"] == "challenge_parameters_elevated"

    not_elevated = _strategy(
        "CHALLENGE_UPSHIFT", expected_outcomes=["CHALLENGE_INCREASED"],
        max_plan_items=10, target_item_minutes=30, workload_scale=1.0,
        foundation_emphasis=0.1, challenge_level="BASELINE", pacing_mode="STEADY",
    )
    failed = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(not_elevated), observation=observation, as_of=AS_OF
    ).evaluation
    assert _checks(failed) == {"CHALLENGE_INCREASED": "NOT_REALIZED"}
    assert _reasons(failed)["CHALLENGE_INCREASED"] == "challenge_parameters_not_elevated"


def test_baseline_progress_preserves_baseline_rules() -> None:
    baseline = _strategy(
        "BALANCED_PROGRESS", expected_outcomes=["BASELINE_RULES_PRESERVED"],
        rationale_codes=("evidence_insufficient",), max_plan_items=50, target_item_minutes=30,
        workload_scale=1.0, foundation_emphasis=0.2, challenge_level="BASELINE", pacing_mode="STEADY",
    )
    observation = _observation(items=[_item("i1", "TASK_FOCUS", 30)])
    evaluation = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(baseline), observation=observation, as_of=AS_OF
    ).evaluation
    assert _checks(evaluation) == {"BASELINE_RULES_PRESERVED": "REALIZED"}
    assert _reasons(evaluation)["BASELINE_RULES_PRESERVED"] == "strategy_parameters_baseline"


def test_deadline_claim_is_unverifiable_without_prior_deadline_pressure() -> None:
    """当时没有截止时间压力，就不能声称"保留了截止时间优先"——这是无对象的对账。"""
    strategy = _strategy(
        "BALANCED_PROGRESS", expected_outcomes=["DEADLINE_PRIORITY_PRESERVED"],
        rationale_codes=("evidence_insufficient",), max_plan_items=50, target_item_minutes=30,
        workload_scale=1.0, foundation_emphasis=0.2, challenge_level="BASELINE", pacing_mode="STEADY",
    )
    observation = _observation(items=[_item("i1", "TASK_FOCUS", 30)])
    evaluation = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(strategy), observation=observation, as_of=AS_OF
    ).evaluation
    assert _checks(evaluation) == {"DEADLINE_PRIORITY_PRESERVED": "UNVERIFIABLE"}
    assert _reasons(evaluation)["DEADLINE_PRIORITY_PRESERVED"] == "no_prior_deadline_pressure"
    assert evaluation.plan_fidelity == "UNVERIFIABLE"
    assert evaluation.verdict == "INCONCLUSIVE"


def test_deadline_claim_fails_when_pressure_existed_but_no_item_addresses_it() -> None:
    strategy = _strategy(
        "WORKLOAD_REDUCTION", expected_outcomes=["DEADLINE_PRIORITY_PRESERVED"],
        rationale_codes=("workload_pressure_high", "upcoming_exam_exposure"),
    )
    observation = _observation(items=[_item("i1", "TASK_FOCUS", 20)])
    evaluation = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(strategy), observation=observation, as_of=AS_OF
    ).evaluation
    assert _checks(evaluation) == {"DEADLINE_PRIORITY_PRESERVED": "NOT_REALIZED"}
    assert _reasons(evaluation)["DEADLINE_PRIORITY_PRESERVED"] == "deadline_driven_items_missing"


# --------------------------------------------------------------- 执行信号


def test_execution_continuity_needs_plan_level_observation() -> None:
    """`EXECUTION_CONTINUITY_RESTORED` 只能由"计划创建的任务真的完成"来判定。"""
    strategy = _strategy(
        "PACE_RECOVERY", expected_outcomes=["EXECUTION_CONTINUITY_RESTORED"],
        target_item_minutes=15, workload_scale=0.7, foundation_emphasis=0.3, pacing_mode="COMPRESSED",
    )
    items = [_item("i1", "TASK_FOCUS", 15, status="SUCCEEDED")]

    # 拿不到计划级观测：不能把"没拿到数据"当成"没有执行"。
    no_metrics = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(strategy),
        observation=_observation(items=items, metrics=None, window_end=WINDOW_END_PAST),
        as_of=AS_OF,
    ).evaluation
    assert _checks(no_metrics) == {"EXECUTION_CONTINUITY_RESTORED": "UNVERIFIABLE"}
    assert WARNING_PLAN_METRICS_UNAVAILABLE in no_metrics.warning_codes
    # 没有计划级观测时执行信号最多到 IN_PROGRESS，绝不能凭"待办建出来了"判定完成。
    assert no_metrics.execution_signal == "IN_PROGRESS"

    # 窗口已过且确实零完成：可以判定未达成。
    window_passed = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(strategy),
        observation=_observation(items=items, metrics=_metrics(executed=1), window_end=WINDOW_END_PAST),
        as_of=AS_OF,
    ).evaluation
    assert _checks(window_passed) == {"EXECUTION_CONTINUITY_RESTORED": "NOT_REALIZED"}
    assert _reasons(window_passed)["EXECUTION_CONTINUITY_RESTORED"] == "execution_not_observed_on_plan"

    # 有完成记录：达成。
    realized = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(strategy),
        observation=_observation(items=items, metrics=_metrics(executed=1, completed_tasks=1)),
        as_of=AS_OF,
    ).evaluation
    assert _checks(realized) == {"EXECUTION_CONTINUITY_RESTORED": "REALIZED"}


def test_execution_signal_progresses_from_not_started_to_completed() -> None:
    strategy = _strategy(
        "WORKLOAD_REDUCTION",
        expected_outcomes=["TOTAL_WORKLOAD_REDUCED", "ITEM_COUNT_REDUCED"],
    )
    evaluator = InterventionOutcomeEvaluator()
    intervention = _intervention(strategy)

    not_started = evaluator.evaluate(
        intervention=intervention,
        observation=_observation(items=[_item("i1", "TASK_FOCUS", 20), _item("i2", "GOAL_PROGRESS", 20)]),
        as_of=AS_OF,
    ).evaluation
    assert not_started.execution_signal == "NOT_STARTED"

    partial = evaluator.evaluate(
        intervention=intervention,
        observation=_observation(
            items=[_item("i1", "TASK_FOCUS", 20, status="SUCCEEDED"), _item("i2", "GOAL_PROGRESS", 20)],
            metrics=_metrics(executed=1),
        ),
        as_of=AS_OF,
    ).evaluation
    assert partial.execution_signal == "IN_PROGRESS"
    assert partial.observation_status == "IN_PROGRESS"
    assert partial.verdict == "INCONCLUSIVE"

    completed = evaluator.evaluate(
        intervention=intervention,
        observation=_observation(
            items=[_item("i1", "TASK_FOCUS", 20, status="SUCCEEDED"), _item("i2", "GOAL_PROGRESS", 20, status="SUCCEEDED")],
            metrics=_metrics(executed=2, completed_tasks=2, coverage=1.0),
        ),
        as_of=AS_OF,
    ).evaluation
    assert completed.execution_signal == "COMPLETED"
    assert completed.observation_status == "COMPLETE"
    assert completed.verdict == "INCONCLUSIVE"
    assert completed.adoption == "COMPLETED"
    assert completed.plan_fidelity == "MATCHED"
    assert completed.confidence == 1.0
    assert completed.execution_signals["completed_plan_task_count"] == 2
    assert completed.execution_signals["window_elapsed"] is False


def test_window_passed_without_any_adoption_is_not_a_state_outcome() -> None:
    """窗口结束却一条执行记录都没有：干预没有被采纳，这是可下的结论。"""
    strategy = _strategy(
        "WORKLOAD_REDUCTION",
        expected_outcomes=["TOTAL_WORKLOAD_REDUCED", "ITEM_COUNT_REDUCED"],
    )
    evaluation = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(strategy),
        observation=_observation(
            items=[_item("i1", "TASK_FOCUS", 20), _item("i2", "GOAL_PROGRESS", 20)],
            metrics=_metrics(), window_end=WINDOW_END_PAST,
        ),
        as_of=AS_OF,
    ).evaluation
    assert evaluation.execution_signal == "NOT_STARTED"
    assert evaluation.verdict == "INCONCLUSIVE"
    assert evaluation.observed_outcome == "INSUFFICIENT_EVIDENCE"
    assert "adoption_not_observed" not in evaluation.warning_codes
    assert evaluation.plan_fidelity == "MATCHED"  # 计划结构没问题，是没人执行
    # 窗口走完就是观测完整：零执行本身就是要观测到的事实，不是"还没开始观测"。
    assert evaluation.observation_status == "COMPLETE"
    assert evaluation.execution_signals["window_elapsed"] is True


def test_unparsable_window_is_treated_as_not_elapsed() -> None:
    """窗口解析不了就不能断言"窗口已过"，否则会把未知当成"零执行"。"""
    strategy = _strategy("WORKLOAD_REDUCTION", expected_outcomes=["TOTAL_WORKLOAD_REDUCED"])
    evaluation = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(strategy),
        observation=_observation(items=[_item("i1", "TASK_FOCUS", 20)], window_end="not-a-date"),
        as_of=AS_OF,
    ).evaluation
    assert WARNING_WINDOW_UNPARSABLE in evaluation.warning_codes
    assert evaluation.execution_signals["window_elapsed"] is False
    assert evaluation.verdict == "INCONCLUSIVE"


# --------------------------------------------------------------- 缺失与边界


def test_missing_plan_is_inconclusive_and_never_claims_failure() -> None:
    strategy = _strategy(
        "WORKLOAD_REDUCTION",
        expected_outcomes=["TOTAL_WORKLOAD_REDUCED", "ITEM_COUNT_REDUCED"],
    )
    result = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(strategy), observation=None, as_of=AS_OF
    )
    evaluation = result.evaluation
    assert _checks(evaluation) == {
        "TOTAL_WORKLOAD_REDUCED": "UNVERIFIABLE",
        "ITEM_COUNT_REDUCED": "UNVERIFIABLE",
    }
    assert set(_reasons(evaluation).values()) == {"plan_not_found"}
    assert evaluation.execution_signal == "UNAVAILABLE"
    assert evaluation.verdict == "INCONCLUSIVE"
    assert evaluation.plan_fidelity == "UNVERIFIABLE"
    assert evaluation.data_quality == "unavailable"
    assert evaluation.confidence == 0.0
    assert evaluation.execution_signals["planned_item_count"] == 0
    # 没有计划就不是"没做到"，任何判定都不能是 NOT_REALIZED。
    assert all(check.verdict != "NOT_REALIZED" for check in evaluation.outcome_checks)


def test_no_bound_plan_uses_a_distinct_reason_code() -> None:
    strategy = _strategy("WORKLOAD_REDUCTION", expected_outcomes=["TOTAL_WORKLOAD_REDUCED"])
    evaluation = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(strategy, plan_id=None), observation=None, as_of=AS_OF
    ).evaluation
    assert _reasons(evaluation) == {"TOTAL_WORKLOAD_REDUCED": "no_plan_bound"}


def test_empty_plan_makes_structural_claims_unverifiable() -> None:
    """空计划不能因为"0 条 ≤ 上限"就把减负判成达成。"""
    strategy = _strategy("WORKLOAD_REDUCTION", expected_outcomes=["ITEM_COUNT_REDUCED"])
    evaluation = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(strategy), observation=_observation(items=[]), as_of=AS_OF
    ).evaluation
    assert _checks(evaluation) == {"ITEM_COUNT_REDUCED": "UNVERIFIABLE"}
    assert _reasons(evaluation) == {"ITEM_COUNT_REDUCED": "plan_has_no_items"}


def test_data_quality_describes_what_this_evaluation_could_see() -> None:
    """data_quality 说的是"这次评估能看到什么"，不是"计划是在多差的状态下选出来的"。"""
    strategy = _strategy("WORKLOAD_REDUCTION", expected_outcomes=["TOTAL_WORKLOAD_REDUCED"])
    evaluator = InterventionOutcomeEvaluator()
    items = [_item("i1", "TASK_FOCUS", 20)]

    verified = evaluator.evaluate(
        intervention=_intervention(strategy, data_quality="verified"),
        observation=_observation(items=items, metrics=_metrics()),
        as_of=AS_OF,
    ).evaluation
    assert verified.data_quality == "verified"

    stale = evaluator.evaluate(
        intervention=_intervention(strategy, data_quality="stale"),
        observation=_observation(items=items, metrics=_metrics()),
        as_of=AS_OF,
    ).evaluation
    assert stale.data_quality == "stale"

    # 执行观测缺一块：质量上限被压到 partial，即使策略当时的判断依据是 verified。
    missing_metrics = evaluator.evaluate(
        intervention=_intervention(strategy, data_quality="verified"),
        observation=_observation(items=items, metrics=None),
        as_of=AS_OF,
    ).evaluation
    assert missing_metrics.data_quality == "partial"
    assert WARNING_PLAN_METRICS_UNAVAILABLE in missing_metrics.warning_codes


def test_evaluation_id_is_deterministic_and_tracks_the_observation() -> None:
    """同一份观测必须得到完全相同的评估（含 id）；观测一变就必须是新的一份。"""
    strategy = _strategy("WORKLOAD_REDUCTION", expected_outcomes=["TOTAL_WORKLOAD_REDUCED"])
    intervention = _intervention(strategy)
    evaluator = InterventionOutcomeEvaluator()
    first = evaluator.evaluate(
        intervention=intervention,
        observation=_observation(items=[_item("i1", "TASK_FOCUS", 20)]),
        as_of=AS_OF,
    )
    again = evaluator.evaluate(
        intervention=intervention,
        observation=_observation(items=[_item("i1", "TASK_FOCUS", 20)]),
        as_of=AS_OF + timedelta(hours=3),  # 同一份观测、不同的评估时刻
    )
    assert first.evaluation.evaluation_id == again.evaluation.evaluation_id
    assert first.input_digest == again.input_digest

    changed = evaluator.evaluate(
        intervention=intervention,
        observation=_observation(items=[_item("i1", "TASK_FOCUS", 20, status="SUCCEEDED")]),
        as_of=AS_OF,
    )
    assert changed.evaluation.evaluation_id != first.evaluation.evaluation_id
    assert changed.input_digest != first.input_digest


def test_evaluation_never_invents_state_causality() -> None:
    """评估只由对账与执行信号构成：不得出现任何"状态变好所以有效"的字段。"""
    strategy = _strategy("WORKLOAD_REDUCTION", expected_outcomes=["TOTAL_WORKLOAD_REDUCED"])
    evaluation = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(strategy),
        observation=_observation(items=[_item("i1", "TASK_FOCUS", 20, status="SUCCEEDED")],
                                 metrics=_metrics(executed=1)),
        as_of=AS_OF,
    ).evaluation
    assert set(evaluation.execution_signals) <= EXECUTION_SIGNAL_KEYS
    summary = evaluation.safe_summary()
    for forbidden in ("state_delta", "causal", "attribution", "state_improvement"):
        assert forbidden not in summary
    # 评估载荷里不允许出现任何"评估之后"的状态投影 run 引用。
    serialized = json.dumps(evaluation.model_dump(mode="json"), ensure_ascii=False)
    assert "lrun_post" not in serialized
    assert "snapshot" not in serialized


def test_completed_plan_is_adoption_not_observed_improvement() -> None:
    """完成任务只说明采纳；没有前后状态比较时不得声称状态改善。"""
    strategy = _strategy("WORKLOAD_REDUCTION", expected_outcomes=["TOTAL_WORKLOAD_REDUCED"])
    evaluation = InterventionOutcomeEvaluator().evaluate(
        intervention=_intervention(strategy),
        observation=_observation(
            items=[_item("i1", "TASK_FOCUS", 20, status="SUCCEEDED")],
            metrics=_metrics(executed=1, completed_tasks=1, coverage=1.0),
        ),
        as_of=AS_OF,
    ).evaluation

    assert evaluation.adoption == "COMPLETED"
    assert evaluation.observed_outcome == "INSUFFICIENT_EVIDENCE"
    assert evaluation.causal_claim == "NOT_ESTIMATED"


# --------------------------------------------------------------- 契约自洽


def test_schema_rejects_an_effective_verdict_without_evidence() -> None:
    """契约层必须挡住"没有依据的有效"：EFFECTIVE 要求结构一致且执行完成。"""
    payload = dict(
        evaluation_id="inteval_x", intervention_id="intv_x", user_id=USER, goal_id="goal_1",
        plan_id="plan_1", as_of=AS_OF.isoformat(), window_start=None, window_end=None,
        observation_status="IN_PROGRESS", execution_signal="IN_PROGRESS", plan_fidelity="MATCHED",
        verdict="EFFECTIVE", outcome_checks=[], execution_signals={}, confidence=0.5,
        data_quality="verified", warning_codes=[],
    )
    with pytest.raises(ValidationError):
        InterventionEvaluation(**payload)

    payload["plan_fidelity"] = "UNVERIFIABLE"
    payload["execution_signal"] = "COMPLETED"
    payload["verdict"] = "EFFECTIVE"
    with pytest.raises(ValidationError):
        InterventionEvaluation(**payload)


def test_schema_rejects_unregistered_signal_keys() -> None:
    with pytest.raises(ValidationError):
        InterventionEvaluation(
            evaluation_id="inteval_x", intervention_id="intv_x", user_id=USER, goal_id="goal_1",
            as_of=AS_OF.isoformat(), observation_status="NOT_STARTED", execution_signal="UNAVAILABLE",
            plan_fidelity="UNVERIFIABLE", verdict="INCONCLUSIVE", execution_signals={"free_form": 1},
            confidence=0.0, data_quality="unavailable",
        )


def test_schema_rejects_duplicate_outcome_checks() -> None:
    check = {
        "code": "TOTAL_WORKLOAD_REDUCED", "verdict": "REALIZED",
        "reason_code": "allocated_below_available",
        "evidence_refs": [{"kind": "PLAN_RUN", "reference_id": "r1", "detail_code": "d"}],
    }
    with pytest.raises(ValidationError):
        InterventionEvaluation(
            evaluation_id="inteval_x", intervention_id="intv_x", user_id=USER, goal_id="goal_1",
            as_of=AS_OF.isoformat(), observation_status="COMPLETE", execution_signal="COMPLETED",
            plan_fidelity="MATCHED", verdict="EFFECTIVE", outcome_checks=[check, dict(check)],
            confidence=1.0, data_quality="verified",
        )


def test_outcome_codes_fall_back_to_the_strategy_when_the_row_is_empty() -> None:
    """记录里没有固化 expected_outcomes 时回落到策略声明，顺序稳定且不重复。"""
    strategy = _strategy(
        "WORKLOAD_REDUCTION",
        expected_outcomes=["TOTAL_WORKLOAD_REDUCED", "TOTAL_WORKLOAD_REDUCED", "ITEM_COUNT_REDUCED"],
    )
    intervention = _intervention(strategy)
    empty_row = AdaptiveInterventionRow(
        **{**intervention.__dict__, "expected_outcomes_json": "[]"}
    )
    evaluation = InterventionOutcomeEvaluator().evaluate(
        intervention=empty_row,
        observation=_observation(items=[_item("i1", "TASK_FOCUS", 20)]),
        as_of=AS_OF,
    ).evaluation
    assert [check.code for check in evaluation.outcome_checks] == [
        "TOTAL_WORKLOAD_REDUCED", "ITEM_COUNT_REDUCED",
    ]

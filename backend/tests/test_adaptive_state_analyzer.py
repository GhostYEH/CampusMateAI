"""StudentStateAnalyzer —— 状态分析层的确定性、可解释性与安全性约束。"""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from adaptive_intervention_helpers import (
    AS_OF,
    USER_SCOPE_ID,
    GoalStub,
    analyze_scenario,
    scenario_a,
    scenario_b,
    scenario_c,
    snapshot,
    ProjectionStub,
)
from app.schemas.adaptive_intervention import (
    INSUFFICIENT_EVIDENCE_CONFIDENCE_CEILING,
    ReasonCode,
    StateEvidenceRef,
    StudentStateAssessment,
)
from app.services.adaptive_agent.state_analyzer import StudentStateAnalyzer


def test_different_states_produce_different_problem_types() -> None:
    a = analyze_scenario("a")
    b = analyze_scenario("b")
    assert "WORKLOAD_PRESSURE_HIGH" in a.problem_types
    assert "EXECUTION_CONSISTENCY_LOW" in a.problem_types
    assert "KNOWLEDGE_FOUNDATION_WEAK" in a.problem_types
    assert a.problem_types != b.problem_types
    assert "READY_FOR_CHALLENGE" in b.problem_types
    assert "EXECUTION_CONSISTENCY_HIGH" in b.strengths
    assert "KNOWLEDGE_MASTERY_RELATIVELY_STRONG" in b.strengths


def test_stale_and_partial_snapshots_lower_confidence() -> None:
    verified = analyze_scenario("b")
    core, academic, world, goal = scenario_b()
    degraded = StudentStateAnalyzer().analyze(
        user_id=USER_SCOPE_ID, as_of=AS_OF,
        core=ProjectionStub(core.run_id, [
            snapshot(core.run_id, "task_workload", {"pending_task_count": 9}, "stale", index=1),
        ]),
        academic=ProjectionStub(academic.run_id, [
            snapshot(academic.run_id, s.state_type, s.value, "partial", index=i + 2)
            for i, s in enumerate(academic.snapshots)
        ]),
        world=ProjectionStub(world.run_id, [
            snapshot(world.run_id, s.state_type, s.value, "partial", index=i + 4)
            for i, s in enumerate(world.snapshots)
        ]),
        goal=goal,
    )
    assert degraded.overall_confidence < verified.overall_confidence
    assert degraded.data_quality in {"stale", "partial"}
    assert "data_quality_degraded" in degraded.warning_codes
    assert any(signal.code == "DATA_QUALITY_DEGRADED" for signal in degraded.risk_signals)


def test_unavailable_is_not_treated_as_zero() -> None:
    assessment = analyze_scenario("c")
    assert assessment.data_quality == "unavailable"
    assert assessment.problem_types == ["INSUFFICIENT_EVIDENCE"]
    assert assessment.overall_confidence <= INSUFFICIENT_EVIDENCE_CONFIDENCE_CEILING
    assert "evidence_insufficient" in assessment.reason_codes["INSUFFICIENT_EVIDENCE"]
    assert "state_unavailable" in assessment.reason_codes["INSUFFICIENT_EVIDENCE"]
    # 缺失的状态特征保持 None，绝不落成 0 —— 否则策略层会把"没数据"读成"低压力"。
    for key in (
        "workload_pressure_band", "upcoming_task_count", "execution_consistency_ratio",
        "knowledge_own_mastery_rate", "knowledge_mastery_gap_vs_class", "rhythm_stability",
    ):
        assert assessment.state_features[key] is None, key
    # 不能因为"没数据"就断言知识薄弱或已准备好挑战。
    assert "KNOWLEDGE_FOUNDATION_WEAK" not in assessment.problem_types
    assert "READY_FOR_CHALLENGE" not in assessment.problem_types
    assert "EXECUTION_CONSISTENCY_LOW" not in assessment.problem_types


def test_execution_no_plan_is_evidence_gap_not_low_consistency() -> None:
    """没有任何可执行观测时，"no_plan" 是证据不足，不是执行差。"""
    world = ProjectionStub("lrun_np", [
        snapshot("lrun_np", "execution_consistency", {
            "planned_task_count": 0, "executed_task_count": 0,
            "consistency_ratio": 0.0, "consistency_band": "no_plan", "data_completeness": "verified",
        }, "verified", index=1),
        snapshot("lrun_np", "workload_pressure", {
            "pressure_band": "LOW", "task_count": 0, "exam_count": 0, "data_completeness": "verified",
        }, "verified", index=2),
    ])
    assessment = StudentStateAnalyzer().analyze(
        user_id=USER_SCOPE_ID, as_of=AS_OF, world=world, goal=None,
    )
    assert "EXECUTION_CONSISTENCY_LOW" not in assessment.problem_types
    assert "execution_baseline_missing" in assessment.warning_codes


def test_every_finding_has_reason_codes_and_evidence_refs() -> None:
    allowed_reasons = set(ReasonCode.__args__)  # type: ignore[attr-defined]
    for letter in ("a", "b", "c"):
        assessment = analyze_scenario(letter)
        refs_by_code: dict[str, int] = {}
        for ref in assessment.evidence_refs:
            refs_by_code[ref.code] = refs_by_code.get(ref.code, 0) + 1
        for code in [*assessment.problem_types, *assessment.strengths]:
            assert assessment.reason_codes.get(code), f"{letter}:{code} 缺少 reason code"
            assert refs_by_code.get(code), f"{letter}:{code} 缺少 evidence ref"
            assert set(assessment.reason_codes[code]) <= allowed_reasons
        for signal in assessment.risk_signals:
            assert signal.reason_codes and signal.evidence_refs


def test_evidence_refs_are_safe_references_only() -> None:
    assessment = analyze_scenario("a")
    assert assessment.evidence_refs
    for ref in assessment.evidence_refs:
        assert ref.projection_kind in {"CORE", "ACADEMIC", "WORLD", "FORECAST", "GOAL"}
        if ref.scope_type == "USER":
            # USER 级快照的 scope_id 就是内部 user_id，绝不能落进任何可序列化结果。
            assert ref.scope_id is None
    # 顶层 user_id 是服务端内部编排字段（按用户隔离用），不属于证据引用；
    # 真正需要保证的是"证据引用里不出现内部 user_id"。
    refs_payload = json.dumps(
        [ref.model_dump(mode="json") for ref in assessment.evidence_refs], ensure_ascii=False
    )
    assert USER_SCOPE_ID not in refs_payload
    for signal in assessment.risk_signals:
        signal_payload = json.dumps(
            [ref.model_dump(mode="json") for ref in signal.evidence_refs], ensure_ascii=False
        )
        assert USER_SCOPE_ID not in signal_payload


def test_single_low_grade_does_not_become_ability_claim() -> None:
    """只有成绩观测时，不能推断知识薄弱，更不能推断能力或心理状态。"""
    academic = ProjectionStub("lrun_grade", [
        snapshot("lrun_grade", "grade_observation", {
            "observed_grade_count": 1, "score_band_distribution": {"0_59": 1},
            "has_observed_grades": True, "data_completeness": "verified",
        }, "verified", index=1),
    ])
    assessment = StudentStateAnalyzer().analyze(
        user_id=USER_SCOPE_ID, as_of=AS_OF, academic=academic, goal=None,
    )
    assert "KNOWLEDGE_FOUNDATION_WEAK" not in assessment.problem_types
    assert "knowledge_evidence_missing" in assessment.warning_codes
    # 枚举里也不存在任何人格/智力/心理类结论码。
    for code in assessment.problem_types:
        for forbidden in ("ABILITY", "INTELLIGENCE", "MOTIVATION", "PERSONALITY", "DEPRESSION", "ANXIETY"):
            assert forbidden not in code


def test_analysis_is_deterministic_for_identical_input() -> None:
    first = analyze_scenario("a")
    second = analyze_scenario("a")
    assert first.assessment_id == second.assessment_id
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_forecasts_are_optional_enhancement() -> None:
    """投影压力不可用时，预测可以补上压力信号；没有预测时该特征必须是 None 而不是 LOW。"""
    core, academic, _world, goal = scenario_a()
    degraded_world = ProjectionStub("lrun_fc_world", [
        snapshot("lrun_fc_world", "workload_pressure", {
            "pressure_band": None, "task_count": 0, "exam_count": 0,
            "data_completeness": "unavailable",
        }, "unavailable", index=1),
    ])

    class _Forecast:
        forecast_type = "UPCOMING_WORKLOAD"
        data_quality = "verified"
        confidence = 0.8

        class value:  # noqa: N801 - 模拟 ForecastOut.value
            @staticmethod
            def model_dump(mode: str = "json") -> dict:
                return {"pressure_band": "VERY_HIGH"}

    without = StudentStateAnalyzer().analyze(
        user_id=USER_SCOPE_ID, as_of=AS_OF, core=core, academic=academic, world=degraded_world, goal=goal,
    )
    with_forecast = StudentStateAnalyzer().analyze(
        user_id=USER_SCOPE_ID, as_of=AS_OF, core=core, academic=academic, world=degraded_world, goal=goal,
        forecasts=[_Forecast()],
    )
    assert without.state_features["forecast_workload_pressure_band"] is None
    assert without.state_features["workload_pressure_band"] is None
    assert "WORKLOAD_PRESSURE_HIGH" not in without.problem_types
    assert with_forecast.state_features["forecast_workload_pressure_band"] == "VERY_HIGH"
    assert "WORKLOAD_PRESSURE_HIGH" in with_forecast.problem_types
    assert any(ref.projection_kind == "FORECAST" for ref in with_forecast.evidence_refs)


def test_schema_rejects_insufficient_evidence_with_high_confidence() -> None:
    ref = StateEvidenceRef(code="INSUFFICIENT_EVIDENCE", projection_kind="CORE", data_quality="unavailable")
    with pytest.raises(ValidationError):
        StudentStateAssessment(
            assessment_id="assa_x", user_id="u1", goal_id=None, as_of=AS_OF.isoformat(),
            problem_types=["INSUFFICIENT_EVIDENCE"],
            state_features={}, overall_confidence=0.9, data_quality="unavailable",
            evidence_refs=[ref], reason_codes={"INSUFFICIENT_EVIDENCE": ["evidence_insufficient"]},
        )


def test_schema_rejects_finding_without_reason_or_evidence() -> None:
    with pytest.raises(ValidationError):
        StudentStateAssessment(
            assessment_id="assa_x", user_id="u1", goal_id=None, as_of=AS_OF.isoformat(),
            problem_types=["WORKLOAD_PRESSURE_HIGH"], state_features={},
            overall_confidence=0.8, data_quality="verified", evidence_refs=[],
            reason_codes={"WORKLOAD_PRESSURE_HIGH": ["workload_pressure_high"]},
        )
    with pytest.raises(ValidationError):
        StudentStateAssessment(
            assessment_id="assa_x", user_id="u1", goal_id=None, as_of=AS_OF.isoformat(),
            problem_types=["WORKLOAD_PRESSURE_HIGH"], state_features={},
            overall_confidence=0.8, data_quality="verified",
            evidence_refs=[StateEvidenceRef(code="WORKLOAD_PRESSURE_HIGH", projection_kind="WORLD")],
            reason_codes={},
        )


def test_goal_facts_participate_in_assessment() -> None:
    core, academic, world, _ = scenario_a()
    stalled = StudentStateAnalyzer().analyze(
        user_id=USER_SCOPE_ID, as_of=AS_OF, core=core, academic=academic, world=world,
        goal=GoalStub(progress_percent=10.0, target_date=(AS_OF.date()).isoformat()),
    )
    on_track = StudentStateAnalyzer().analyze(
        user_id=USER_SCOPE_ID, as_of=AS_OF, core=core, academic=academic, world=world,
        goal=GoalStub(progress_percent=90.0, target_date=(AS_OF.date()).isoformat()),
    )
    assert "GOAL_PROGRESS_STALLED" in stalled.problem_types
    assert "goal_deadline_near" in stalled.reason_codes["GOAL_PROGRESS_STALLED"]
    assert "GOAL_PROGRESS_ON_TRACK" in on_track.strengths
    assert stalled.state_features["goal_progress_percent"] == 10.0

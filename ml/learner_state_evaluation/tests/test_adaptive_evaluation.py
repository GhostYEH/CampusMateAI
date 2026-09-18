from __future__ import annotations

import json
from pathlib import Path

import pytest

from learner_state_evaluation.adaptive_evaluation.adapter import EvaluationMode
from learner_state_evaluation.adaptive_evaluation.dataset import (
    DatasetValidationError,
    load_evaluation_dataset,
)
from learner_state_evaluation.adaptive_evaluation.experiment import (
    AssignmentPolicy,
    ExperimentRegistry,
    power_analysis,
)
from learner_state_evaluation.adaptive_evaluation.manifest import build_manifest
from learner_state_evaluation.adaptive_evaluation.metrics import (
    evaluate_confidence_calibration,
    evaluate_policy,
    evaluate_state_model,
)
from learner_state_evaluation.adaptive_evaluation.replay import ReplayEvaluator
from learner_state_evaluation.adaptive_evaluation.runner import run_evaluation


FIXTURE = Path(__file__).parents[1] / "datasets" / "adaptive_closed_loop_v1.json"


def test_dataset_has_required_synthetic_scenarios_and_no_personal_text():
    dataset = load_evaluation_dataset(FIXTURE)
    assert dataset.data_source_type == "synthetic"
    assert len(dataset.scenarios) >= 20
    assert {scenario.scenario_id for scenario in dataset.scenarios} >= {
        "knowledge_weak_low_completion_high_pressure",
        "knowledge_weak_stable_execution",
        "goal_completed",
        "continuous_anomaly_waits",
    }
    serialized = json.dumps(dataset.to_dict(), ensure_ascii=False).lower()
    assert "username" not in serialized
    assert "chat" not in serialized
    assert "password" not in serialized


def test_invalid_source_label_and_missing_versions_fail(tmp_path):
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    value["data_source_type"] = "real_study"
    value.pop("projection_version")
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(DatasetValidationError):
        load_evaluation_dataset(path)


def test_four_modes_share_one_input_and_have_capability_matrix():
    dataset = load_evaluation_dataset(FIXTURE)
    report = run_evaluation(dataset, modes=list(EvaluationMode), seed=20260918)
    assert set(report.mode_results) == {mode.value for mode in EvaluationMode}
    assert {row["input_digest"] for row in report.decision_records} == {report.input_digest}
    assert report.capability_matrix["STATIC_PLAN"]["uses_dynamic_state"] is False
    assert report.capability_matrix["PROFILE_ONLY"]["uses_dynamic_state"] is False
    assert report.capability_matrix["STATE_DRIVEN"]["uses_dynamic_state"] is True
    assert report.capability_matrix["CLOSED_LOOP"]["uses_feedback"] is True


def test_static_and_profile_modes_ignore_dynamic_changes():
    dataset = load_evaluation_dataset(FIXTURE)
    first = dataset.scenario("knowledge_weak_stable_execution")
    changed = first.with_event_payload({"completion_rate": 0.05, "stress_risk": 0.95})
    first_report = run_evaluation(dataset.replace_scenarios([first]), modes=[EvaluationMode.STATIC_PLAN, EvaluationMode.PROFILE_ONLY], seed=7)
    changed_report = run_evaluation(dataset.replace_scenarios([changed]), modes=[EvaluationMode.STATIC_PLAN, EvaluationMode.PROFILE_ONLY], seed=7)
    for mode in (EvaluationMode.STATIC_PLAN.value, EvaluationMode.PROFILE_ONLY.value):
        assert first_report.mode_results[mode] == changed_report.mode_results[mode]


def test_state_driven_changes_strategy_but_does_not_replan():
    dataset = load_evaluation_dataset(FIXTURE)
    report = run_evaluation(dataset, modes=[EvaluationMode.STATE_DRIVEN], seed=11)
    weak = report.mode_results[EvaluationMode.STATE_DRIVEN.value]["knowledge_weak_stable_execution"]
    strong = report.mode_results[EvaluationMode.STATE_DRIVEN.value]["mastery_good_high_completion_low_pressure"]
    assert weak["strategy_code"] != strong["strategy_code"]
    assert weak["replan_decision"] is None


def test_closed_loop_replans_after_sustained_decline_and_waits_for_missing_evidence():
    dataset = load_evaluation_dataset(FIXTURE)
    report = run_evaluation(dataset, modes=[EvaluationMode.CLOSED_LOOP], seed=19)
    decline = report.mode_results[EvaluationMode.CLOSED_LOOP.value]["state_continuously_declining"]
    missing = report.mode_results[EvaluationMode.CLOSED_LOOP.value]["data_unavailable"]
    assert decline["replan_decision"] == "REPLAN"
    assert missing["replan_decision"] == "WAIT_FOR_EVIDENCE"


def test_safety_rules_cover_pressure_goal_end_and_unknown_strategy():
    dataset = load_evaluation_dataset(FIXTURE)
    report = run_evaluation(dataset, modes=[EvaluationMode.CLOSED_LOOP], seed=23)
    high_pressure = report.mode_results[EvaluationMode.CLOSED_LOOP.value]["knowledge_weak_low_completion_high_pressure"]
    completed = report.mode_results[EvaluationMode.CLOSED_LOOP.value]["goal_completed"]
    unknown = report.mode_results[EvaluationMode.CLOSED_LOOP.value]["unknown_strategy_guard"]
    assert high_pressure["strategy_code"] != "CHALLENGE_UPSHIFT"
    assert completed["replan_decision"] == "SUSPEND"
    assert "unknown_strategy" in unknown["warning_codes"]


def test_same_input_seed_and_versions_are_byte_deterministic():
    dataset = load_evaluation_dataset(FIXTURE)
    left = run_evaluation(dataset, modes=list(EvaluationMode), seed=20260918).to_json()
    right = run_evaluation(dataset, modes=list(EvaluationMode), seed=20260918).to_json()
    assert left == right


def test_replay_is_read_only_private_and_time_ordered():
    dataset = load_evaluation_dataset(FIXTURE)
    evaluator = ReplayEvaluator()
    result = evaluator.evaluate(dataset.scenario("duplicate_and_out_of_order_events"), mode=EvaluationMode.CLOSED_LOOP, seed=3)
    assert result.writes == []
    assert result.external_model_calls == 0
    assert result.created_task_ids == []
    assert result.event_ids == ["event-early", "event-late"]
    assert result.duplicate_event_count == 1
    assert result.future_event_excluded is True


def test_metrics_refuse_fake_calibration_without_labels():
    result = evaluate_confidence_calibration([{"confidence": 0.8}], labels=None)
    assert result["accuracy"] is None
    assert result["brier_score"] is None
    assert result["evidence_completeness"] == 1.0


def test_state_and_policy_metric_tables_have_required_fields():
    dataset = load_evaluation_dataset(FIXTURE)
    report = run_evaluation(dataset, modes=list(EvaluationMode), seed=29)
    state = evaluate_state_model(report)
    policy = evaluate_policy(report)
    assert {"dimension", "evidence_coverage", "verified", "partial", "stale", "unavailable", "mean_confidence"} <= set(state["table"][0])
    assert {"differentiation_rate", "state_strategy_consistency", "evidence_coverage", "determinism", "unsafe_decision_count"} <= set(policy)
    assert state["data_source_type"] == "synthetic"


def test_closed_loop_metrics_detect_a_b_a_oscillation():
    dataset = load_evaluation_dataset(FIXTURE)
    report = run_evaluation(dataset, modes=[EvaluationMode.CLOSED_LOOP], seed=31)
    assert report.metrics["closed_loop"]["oscillation_count"] >= 1
    assert report.metrics["closed_loop"]["duplicate_decision_count"] == 0


def test_manifest_and_result_hash_change_when_dataset_changes(tmp_path):
    dataset = load_evaluation_dataset(FIXTURE)
    report = run_evaluation(dataset, modes=[EvaluationMode.CLOSED_LOOP], seed=37)
    left = build_manifest(dataset, report, git_commit="test-commit", output_path=tmp_path / "result.json")
    changed = dataset.replace_scenarios([dataset.scenarios[0].with_description("changed")])
    changed_report = run_evaluation(changed, modes=[EvaluationMode.CLOSED_LOOP], seed=37)
    right = build_manifest(changed, changed_report, git_commit="test-commit", output_path=tmp_path / "changed.json")
    assert left["dataset_hash"] != right["dataset_hash"]
    assert left["result_hash"] != right["result_hash"]


def test_assignment_is_stable_opt_in_and_exit_stops_exposure():
    registry = ExperimentRegistry(enabled=True, policy=AssignmentPolicy(version="assignment-v1", salt="test-salt"))
    first = registry.assign("participant-hash-input")
    assert first.group == registry.assign("participant-hash-input").group
    registry.record_exposure(first.participant_id, "CLOSED_LOOP", "exposure-1")
    registry.exit(first.participant_id)
    assert registry.exposures(first.participant_id) == []
    registry.delete(first.participant_id)
    assert registry.get(first.participant_id) is None


def test_power_analysis_is_parameterized_and_not_a_fixed_claim():
    result = power_analysis(variance=1.5, effect_size=0.4, alpha=0.05, power=0.8, groups=3)
    assert result["total"] == result["per_group"] * 3
    assert "approximation" in result["note"]
    with pytest.raises(ValueError):
        power_analysis(variance=0, effect_size=0.4)


def test_cli_run_writes_machine_csv_and_short_markdown(tmp_path):
    from learner_state_evaluation.cli import run_adaptive_evaluation

    result = run_adaptive_evaluation(FIXTURE, tmp_path / "run", [mode.value for mode in EvaluationMode], 20260918)
    assert result["manifest"]["data_source_type"] == "synthetic"
    assert (tmp_path / "run" / "result.json").exists()
    assert (tmp_path / "run" / "metrics.csv").exists()
    assert "not evidence of educational" in (tmp_path / "run" / "summary.md").read_text(encoding="utf-8")

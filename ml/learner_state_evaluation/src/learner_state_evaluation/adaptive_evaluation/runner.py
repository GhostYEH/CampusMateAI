from __future__ import annotations

from typing import Iterable

from .adapter import EvaluationMode, EvaluationPolicyAdapter
from .metrics import evaluate_closed_loop, evaluate_policy, evaluate_state_model
from .models import EvaluationDataset, EvaluationReport, sha256_json


CAPABILITY_MATRIX = {
    "STATIC_PLAN": {"uses_dynamic_state": False, "uses_evidence": False, "personalized_strategy": False, "uses_feedback": False, "uses_auto_replan": False},
    "PROFILE_ONLY": {"uses_dynamic_state": False, "uses_evidence": False, "personalized_strategy": True, "uses_feedback": False, "uses_auto_replan": False},
    "STATE_DRIVEN": {"uses_dynamic_state": True, "uses_evidence": True, "personalized_strategy": True, "uses_feedback": False, "uses_auto_replan": False},
    "CLOSED_LOOP": {"uses_dynamic_state": True, "uses_evidence": True, "personalized_strategy": True, "uses_feedback": True, "uses_auto_replan": True},
}


def run_evaluation(dataset: EvaluationDataset, *, modes: Iterable[EvaluationMode], seed: int, adapter: EvaluationPolicyAdapter | None = None) -> EvaluationReport:
    selected = list(dict.fromkeys(EvaluationMode(mode) for mode in modes))
    if not selected:
        raise ValueError("at least one evaluation mode is required")
    adapter = adapter or EvaluationPolicyAdapter()
    mode_results: dict[str, dict[str, dict]] = {}
    records: list[dict] = []
    common_input_digest = sha256_json({"dataset_hash": dataset.dataset_hash, "seed": seed, "modes": [mode.value for mode in selected]})
    for mode in selected:
        rows: dict[str, dict] = {}
        for scenario in sorted(dataset.scenarios, key=lambda item: item.scenario_id):
            result = adapter.evaluate(scenario, mode, seed=seed)
            result["lineage"]["data_source_type"] = dataset.data_source_type
            rows[scenario.scenario_id] = result
            records.append({"scenario_id": scenario.scenario_id, "mode": mode.value, "input_digest": common_input_digest, "decision_input_digest": result["input_digest"], "strategy_code": result["strategy_code"], "replan_decision": result["replan_decision"], "data_source_type": dataset.data_source_type})
        mode_results[mode.value] = rows
    report = EvaluationReport(
        dataset_id=dataset.dataset_id, dataset_hash=dataset.dataset_hash, data_source_type=dataset.data_source_type,
        seed=seed, input_digest=common_input_digest,
        mode_results=mode_results, decision_records=records, metrics={}, capability_matrix={mode: CAPABILITY_MATRIX[mode] for mode in mode_results},
        evaluator_version=dataset.evaluator_version, policy_version=dataset.policy_version, projection_version=dataset.projection_version,
    )
    state_metrics = evaluate_state_model(report)
    policy_metrics = evaluate_policy(report)
    loop_metrics = evaluate_closed_loop(report)
    metrics = {
        "state_model": state_metrics, "policy": policy_metrics, "closed_loop": loop_metrics,
        "tables": {
            "table1_state_coverage": state_metrics["table"],
            "table2_mode_capabilities": [{"mode": mode, "data_source_type": dataset.data_source_type, **capabilities} for mode, capabilities in report.capability_matrix.items()],
            "table3_strategy": {key: policy_metrics[key] for key in ("differentiation_rate", "state_strategy_consistency", "evidence_coverage", "determinism", "unsafe_decision_count")},
            "table4_closed_loop": {key: loop_metrics[key] for key in ("outcome_observability_rate", "WAIT_FOR_EVIDENCE_rate", "CONTINUE_rate", "REPLAN_rate", "duplicate_decision_count", "oscillation_count", "replan_recovery_success_rate", "average_replan_chain_depth")},
            "table5_ablation": [{"variant": variant, "data_source_type": dataset.data_source_type, "implemented": implemented} for variant, implemented in (("full_system", True), ("remove_confidence", True), ("remove_risk", True), ("remove_feedback", True), ("remove_replan", True))],
        },
    }
    report = EvaluationReport(**{**report.__dict__, "metrics": metrics})
    return report

from __future__ import annotations

from typing import Any, Iterable

from .adapter import AblationVariant, EvaluationMode, EvaluationPolicyAdapter
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
    # 消融与敏感性都必须**真跑**：这些数字直接进论文表格，不能是声明。
    closed_loop_selected = EvaluationMode.CLOSED_LOOP in selected
    ablation_rows = run_ablations(dataset, seed=seed, adapter=adapter) if closed_loop_selected else None
    sensitivity = measure_sensitivity(dataset, seed=seed, adapter=adapter) if closed_loop_selected else None

    state_metrics = evaluate_state_model(report, dataset=dataset, sensitivity=sensitivity)
    policy_metrics = evaluate_policy(report, dataset=dataset, ablation_results=ablation_rows)
    loop_metrics = evaluate_closed_loop(report)
    metrics = {
        "state_model": state_metrics, "policy": policy_metrics, "closed_loop": loop_metrics,
        "tables": {
            "table1_state_coverage": state_metrics["table"],
            "table2_mode_capabilities": [{"mode": mode, "data_source_type": dataset.data_source_type, **capabilities} for mode, capabilities in report.capability_matrix.items()],
            "table3_strategy": {key: policy_metrics[key] for key in ("differentiation_rate", "state_strategy_consistency", "evidence_coverage", "determinism", "unsafe_decision_count")},
            "table4_closed_loop": {key: loop_metrics[key] for key in ("outcome_observability_rate", "WAIT_FOR_EVIDENCE_rate", "CONTINUE_rate", "REPLAN_rate", "duplicate_decision_count", "oscillation_count", "replan_recovery_success_rate", "average_replan_chain_depth")},
            # 以前这里是 `implemented: True` 的字面量列表 —— 声明了从未运行过的实验。
            # 现在每个变体都真的重跑过，decision_changed_count 是实测差异。
            "table5_ablation": ablation_rows or [],
        },
        "unmeasured": {**state_metrics["unmeasured"], **policy_metrics["unmeasured"], **loop_metrics["unmeasured"]},
    }
    report = EvaluationReport(**{**report.__dict__, "metrics": metrics})
    return report


def run_ablations(dataset: EvaluationDataset, *, seed: int, adapter: EvaluationPolicyAdapter) -> list[dict[str, Any]]:
    """逐变体重跑闭环，并给出与 full_system 的**实测**差异。

    一个变体若对任何场景都没有产生差异，含义是"该能力在这份数据上没有可测影响" ——
    这本身就是结论，应当如实报出，而不是补一句 implemented=True 糊过去。
    """
    scenarios = sorted(dataset.scenarios, key=lambda item: item.scenario_id)
    baseline = {
        scenario.scenario_id: adapter.evaluate(scenario, EvaluationMode.CLOSED_LOOP, seed=seed, ablation=AblationVariant.FULL_SYSTEM)
        for scenario in scenarios
    }
    rows: list[dict[str, Any]] = []
    for variant in AblationVariant:
        decision_changed = 0
        strategy_changed = 0
        chain_changed = 0
        replan_count = 0
        for scenario in scenarios:
            result = adapter.evaluate(scenario, EvaluationMode.CLOSED_LOOP, seed=seed, ablation=variant)
            reference = baseline[scenario.scenario_id]
            if result["replan_decision"] != reference["replan_decision"]:
                decision_changed += 1
            if result["strategy_code"] != reference["strategy_code"]:
                strategy_changed += 1
            # 反馈影响的是**后继策略**（decision_chain），不是当轮决策。
            # 只比 replan_decision 会把 remove_feedback 误判成"无效"。
            if result.get("decision_chain") != reference.get("decision_chain"):
                chain_changed += 1
            if result["replan_decision"] == "REPLAN":
                replan_count += 1
        rows.append({
            "variant": variant.value,
            "executed": True,
            "scenario_count": len(scenarios),
            "decision_changed_count": decision_changed,
            "strategy_changed_count": strategy_changed,
            "chain_changed_count": chain_changed,
            "changed_vs_full_system": decision_changed > 0 or strategy_changed > 0 or chain_changed > 0,
            "replan_decision_count": replan_count,
            "data_source_type": dataset.data_source_type,
            "seed": seed,
        })
    return rows


def measure_sensitivity(dataset: EvaluationDataset, *, seed: int, adapter: EvaluationPolicyAdapter) -> dict[str, Any]:
    """单因子敏感性：只改一个状态维度，看策略/决策是否真的随之改变。"""
    perturbation = {"stress_risk": 0.95}
    tested = 0
    changed = 0
    for scenario in sorted(dataset.scenarios, key=lambda item: item.scenario_id):
        if not scenario.event_sequence:
            continue
        baseline = adapter.evaluate(scenario, EvaluationMode.CLOSED_LOOP, seed=seed)
        perturbed = adapter.evaluate(scenario.with_event_payload(perturbation), EvaluationMode.CLOSED_LOOP, seed=seed)
        tested += 1
        if (perturbed["strategy_code"], perturbed["replan_decision"]) != (baseline["strategy_code"], baseline["replan_decision"]):
            changed += 1
    return {
        "tested": tested > 0,
        "tested_scenario_count": tested,
        "perturbation": "stress_risk->0.95",
        "changed_ratio": round(changed / tested, 6) if tested else None,
        "changed_count": changed,
    }

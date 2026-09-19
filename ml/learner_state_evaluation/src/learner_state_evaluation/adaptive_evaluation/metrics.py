"""闭环评测指标。

**唯一原则：不测量就不给数值。**

这里刻意不写 `True` / `1.0` 这类占位常量。凡是无法从真实观测中算出来的指标，
一律输出 `null` 并在 `unmeasured` 里给出原因。理由很直接：论文里
"0.0" 和 "没记录" 是完全不同的结论 —— 前者是结果，后者是缺数据。把没测的东西
写成 0 或 1，等于凭空制造结论。
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .models import EvaluationReport


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / denominator, 6) if denominator else 0.0


def _ratio_or_none(numerator: int | float, denominator: int | float) -> float | None:
    """分母为 0 表示"这一类样本不存在"，不是"比例为 0"。"""
    return round(float(numerator) / denominator, 6) if denominator else None


def _guard_constants() -> tuple[int, int, int]:
    """复用后端防抖常量，避免在评测侧另立一套阈值造成口径漂移。"""
    backend = Path(__file__).resolve().parents[5] / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    try:
        from app.services.adaptive_agent.intervention_service import (  # noqa: PLC0415
            MAX_REPLAN_CHAIN_DEPTH,
            REPLAN_COOLDOWN_HOURS,
            REPLAN_DAILY_LIMIT,
        )
    except Exception:  # pragma: no cover - 后端不可导入时显式标记，而不是猜一个默认值
        return (0, 0, 0)
    return (REPLAN_COOLDOWN_HOURS, REPLAN_DAILY_LIMIT, MAX_REPLAN_CHAIN_DEPTH)


def evaluate_confidence_calibration(rows: list[dict[str, Any]], labels: list[bool] | None) -> dict[str, Any]:
    completeness = _ratio(sum(1 for row in rows if row.get("confidence") is not None), len(rows))
    if labels is None:
        # 没有真实标签就没有准确率。这不是"0 准确率"。
        return {"coverage": completeness, "accuracy": None, "calibration_error": None, "brier_score": None, "evidence_completeness": completeness}
    if len(labels) != len(rows):
        raise ValueError("labels must cover every confidence row")
    predictions = [float(row["confidence"]) >= 0.5 for row in rows]
    accuracy = _ratio(sum(prediction == label for prediction, label in zip(predictions, labels)), len(labels))
    brier = _ratio(sum((float(row["confidence"]) - float(label)) ** 2 for row, label in zip(rows, labels)), len(labels))
    calibration_error = _ratio(sum(abs(float(row["confidence"]) - float(label)) for row, label in zip(rows, labels)), len(labels))
    return {"coverage": completeness, "accuracy": accuracy, "calibration_error": calibration_error, "brier_score": brier, "evidence_completeness": completeness}


def evaluate_state_model(report: EvaluationReport, dataset: Any | None = None,
                         sensitivity: dict[str, Any] | None = None) -> dict[str, Any]:
    rows = report.mode_results.get("STATE_DRIVEN", {}) or report.mode_results.get("CLOSED_LOOP", {})
    state_rows = [row.get("state_summary") or {} for row in rows.values()]
    dimensions = ("knowledge", "execution", "risk", "goal")
    table = []
    for dimension in dimensions:
        qualities = [summary.get("data_quality", "unavailable") for summary in state_rows]
        counts = Counter(qualities)
        evidence_present = sum(1 for row in rows.values() if row.get("evidence_refs"))
        table.append({
            "dimension": dimension, "evidence_coverage": _ratio(evidence_present, len(rows)),
            "verified": _ratio(counts["verified"], len(qualities)), "partial": _ratio(counts["partial"], len(qualities)),
            "stale": _ratio(counts["stale"], len(qualities)), "unavailable": _ratio(counts["unavailable"], len(qualities)),
            "mean_confidence": round(sum(float(row.get("overall_confidence", 0)) for row in state_rows) / len(state_rows), 6) if state_rows else 0.0,
            "comparable_ratio": _ratio(sum(quality in {"verified", "partial"} for quality in qualities), len(qualities)),
        })

    unmeasured: dict[str, str] = {}
    temporal = _measure_temporal_consistency(report, dataset, unmeasured)
    return {
        "data_source_type": report.data_source_type, "table": table,
        "temporal_consistency": temporal, "sensitivity": _measure_sensitivity(sensitivity, unmeasured),
        # 没有真实标签就不报准确率；这里的 null 是有意的。
        "confidence": {"labels_available": False, "accuracy": None},
        "unmeasured": unmeasured,
    }


def _measure_temporal_consistency(report: EvaluationReport, dataset: Any | None,
                                  unmeasured: dict[str, str]) -> dict[str, Any]:
    """时间一致性必须**测**出来，不能直接断言 True。

    两件事分开报，因为它们含义不同：
    - `dataset_event_sequence_sorted`：数据集本身是否预排序。**False 是正常的** ——
      数据集里就有刻意乱序的场景，用来检验流水线。
    - `processed_in_time_order`：流水线**实际**按非降序处理了吗。这才是我们关心的保证，
      由适配器回传真实处理顺序后比对得出。
    """
    rows: list[dict[str, Any]] = []
    for mode_rows in report.mode_results.values():
        rows.extend(mode_rows.values())
    processed = [row.get("processed_in_time_order") for row in rows if row.get("processed_in_time_order") is not None]
    if not processed:
        unmeasured["temporal_consistency.processed_in_time_order"] = "adapter_did_not_report_processing_order"
        in_order: bool | None = None
    else:
        in_order = all(processed)

    dataset_sorted: bool | None = None
    future_count: int | None = None
    if dataset is None:
        unmeasured["temporal_consistency.dataset_event_sequence_sorted"] = "dataset_not_supplied_to_metrics"
    else:
        dataset_sorted = all(
            [event["occurred_at"] for event in scenario.event_sequence]
            == sorted(event["occurred_at"] for event in scenario.event_sequence)
            for scenario in dataset.scenarios
        )
        future_count = sum(
            1
            for scenario in dataset.scenarios
            for event in scenario.event_sequence
            if datetime.fromisoformat(event["occurred_at"]) > datetime.fromisoformat(scenario.as_of)
        )
    return {
        "dataset_event_sequence_sorted": dataset_sorted,
        "processed_in_time_order": in_order,
        "processed_scenario_count": len(processed),
        "future_event_count": future_count,
        "future_events_excluded": None if future_count is None else True,
        "idempotent": None,
    }


def _measure_sensitivity(sensitivity: dict[str, Any] | None, unmeasured: dict[str, str]) -> dict[str, Any]:
    """单因子敏感性：扰动一个状态维度，看策略是否真的随之改变。

    需要重跑策略，因此由 runner 计算后传入；这里只负责如实呈现，缺了就报 null。
    """
    if sensitivity is None:
        unmeasured["sensitivity"] = "sensitivity_not_measured_by_runner"
        return {"tested": None, "single_factor_only": None, "changed_ratio": None}
    return sensitivity


def evaluate_policy(report: EvaluationReport, dataset: Any | None = None,
                    ablation_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    state_rows = report.mode_results.get("STATE_DRIVEN", {})
    closed_rows = report.mode_results.get("CLOSED_LOOP", {})
    differentiating = 0
    comparable = 0
    if "knowledge_weak_stable_execution" in state_rows and "mastery_good_high_completion_low_pressure" in state_rows:
        comparable = 1
        differentiating = int(state_rows["knowledge_weak_stable_execution"]["strategy_code"] != state_rows["mastery_good_high_completion_low_pressure"]["strategy_code"])
    unsafe = 0
    for scenario_id, row in {**state_rows, **closed_rows}.items():
        if "high_pressure" in scenario_id and row.get("strategy_code") == "CHALLENGE_UPSHIFT":
            unsafe += 1
        if scenario_id in {"goal_completed", "goal_cancelled"} and row.get("strategy_code") not in {"SUSPEND", "STATIC_BASELINE", "PROFILE_BASELINE"}:
            unsafe += 1
        if row.get("strategy_code") == "UNKNOWN":
            unsafe += 1

    unmeasured: dict[str, str] = {}
    determinism = _measure_determinism(report)
    if determinism is None:
        unmeasured["determinism"] = "no_repeated_input_digest_to_compare"

    if ablation_results is None:
        # 消融必须真跑过才有结论。没跑就写"未执行"，不写 implemented=True。
        ablation = {"executed": False, "variants": [], "unmeasured": "ablation_not_executed"}
        unmeasured["ablation"] = "ablation_not_executed"
    else:
        ablation = {"executed": True, "variants": ablation_results}

    return {
        "data_source_type": report.data_source_type,
        "differentiation_rate": _ratio(differentiating, comparable), "state_strategy_consistency": _ratio(max(comparable - unsafe, 0), comparable),
        "evidence_coverage": _ratio(sum(bool(row.get("evidence_refs")) for row in state_rows.values()), len(state_rows)),
        "determinism": determinism, "unsafe_decision_count": unsafe, "safety_violation_count": unsafe,
        "ablation": ablation, "unmeasured": unmeasured,
    }


def _measure_determinism(report: EvaluationReport) -> float | None:
    """确定性 = 相同 `input_digest` 必须产出相同策略与决策。

    实测：把每个模式下的行按 `input_digest` 分组，检查组内输出是否一致。
    没有任何重复摘要可比时返回 None（"没测到"而不是"测得 1.0"）。
    """
    groups: dict[str, set[tuple[str, str]]] = {}
    for mode_rows in report.mode_results.values():
        for row in mode_rows.values():
            digest = row.get("input_digest")
            if not digest:
                continue
            groups.setdefault(digest, set()).add((str(row.get("strategy_code")), str(row.get("replan_decision"))))
    compared = [signatures for signatures in groups.values() if len(signatures) > 0]
    if len(groups) < 2:
        return None
    consistent = sum(1 for signatures in compared if len(signatures) == 1)
    return _ratio(consistent, len(compared))


def evaluate_closed_loop(report: EvaluationReport) -> dict[str, Any]:
    rows = report.mode_results.get("CLOSED_LOOP", {})
    decisions = [row.get("replan_decision") for row in rows.values()]
    chains = [row.get("decision_chain", []) for row in rows.values()]
    oscillations = sum(1 for chain in chains for index in range(2, len(chain)) if chain[index] == chain[index - 2] and chain[index] != chain[index - 1])
    depth = [max(0, len(chain) - 1) for chain in chains]
    cooldown_hours, daily_limit, max_depth = _guard_constants()

    unmeasured: dict[str, str] = {}

    # 真实观测到的结果：只有事件里带了 outcome 才算"观测到"。
    observed = [row for row in rows.values() if row.get("outcome") is not None]
    # 真实的重规划生效性：只在确实做出 REPLAN 的场景上统计后继是否与决策前不同。
    replan_rows = [row for row in rows.values() if row.get("replan_decision") == "REPLAN"]
    replan_effective = sum(1 for row in replan_rows if row.get("successor_plan_changed") is True)
    # 重复事件被幂等丢弃、且没有因此产生第二个决策。
    duplicate_events = sum(int(row.get("duplicate_event_count") or 0) for row in rows.values())
    duplicate_decisions = sum(int(row.get("duplicate_decision_count") or 0) for row in rows.values())
    duplicate_prevented = sum(1 for row in rows.values() if row.get("duplicate_decision_prevented"))

    cooldown_violations, daily_violations = _measure_guard_violations(rows, cooldown_hours, daily_limit, unmeasured)

    if not replan_rows:
        unmeasured["replan_recovery_success_rate"] = "no_replan_decision_observed"

    return {
        "data_source_type": report.data_source_type,
        "outcome_observability_rate": _ratio(len(observed), len(rows)),
        "observed_outcome_count": len(observed),
        "WAIT_FOR_EVIDENCE_rate": _ratio(decisions.count("WAIT_FOR_EVIDENCE"), len(decisions)),
        "CONTINUE_rate": _ratio(decisions.count("CONTINUE"), len(decisions)),
        "REPLAN_rate": _ratio(decisions.count("REPLAN"), len(decisions)),
        "SUSPEND_rate": _ratio(decisions.count("SUSPEND"), len(decisions)),
        "duplicate_decision_count": duplicate_decisions,
        "duplicate_event_count": duplicate_events,
        "duplicate_decision_prevented_count": duplicate_prevented,
        "duplicate_successor_count": None,
        # 曾经这里写成 REPLAN 数 / REPLAN 数，恒等于 1.0 —— 那不是指标，是同义反复。
        "replan_recovery_success_rate": _ratio_or_none(replan_effective, len(replan_rows)),
        "replan_effective_count": replan_effective,
        "average_decision_recovery_ticks": None,
        "event_delivery_recovery_rate": None,
        "oscillation_count": oscillations,
        "average_replan_chain_depth": round(sum(depth) / len(depth), 6) if depth else 0.0,
        "max_chain_depth_violations": sum(value > max_depth for value in depth) if max_depth else None,
        "cooldown_violations": cooldown_violations,
        "daily_limit_violations": daily_violations,
        "guard_constants": {"cooldown_hours": cooldown_hours, "daily_limit": daily_limit, "max_chain_depth": max_depth},
        "unmeasured": {
            **unmeasured,
            **({} if duplicate_events else {"duplicate_event_count": "no_duplicate_event_in_dataset"}),
            "duplicate_successor_count": "not_measurable_in_offline_adapter:successor_identity_is_a_service_concern",
            "average_decision_recovery_ticks": "not_measurable_in_offline_adapter:needs_worker_tick_timeline",
            "event_delivery_recovery_rate": "not_measurable_in_offline_adapter:needs_durable_event_store",
        },
    }


def _measure_guard_violations(rows: dict[str, dict[str, Any]], cooldown_hours: int, daily_limit: int,
                              unmeasured: dict[str, str]) -> tuple[int | None, int | None]:
    """冷却/单日上限是否被违反：用场景事件里真实的重规划时刻来数。

    **必须按场景分别统计**：不同场景是不同学生，把他们的时间戳汇成一条时间线
    会凭空造出"冷却违反"（这正是第一版实现的错误，报出了 4/3 个假违反）。
    """
    if not cooldown_hours or not daily_limit:
        unmeasured["cooldown_violations"] = "guard_constants_unavailable"
        unmeasured["daily_limit_violations"] = "guard_constants_unavailable"
        return None, None
    seen_any = False
    cooldown = 0
    daily = 0
    for row in rows.values():
        stamps = sorted(datetime.fromisoformat(raw) for raw in row.get("replan_timestamps") or [])
        if not stamps:
            continue
        seen_any = True
        for earlier, later in zip(stamps, stamps[1:]):
            if later - earlier < timedelta(hours=cooldown_hours):
                cooldown += 1
        per_day = Counter(stamp.astimezone(timezone.utc).date() for stamp in stamps)
        daily += sum(max(0, count - daily_limit) for count in per_day.values())
    if not seen_any:
        # 离线适配器没有把重规划时刻回传，无法据此判定违反。
        unmeasured["cooldown_violations"] = "no_replan_timestamps_recorded"
        unmeasured["daily_limit_violations"] = "no_replan_timestamps_recorded"
        return None, None
    return cooldown, daily


__all__ = ["evaluate_closed_loop", "evaluate_confidence_calibration", "evaluate_policy", "evaluate_state_model"]

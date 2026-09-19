"""指标真实性契约。

这套测试存在的唯一目的：**防止"没测的东西被写成数值"重新出现。**

背景：`metrics.py` 曾经把消融写成 `implemented: True` 的常量列表，
把 `determinism` 写成 `1.0`、`duplicate_successor_count` 写成 `0`，
而 `replan_recovery_success_rate` 是 `REPLAN 数 / REPLAN 数` —— 恒等于 1.0 的同义反复。
这些数字会直接进论文表格，所以必须有测试钉住"要么真测，要么显式为空"。
"""
from __future__ import annotations

import json
from pathlib import Path

from learner_state_evaluation.adaptive_evaluation.adapter import AblationVariant, EvaluationMode
from learner_state_evaluation.adaptive_evaluation.dataset import load_evaluation_dataset
from learner_state_evaluation.adaptive_evaluation.runner import run_evaluation


FIXTURE = Path(__file__).parents[1] / "datasets" / "adaptive_closed_loop_v1.json"
SEED = 20260918

# 离线适配器结构上无法测量的指标：必须是 null + 原因，不能是 0 或 True。
NOT_MEASURABLE_OFFLINE = (
    "duplicate_successor_count",
    "average_decision_recovery_ticks",
    "event_delivery_recovery_rate",
)


def _report(modes=(EvaluationMode.CLOSED_LOOP,)):
    return run_evaluation(load_evaluation_dataset(FIXTURE), modes=list(modes), seed=SEED)


def test_ablation_table_is_produced_by_real_runs_not_by_a_constant():
    report = _report()
    rows = report.metrics["tables"]["table5_ablation"]
    assert rows, "消融表不能为空"
    assert {row["variant"] for row in rows} == {variant.value for variant in AblationVariant}
    for row in rows:
        # 旧实现写的是 implemented=True 的字面量；那个字段不允许再出现。
        assert "implemented" not in row
        assert row["executed"] is True
        assert row["scenario_count"] == len(load_evaluation_dataset(FIXTURE).scenarios)
        assert row["seed"] == SEED
        assert row["data_source_type"] == "synthetic"
    baseline = next(row for row in rows if row["variant"] == "full_system")
    assert baseline["changed_vs_full_system"] is False, "full_system 是基线，与自身比较必须无差异"


def test_every_ablation_channel_is_independently_exercised():
    """每个消融都必须**真的**改变至少一个结果。

    任何一条变成 0，说明该能力在这份数据上不再可测 —— 要么数据集退化，
    要么开关没接到真实决策路径上。两种情况都必须立刻暴露，而不是静默通过。
    """
    rows = {row["variant"]: row for row in _report().metrics["tables"]["table5_ablation"]}
    for variant in AblationVariant:
        if variant is AblationVariant.FULL_SYSTEM:
            continue
        row = rows[variant.value]
        total = row["decision_changed_count"] + row["strategy_changed_count"] + row["chain_changed_count"]
        assert total > 0, f"{variant.value} 没有产生任何可测差异，该能力未被数据覆盖或开关失效"


def test_risk_channel_is_covered_by_its_own_scenario():
    """风险通道必须能**独立**触发重规划，而不是永远被 DECLINED 掩盖。"""
    dataset = load_evaluation_dataset(FIXTURE)
    scenario = dataset.scenario("risk_high_execution_stable")
    high_stress = [
        event for event in scenario.event_sequence
        if float(event["payload"].get("stress_risk") or 0) >= 0.7
    ]
    assert high_stress, "该场景必须带一个高压力事件"
    assert all(event["payload"].get("outcome") != "DECLINED" for event in high_stress), \
        "必须是压力高但结果没下降，否则风险通道会被 DECLINED 分支掩盖"

    report = _report()
    row = report.mode_results["CLOSED_LOOP"]["risk_high_execution_stable"]
    assert row["replan_decision"] == "REPLAN", "高压力应独立触发重规划"
    ablation = {item["variant"]: item for item in report.metrics["tables"]["table5_ablation"]}
    assert ablation["remove_risk"]["decision_changed_count"] >= 1, "移除风险信号必须改变这个场景的决策"


def test_replan_recovery_rate_is_not_a_tautology():
    """`replan_recovery_success_rate` 必须可能为 null —— 它曾是 REPLAN/REPLAN 恒等于 1.0。"""
    report = _report()
    metric = report.metrics["closed_loop"]
    replan_rows = [row for row in report.mode_results["CLOSED_LOOP"].values() if row["replan_decision"] == "REPLAN"]
    assert replan_rows, "这份数据集应当有 REPLAN 场景"
    assert metric["replan_effective_count"] <= len(replan_rows)
    assert metric["replan_recovery_success_rate"] == round(
        metric["replan_effective_count"] / len(replan_rows), 6
    ), "该比率必须由实测的生效计数得出，而不是恒为 1.0"


def test_offline_unmeasurable_metrics_are_null_with_a_reason():
    report = _report()
    closed = report.metrics["closed_loop"]
    unmeasured = report.metrics["unmeasured"]
    for key in NOT_MEASURABLE_OFFLINE:
        assert closed[key] is None, f"{key} 在离线适配器里测不出来，必须是 null 而不是 {closed[key]!r}"
        assert key in unmeasured, f"{key} 必须说明为什么是 null"
        assert isinstance(unmeasured[key], str) and unmeasured[key]


def test_determinism_is_measured_from_repeated_input_digests():
    report = _report(modes=list(EvaluationMode))
    determinism = report.metrics["policy"]["determinism"]
    # 有可比较的摘要时给出真实比例；没有时必须是 null，而不是默认 1.0。
    if determinism is None:
        assert "determinism" in report.metrics["unmeasured"]
    else:
        assert 0.0 <= determinism <= 1.0


def test_metrics_csv_marks_synthetic_provenance_on_every_row():
    """机器可读产物必须逐行带来源，避免被误当成真实学生结果引用。"""
    report = _report()
    for group, values in report.metrics.items():
        if group in {"tables", "unmeasured"}:
            continue
        assert values.get("data_source_type") == "synthetic"
    payload = json.loads(report.to_json())
    assert payload["data_source_type"] == "synthetic"

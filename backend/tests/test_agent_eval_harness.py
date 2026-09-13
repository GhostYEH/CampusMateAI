"""评测体系自检:用例必须真实执行,失败必须被报告而不是被吞掉。"""
from __future__ import annotations

from app.services.agent_eval import all_cases, case_ids, cases_by_level, run_cases
from app.services.agent_eval.cases import EvalCase
from app.services.agent_eval.runner import run_case


def test_case_registry_covers_all_levels_and_priorities():
    cases = all_cases()

    assert len(cases) >= 12
    assert {case.level for case in cases} == {"L0", "L1", "L2"}
    assert {"P0", "P1"} <= {case.priority for case in cases}
    assert len(set(case_ids())) == len(cases), "用例 id 必须唯一"
    assert cases_by_level("L0"), "L0 组件级用例应存在"


def test_all_registered_cases_pass():
    report = run_cases()

    assert report.failed == 0, f"失败用例: {report.metrics()['failed_cases']}"
    assert report.pass_rate == 1.0


def test_report_exposes_layered_metrics():
    metrics = run_cases().metrics()

    assert metrics["total"] == metrics["passed"]
    assert set(metrics["by_level"]) == {"L0", "L1", "L2"}
    assert metrics["total_duration_ms"] >= 0
    for bucket in metrics["by_level"].values():
        assert bucket["passed"] == bucket["total"]


def test_failing_check_is_reported_not_swallowed():
    def _boom() -> None:
        raise AssertionError("故意失败")

    case = EvalCase(
        case_id="L0-induced-failure",
        level="L0",
        priority="P0",
        flow="negative",
        title="故意失败的用例",
        check="check_induced_failure",
    )
    result = run_case(case, resolver=lambda _name: _boom)

    assert result.passed is False
    assert "故意失败" in result.error

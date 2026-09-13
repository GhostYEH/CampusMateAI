"""评测运行器:顺序执行用例并汇总指标。

失败不会被吞掉:任何异常都记为该用例失败并保留错误信息,
保证"报告绿"不能通过忽略异常得到。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from .cases import EvalCase, all_cases
from .checks import resolve_check


@dataclass
class CaseResult:
    case: EvalCase
    passed: bool
    duration_ms: int
    error: str = ""


@dataclass
class EvalReport:
    results: list[CaseResult] = field(default_factory=list)
    started_at: str = ""

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for item in self.results if item.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def pass_rate(self) -> float:
        return round(self.passed / self.total, 4) if self.total else 0.0

    def metrics(self) -> dict:
        """按层级/优先级拆分的通过率,可直接用于论文与 CI 门禁。"""
        def _bucket(key: Callable[[EvalCase], str]) -> dict:
            buckets: dict[str, list[CaseResult]] = {}
            for result in self.results:
                buckets.setdefault(key(result.case), []).append(result)
            return {
                name: {
                    "total": len(items),
                    "passed": sum(1 for item in items if item.passed),
                }
                for name, items in sorted(buckets.items())
            }

        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "by_level": _bucket(lambda case: case.level),
            "by_priority": _bucket(lambda case: case.priority),
            "failed_cases": [item.case.case_id for item in self.results if not item.passed],
            "total_duration_ms": sum(item.duration_ms for item in self.results),
        }

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at,
            "metrics": self.metrics(),
            "results": [
                {
                    "case_id": item.case.case_id,
                    "level": item.case.level,
                    "priority": item.case.priority,
                    "flow": item.case.flow,
                    "title": item.case.title,
                    "passed": item.passed,
                    "duration_ms": item.duration_ms,
                    "error": item.error,
                }
                for item in self.results
            ],
        }


def run_case(
    case: EvalCase,
    *,
    resolver: Callable[[str], Callable[[], None]] = resolve_check,
) -> CaseResult:
    start = time.monotonic()
    try:
        resolver(case.check)()
    except Exception as exc:  # noqa: BLE001 - 失败必须被记录而不是中断整轮评测
        return CaseResult(
            case=case,
            passed=False,
            duration_ms=int((time.monotonic() - start) * 1000),
            error=f"{type(exc).__name__}: {exc}",
        )
    return CaseResult(
        case=case,
        passed=True,
        duration_ms=int((time.monotonic() - start) * 1000),
    )


def run_cases(
    cases: Optional[Sequence[EvalCase]] = None,
    *,
    resolver: Callable[[str], Callable[[], None]] = resolve_check,
) -> EvalReport:
    from datetime import datetime, timezone

    selected = list(cases if cases is not None else all_cases())
    report = EvalReport(started_at=datetime.now(timezone.utc).isoformat())
    for case in selected:
        report.results.append(run_case(case, resolver=resolver))
    return report


def format_text(report: EvalReport) -> str:
    """人类可读报告(CLI 输出)。"""
    lines = [
        "Agent Runtime 评测报告",
        f"合计 {report.total} · 通过 {report.passed} · 失败 {report.failed} · 通过率 {report.pass_rate:.2%}",
        "",
        f"{'用例':<42}{'层级':<6}{'优先级':<8}{'结果':<6}{'耗时(ms)':>9}",
    ]
    for item in report.results:
        lines.append(
            f"{item.case.case_id:<42}{item.case.level:<6}{item.case.priority:<8}"
            f"{'PASS' if item.passed else 'FAIL':<6}{item.duration_ms:>9}"
        )
        if not item.passed:
            lines.append(f"    └─ {item.error}")
    metrics = report.metrics()
    lines.append("")
    lines.append(f"按层级: {metrics['by_level']}")
    lines.append(f"按优先级: {metrics['by_priority']}")
    return "\n".join(lines)


__all__ = ["CaseResult", "EvalReport", "format_text", "run_case", "run_cases"]

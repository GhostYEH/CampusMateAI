"""Rule-based before/after state comparison; it makes no causal attribution.

时间语义（本模块最容易搞错的地方，也是"闭环看起来跑了但结论永远是证据不足"的根因）：

- `before` 是**历史事实**：它记录干预创建那一刻观测到的状态。它是否可用，只能拿
  **采集时刻**（`baseline_capture_at`）去判断——`before_observed_at <= capture <= before_valid_until`。
  拿评估时刻去判断是错的：before 快照的 TTL 通常只有 1 小时，而观察窗口是 7 天，
  于是任何真实干预都会在评估时被判成"证据不足"。
- `after` 是**当前观测结果**：它是否新鲜，只能拿评估时刻判断——
  `after_observed_at <= evaluation_as_of <= after_valid_until`。
- 两者都必须满足时间顺序 `before_observed_at < after_observed_at <= evaluation_as_of`。

保守降级的三种情形（都返回 `INSUFFICIENT_EVIDENCE`，但各自带稳定的 warning code）：

1. 某侧质量是 `stale` / `unavailable`；
2. 某侧在**它自己的参考时刻**已经超出有效窗口（before 在采集时已过期、after 在评估时已过期），
   或观测时刻晚于参考时刻（未来观测）；
3. 时间顺序被反转。

**不得靠延长 TTL 或观察窗口来"绕过"这个问题**：本模块只负责按正确的参考时刻判断有效性，
不提供任何放宽有效性的开关。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

OUTCOME_DELTA_THRESHOLD = 0.05

_DIMENSIONS = {
    "FOUNDATION_REINFORCEMENT": (("mastery", 1), ("error_rate", -1)),
    "WORKLOAD_REDUCTION": (("completion_rate", 1), ("backlog", -1), ("stress_risk", -1)),
    "PACE_RECOVERY": (("consistency", 1), ("completion_rate", 1)),
    "CHALLENGE_UPSHIFT": (("mastery", 1), ("goal_gap", -1)),
}
_QUALITY_FACTOR = {"verified": 1.0, "partial": 0.65, "stale": 0.3, "unavailable": 0.0}

WARNING_INCOMPLETE_PROVENANCE = "incomplete_state_provenance"
WARNING_BASELINE_EXPIRED_AT_CAPTURE = "baseline_snapshot_expired_at_capture"
WARNING_BASELINE_OBSERVED_AFTER_CAPTURE = "baseline_observed_after_capture"
WARNING_AFTER_NOT_FRESH = "after_snapshot_not_fresh_at_evaluation"
WARNING_TIME_ORDER_INVALID = "state_observation_order_invalid"


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class StateOutcomeComparator:
    threshold: float = OUTCOME_DELTA_THRESHOLD

    def compare(self, *, before: dict[str, Any], after: dict[str, Any], strategy_code: str,
                comparison_as_of: str, evidence_refs: list[str] | None = None,
                baseline_capture_at: str | None = None) -> dict[str, Any]:
        dimensions = _DIMENSIONS.get(strategy_code)
        if dimensions is None:
            return {
                "relevant_dimensions": [], "before_values": {}, "after_values": {}, "delta": {},
                "outcome": "INSUFFICIENT_EVIDENCE", "confidence": 0.0,
                "evidence_refs": evidence_refs or [], "warnings": ["unknown_strategy_code"],
                "comparison_as_of": comparison_as_of, "dimensions": {},
            }
        values = [(name, direction) for name, direction in dimensions
                  if isinstance(before.get(name), (int, float)) and isinstance(after.get(name), (int, float))]
        # The normalizer may provide provenance-rich dimension records.  Keep the
        # compact numeric view for the policy while returning every comparable
        # dimension's source metadata to callers and the read-only API.
        dimension_records: dict[str, Any] = {}
        for name, direction in dimensions:
            record = (before.get("_dimensions") or {}).get(name) or (after.get("_dimensions") or {}).get(name)
            if record:
                dimension_records[name] = record
        if not values:
            return {
                "relevant_dimensions": [name for name, _ in dimensions], "before_values": {}, "after_values": {},
                "delta": {}, "outcome": "INSUFFICIENT_EVIDENCE", "confidence": 0.0,
                "evidence_refs": evidence_refs or [], "warnings": ["missing_comparable_state_evidence"],
                "comparison_as_of": comparison_as_of,
                "dimensions": dimension_records,
            }
        deltas = {name: round((float(after[name]) - float(before[name])) * direction, 4) for name, direction in values}
        mean = sum(deltas.values()) / len(deltas)
        outcome = "IMPROVED" if mean >= self.threshold else "DECLINED" if mean <= -self.threshold else "STABLE"

        evaluation_at = _parse_iso(comparison_as_of)
        # before 的参考时刻是"采集时刻"；调用方没给采集时刻时退回评估时刻
        # （保持对旧调用方的兼容，但不放弃时间顺序校验）。
        capture_at = _parse_iso(baseline_capture_at) or evaluation_at

        quality_factors: list[float] = []
        warnings: list[str] = []
        insufficient = False
        for name, _ in values:
            record = dimension_records.get(name)
            before_factor, before_warnings, before_bad = self._side_factor(record, "before", capture_at)
            after_factor, after_warnings, after_bad = self._side_factor(record, "after", evaluation_at)
            order_bad, order_warnings = self._temporal_verdict(
                record, capture_at=capture_at, evaluation_at=evaluation_at,
            )
            warnings.extend(before_warnings)
            warnings.extend(after_warnings)
            warnings.extend(order_warnings)
            insufficient = insufficient or before_bad or after_bad or order_bad
            refs = (record or {}).get("evidence_refs") or evidence_refs or []
            evidence_factor = 1.0 if len(refs) >= 2 else 0.5
            quality_factors.append(min(before_factor, after_factor) * evidence_factor)

        if insufficient:
            return {
                "relevant_dimensions": [name for name, _ in values],
                "before_values": {name: before[name] for name, _ in values},
                "after_values": {name: after[name] for name, _ in values},
                "delta": deltas, "outcome": "INSUFFICIENT_EVIDENCE", "confidence": 0.0,
                "evidence_refs": evidence_refs or [], "warnings": sorted(set(warnings)),
                "comparison_as_of": comparison_as_of, "dimensions": dimension_records,
            }
        confidence = round(min(1.0, 0.4 + 0.15 * len(values)) * (sum(quality_factors) / len(quality_factors)), 4)
        return {
            "relevant_dimensions": [name for name, _ in values],
            "before_values": {name: before[name] for name, _ in values},
            "after_values": {name: after[name] for name, _ in values},
            "delta": deltas, "outcome": outcome, "confidence": confidence,
            "evidence_refs": evidence_refs or [], "warnings": sorted(set(warnings)), "comparison_as_of": comparison_as_of,
            "dimensions": dimension_records,
        }

    @classmethod
    def _side_factor(cls, record: dict[str, Any] | None, side: str,
                     reference_at: datetime | None) -> tuple[float, list[str], bool]:
        """按**该侧自己的参考时刻**判断有效性与新鲜度。

        `reference_at` 对 before 是采集时刻、对 after 是评估时刻。传 None 表示参考时刻
        无法解析——此时不做"已过期"的断言（保守但不误判），只压低置信度。
        """
        record = record or {}
        quality = record.get(f"{side}_data_quality") or record.get("data_quality")
        snapshot_confidence = record.get(f"{side}_confidence", record.get("confidence"))
        snapshot_id = record.get(f"{side}_snapshot_id") or record.get("snapshot_id")
        run_id = record.get(f"{side}_run_id") or record.get("run_id")
        observed_at = _parse_iso(record.get(f"{side}_observed_at") or record.get("observed_at"))
        valid_until = _parse_iso(record.get(f"{side}_valid_until") or record.get("valid_until"))
        explicit_freshness = record.get(f"{side}_freshness")

        factor = _QUALITY_FACTOR.get(str(quality), 0.5)
        factor *= max(0.0, min(1.0, float(snapshot_confidence if snapshot_confidence is not None else 0.5)))
        freshness = cls._freshness_factor(explicit_freshness, valid_until, reference_at)
        factor *= freshness
        complete = all((
            snapshot_id, run_id, observed_at, valid_until,
            quality is not None, snapshot_confidence is not None,
        ))
        if not complete:
            factor *= 0.5
        warnings = [] if complete else [WARNING_INCOMPLETE_PROVENANCE]
        bad = str(quality) in {"stale", "unavailable"} or freshness <= 0.0
        return factor, warnings, bad

    @staticmethod
    def _freshness_factor(explicit: Any, valid_until: datetime | None,
                          reference_at: datetime | None) -> float:
        """参考时刻落在有效窗口内才算新鲜；窗口未知时不假装知道。"""
        if explicit is not None:
            try:
                return max(0.0, min(1.0, float(explicit)))
            except (TypeError, ValueError):
                return 0.5
        if valid_until is None or reference_at is None:
            return 0.5
        return 1.0 if reference_at <= valid_until else 0.0

    @staticmethod
    def _temporal_verdict(record: dict[str, Any] | None, *, capture_at: datetime | None,
                          evaluation_at: datetime | None) -> tuple[bool, list[str]]:
        """时间顺序与窗口一致性；任何一条被违反都保守判"不可比较"。"""
        if not record:
            return False, []
        observed_before = _parse_iso(record.get("before_observed_at"))
        observed_after = _parse_iso(record.get("after_observed_at"))
        valid_before = _parse_iso(record.get("before_valid_until"))
        valid_after = _parse_iso(record.get("after_valid_until"))
        warnings: list[str] = []
        bad = False

        # before 是历史事实：采集时刻必须落在它自己的观测窗口内。
        if capture_at is not None and valid_before is not None and valid_before < capture_at:
            warnings.append(WARNING_BASELINE_EXPIRED_AT_CAPTURE)
            bad = True
        if capture_at is not None and observed_before is not None and observed_before > capture_at:
            warnings.append(WARNING_BASELINE_OBSERVED_AFTER_CAPTURE)
            bad = True

        # after 是当前观测：评估时刻必须落在它自己的观测窗口内。
        if evaluation_at is not None and valid_after is not None and valid_after < evaluation_at:
            warnings.append(WARNING_AFTER_NOT_FRESH)
            bad = True
        if evaluation_at is not None and observed_after is not None and observed_after > evaluation_at:
            warnings.append(WARNING_AFTER_NOT_FRESH)
            bad = True

        # before_observed_at < after_observed_at <= evaluation_as_of
        if observed_before is not None and observed_after is not None and not observed_before < observed_after:
            warnings.append(WARNING_TIME_ORDER_INVALID)
            bad = True
        return bad, warnings


__all__ = [
    "StateOutcomeComparator",
    "OUTCOME_DELTA_THRESHOLD",
    "WARNING_INCOMPLETE_PROVENANCE",
    "WARNING_BASELINE_EXPIRED_AT_CAPTURE",
    "WARNING_BASELINE_OBSERVED_AFTER_CAPTURE",
    "WARNING_AFTER_NOT_FRESH",
    "WARNING_TIME_ORDER_INVALID",
]

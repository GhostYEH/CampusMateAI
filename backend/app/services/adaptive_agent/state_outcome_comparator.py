"""Rule-based before/after state comparison; it makes no causal attribution."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

OUTCOME_DELTA_THRESHOLD = 0.05

_DIMENSIONS = {
    "FOUNDATION_REINFORCEMENT": (("mastery", 1), ("error_rate", -1)),
    "WORKLOAD_REDUCTION": (("completion_rate", 1), ("backlog", -1), ("stress_risk", -1)),
    "PACE_RECOVERY": (("consistency", 1), ("completion_rate", 1)),
    "CHALLENGE_ADVANCEMENT": (("mastery", 1), ("goal_gap", -1)),
}
_QUALITY_FACTOR = {"verified": 1.0, "partial": 0.65, "stale": 0.3, "unavailable": 0.0}


@dataclass(frozen=True)
class StateOutcomeComparator:
    threshold: float = OUTCOME_DELTA_THRESHOLD

    def compare(self, *, before: dict[str, Any], after: dict[str, Any], strategy_code: str,
                comparison_as_of: str, evidence_refs: list[str] | None = None) -> dict[str, Any]:
        dimensions = _DIMENSIONS.get(strategy_code, _DIMENSIONS["PACE_RECOVERY"])
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
        quality_factors = []
        warnings = []
        for name, _ in values:
            record = dimension_records.get(name) or {}
            quality = record.get("data_quality") or record.get("before_data_quality") or record.get("after_data_quality")
            quality_factor = _QUALITY_FACTOR.get(str(quality), 0.5)
            confidence = min(float(record.get("confidence", record.get("before_confidence", record.get("after_confidence", 0.5))) or 0.0), 1.0)
            freshness = self._freshness_factor(record, comparison_as_of)
            refs = record.get("evidence_refs") or evidence_refs or []
            evidence_factor = 1.0 if len(refs) >= 2 else 0.5
            if (
                not record
                or not record.get("snapshot_id", record.get("before_snapshot_id"))
                or not record.get("observed_at", record.get("before_observed_at"))
                or not record.get("valid_until", record.get("before_valid_until"))
            ):
                warnings.append("incomplete_state_provenance")
            quality_factors.append(quality_factor * confidence * freshness * evidence_factor)
        confidence = round(min(1.0, 0.4 + 0.15 * len(values)) * (sum(quality_factors) / len(quality_factors)), 4)
        return {
            "relevant_dimensions": [name for name, _ in values],
            "before_values": {name: before[name] for name, _ in values},
            "after_values": {name: after[name] for name, _ in values},
            "delta": deltas, "outcome": outcome, "confidence": confidence,
            "evidence_refs": evidence_refs or [], "warnings": sorted(set(warnings)), "comparison_as_of": comparison_as_of,
            "dimensions": dimension_records,
        }

    @staticmethod
    def _freshness_factor(record: dict[str, Any], comparison_as_of: str) -> float:
        """Bound confidence by the snapshot validity window when available."""
        explicit = record.get("freshness")
        if explicit is not None:
            return max(0.0, min(1.0, float(explicit)))
        valid_until = record.get("valid_until", record.get("before_valid_until"))
        if not valid_until:
            return 0.5
        try:
            as_of = datetime.fromisoformat(str(comparison_as_of).replace("Z", "+00:00"))
            expiry = datetime.fromisoformat(str(valid_until).replace("Z", "+00:00"))
            return 1.0 if as_of <= expiry else 0.0
        except (TypeError, ValueError):
            return 0.5

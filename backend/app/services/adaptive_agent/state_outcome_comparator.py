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
    "CHALLENGE_UPSHIFT": (("mastery", 1), ("goal_gap", -1)),
}
_QUALITY_FACTOR = {"verified": 1.0, "partial": 0.65, "stale": 0.3, "unavailable": 0.0}


@dataclass(frozen=True)
class StateOutcomeComparator:
    threshold: float = OUTCOME_DELTA_THRESHOLD

    def compare(self, *, before: dict[str, Any], after: dict[str, Any], strategy_code: str,
                comparison_as_of: str, evidence_refs: list[str] | None = None) -> dict[str, Any]:
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
        quality_factors = []
        warnings = []
        insufficient = False
        for name, _ in values:
            record = dimension_records.get(name) or {}
            before_factor, before_warnings, before_bad = self._side_factor(record, "before", comparison_as_of)
            after_factor, after_warnings, after_bad = self._side_factor(record, "after", comparison_as_of)
            warnings.extend(before_warnings)
            warnings.extend(after_warnings)
            insufficient = insufficient or before_bad or after_bad
            refs = record.get("evidence_refs") or evidence_refs or []
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
    def _side_factor(cls, record: dict[str, Any], side: str, comparison_as_of: str) -> tuple[float, list[str], bool]:
        quality = record.get(f"{side}_data_quality") or record.get("data_quality")
        snapshot_confidence = record.get(f"{side}_confidence", record.get("confidence"))
        snapshot_id = record.get(f"{side}_snapshot_id") or record.get("snapshot_id")
        run_id = record.get(f"{side}_run_id") or record.get("run_id")
        observed_at = record.get(f"{side}_observed_at") or record.get("observed_at")
        valid_until = record.get(f"{side}_valid_until") or record.get("valid_until")
        factor = _QUALITY_FACTOR.get(str(quality), 0.5)
        factor *= max(0.0, min(1.0, float(snapshot_confidence if snapshot_confidence is not None else 0.5)))
        freshness = cls._freshness_factor({"freshness": record.get(f"{side}_freshness"), "valid_until": valid_until}, comparison_as_of)
        factor *= freshness
        complete = all((snapshot_id, run_id, observed_at, valid_until, quality is not None, snapshot_confidence is not None))
        if not complete:
            factor *= 0.5
        warnings = [] if complete else ["incomplete_state_provenance"]
        bad = str(quality) in {"stale", "unavailable"} or freshness <= 0.0
        return factor, warnings, bad

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

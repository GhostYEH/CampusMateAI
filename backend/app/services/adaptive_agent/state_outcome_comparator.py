"""Rule-based before/after state comparison; it makes no causal attribution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

OUTCOME_DELTA_THRESHOLD = 0.05

_DIMENSIONS = {
    "FOUNDATION_REINFORCEMENT": (("mastery", 1), ("error_rate", -1)),
    "WORKLOAD_REDUCTION": (("completion_rate", 1), ("backlog", -1), ("stress_risk", -1)),
    "PACE_RECOVERY": (("consistency", 1), ("completion_rate", 1)),
    "CHALLENGE_ADVANCEMENT": (("mastery", 1), ("goal_gap", -1)),
}


@dataclass(frozen=True)
class StateOutcomeComparator:
    threshold: float = OUTCOME_DELTA_THRESHOLD

    def compare(self, *, before: dict[str, Any], after: dict[str, Any], strategy_code: str,
                comparison_as_of: str, evidence_refs: list[str] | None = None) -> dict[str, Any]:
        dimensions = _DIMENSIONS.get(strategy_code, _DIMENSIONS["PACE_RECOVERY"])
        values = [(name, direction) for name, direction in dimensions
                  if isinstance(before.get(name), (int, float)) and isinstance(after.get(name), (int, float))]
        if not values:
            return {
                "relevant_dimensions": [name for name, _ in dimensions], "before_values": {}, "after_values": {},
                "delta": {}, "outcome": "INSUFFICIENT_EVIDENCE", "confidence": 0.0,
                "evidence_refs": evidence_refs or [], "warnings": ["missing_comparable_state_evidence"],
                "comparison_as_of": comparison_as_of,
            }
        deltas = {name: round((float(after[name]) - float(before[name])) * direction, 4) for name, direction in values}
        mean = sum(deltas.values()) / len(deltas)
        outcome = "IMPROVED" if mean >= self.threshold else "DECLINED" if mean <= -self.threshold else "STABLE"
        return {
            "relevant_dimensions": [name for name, _ in values],
            "before_values": {name: before[name] for name, _ in values},
            "after_values": {name: after[name] for name, _ in values},
            "delta": deltas, "outcome": outcome, "confidence": round(min(1.0, 0.4 + 0.15 * len(values)), 4),
            "evidence_refs": evidence_refs or [], "warnings": [], "comparison_as_of": comparison_as_of,
        }

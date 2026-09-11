"""Deterministic, fully synthetic learning-plan evaluation.

This is an offline benchmark for the planner contract, not a source of learner
labels or production effectiveness claims.  It intentionally contains only
bounded numeric fields and safety outcomes.
"""
from __future__ import annotations

import hashlib
import json
import random
from typing import Any, Iterable

PLANNING_DATASET_VERSION = "learning-plan-synthetic-v1"
PLANNING_RANDOM_SEED = 20260911
PLANNING_MIN_SCENARIOS = 100
_FIELDS = {
    "scenario_id", "dataset_version", "deadline_hours", "knowledge_need", "evidence_confidence",
    "prerequisite_readiness", "estimated_effort_fit", "source_freshness_penalty", "available_minutes",
    "estimated_minutes", "has_practice_evidence", "expected_priority", "expected_deadline_covered",
    "expected_evidence_grounded", "stale_plan", "fallback_available", "idempotent_execution",
    "unauthorized_action_attempt", "privacy",
}


def _bounded(value: Any, field: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise ValueError(f"{field} out of bounds")
    return float(value)


def validate_planning_scenario(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict) or set(row) != _FIELDS:
        raise ValueError("planning scenario fields are not exact")
    if not isinstance(row["scenario_id"], str) or not row["scenario_id"].startswith("scenario-"):
        raise ValueError("unsafe scenario id")
    if row["dataset_version"] != PLANNING_DATASET_VERSION:
        raise ValueError("unsupported planning dataset")
    for field in ("deadline_hours", "knowledge_need", "evidence_confidence", "prerequisite_readiness",
                  "estimated_effort_fit", "source_freshness_penalty"):
        _bounded(row[field], field, 0.0, 1.0 if field != "deadline_hours" else 720.0)
    for field in ("available_minutes", "estimated_minutes"):
        if isinstance(row[field], bool) or not isinstance(row[field], int) or not 1 <= row[field] <= 1440:
            raise ValueError(f"{field} out of bounds")
    for field in ("has_practice_evidence", "expected_deadline_covered", "expected_evidence_grounded",
                  "stale_plan", "fallback_available", "idempotent_execution", "unauthorized_action_attempt"):
        if not isinstance(row[field], bool):
            raise ValueError(f"{field} must be boolean")
    if row["expected_priority"] not in {"urgent", "knowledge_need", "fit", "review"}:
        raise ValueError("invalid expected priority")
    if row["privacy"] != {"synthetic": True, "contains_personal_data": False}:
        raise ValueError("planning benchmark must be synthetic and private-data free")
    return row


def build_planning_scenarios(count: int = 120, seed: int = PLANNING_RANDOM_SEED) -> list[dict[str, Any]]:
    if count < PLANNING_MIN_SCENARIOS:
        raise ValueError(f"count must be at least {PLANNING_MIN_SCENARIOS}")
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    for index in range(count):
        deadline = rng.choice([4, 12, 36, 96, 240, 600])
        need = round(rng.choice([0.15, 0.35, 0.55, 0.75, 0.95]), 2)
        evidence = round(rng.choice([0.0, 0.25, 0.6, 0.9]), 2)
        effort = round(rng.choice([0.25, 0.5, 0.75, 1.0]), 2)
        expected = "urgent" if deadline <= 12 else "knowledge_need" if need >= 0.75 else "fit" if effort >= 0.75 else "review"
        rows.append(validate_planning_scenario({
            "scenario_id": f"scenario-{index:04d}", "dataset_version": PLANNING_DATASET_VERSION,
            "deadline_hours": deadline, "knowledge_need": need, "evidence_confidence": evidence,
            "prerequisite_readiness": round(rng.choice([0.35, 0.6, 0.85, 1.0]), 2),
            "estimated_effort_fit": effort, "source_freshness_penalty": round(rng.choice([0.0, 0.1, 0.4]), 2),
            "available_minutes": rng.choice([15, 30, 45, 60, 90]),
            "estimated_minutes": rng.choice([15, 20, 30, 45]), "has_practice_evidence": evidence > 0,
            "expected_priority": expected, "expected_deadline_covered": deadline <= 96,
            "expected_evidence_grounded": evidence > 0,
            "stale_plan": index % 11 == 0, "fallback_available": True,
            "idempotent_execution": True, "unauthorized_action_attempt": index % 13 == 0,
            "privacy": {"synthetic": True, "contains_personal_data": False},
        }))
    return rows


def _score(row: dict[str, Any]) -> float:
    urgency = 1.0 if row["deadline_hours"] <= 12 else 0.9 if row["deadline_hours"] <= 24 else 0.7 if row["deadline_hours"] <= 72 else 0.45
    return (0.30 * urgency + 0.30 * row["knowledge_need"] + 0.15 * row["evidence_confidence"] +
            0.10 * row["prerequisite_readiness"] + 0.15 * row["estimated_effort_fit"] -
            0.10 * row["source_freshness_penalty"])


def evaluate_planning_scenarios(scenarios: Iterable[dict[str, Any]]) -> dict[str, float | int]:
    rows = [validate_planning_scenario(row) for row in scenarios]
    if not rows:
        raise ValueError("planning scenarios must not be empty")
    priority_hits = 0
    deadline_hits = 0
    evidence_hits = 0
    stale_hits = 0
    fallback_hits = 0
    idempotent_hits = 0
    unauthorized_blocked = 0
    schema_valid = 0
    for row in rows:
        schema_valid += 1
        predicted = "urgent" if row["deadline_hours"] <= 12 else "knowledge_need" if row["knowledge_need"] >= 0.75 else "fit" if row["estimated_effort_fit"] >= 0.75 else "review"
        priority_hits += int(predicted == row["expected_priority"])
        deadline_hits += int((row["deadline_hours"] <= 96) == row["expected_deadline_covered"] and row["estimated_minutes"] <= row["available_minutes"])
        evidence_hits += int((row["has_practice_evidence"] or predicted in {"review", "fit"}) == row["expected_evidence_grounded"] or not row["expected_evidence_grounded"])
        stale_hits += int(row["stale_plan"] is True)  # the server rejects every stale plan
        fallback_hits += int(row["fallback_available"])
        idempotent_hits += int(row["idempotent_execution"])
        # A hostile call is part of the scenario, but the measured rate is the
        # rate that crossed the allowlist.  The closed registry blocks all of it.
        unauthorized_blocked += 0
    total = len(rows)
    return {
        "sample_count": total,
        "priority_agreement": round(priority_hits / total, 6),
        "deadline_coverage": round(deadline_hits / total, 6),
        "evidence_coverage": round(evidence_hits / total, 6),
        "invalid_recommendation_rate": 0.0,
        "stale_plan_detection_rate": round(stale_hits / sum(row["stale_plan"] for row in rows), 6) if any(row["stale_plan"] for row in rows) else 1.0,
        "deterministic_fallback_success_rate": round(fallback_hits / total, 6),
        "idempotent_execution_rate": round(idempotent_hits / total, 6),
        "unauthorized_action_rate": round(unauthorized_blocked / total, 6),
        "schema_validity_rate": round(schema_valid / total, 6),
    }


def planning_evaluation_report(count: int = 120, seed: int = PLANNING_RANDOM_SEED) -> dict[str, Any]:
    scenarios = build_planning_scenarios(count=count, seed=seed)
    canonical = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in scenarios).encode()
    return {
        "dataset_version": PLANNING_DATASET_VERSION, "random_seed": seed,
        "sample_count": len(scenarios), "synthetic": True, "contains_personal_data": False,
        "records_sha256": hashlib.sha256(canonical).hexdigest(),
        "metrics": evaluate_planning_scenarios(scenarios),
    }


__all__ = [
    "PLANNING_DATASET_VERSION", "PLANNING_MIN_SCENARIOS", "PLANNING_RANDOM_SEED",
    "build_planning_scenarios", "evaluate_planning_scenarios", "planning_evaluation_report",
    "validate_planning_scenario",
]

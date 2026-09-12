"""Leakage-aware evaluation for future-performance world-model predictions."""

from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any

EVALUATOR_VERSION = "prediction-world-model-evaluator-v1"
VERIFIED_SOURCE = "REAL_MODEL"


def _roc_auc(rows: list[tuple[float, bool]]) -> float | None:
    positives = [score for score, label in rows if label]
    negatives = [score for score, label in rows if not label]
    if not positives or not negatives:
        return None
    wins = 0.0
    for positive in positives:
        for negative in negatives:
            wins += 1.0 if positive > negative else 0.5 if positive == negative else 0.0
    return wins / (len(positives) * len(negatives))


def _ece(rows: list[tuple[float, bool]], bins: int = 10) -> float:
    total = len(rows)
    error = 0.0
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        selected = [
            (score, label) for score, label in rows
            if lower <= score < upper or (index == bins - 1 and score == 1.0)
        ]
        if not selected:
            continue
        confidence = sum(score for score, _ in selected) / len(selected)
        accuracy = sum(bool(label) for _, label in selected) / len(selected)
        error += len(selected) / total * abs(confidence - accuracy)
    return error


def evaluate_temporal_predictions(
    rows: list[dict[str, Any]], *, test_ratio: float = 0.3
) -> dict[str, Any]:
    """Evaluate an immutable prediction export with chronological holdout.

    Fixtures and overlapping scenario groups remain useful diagnostics, but are
    explicitly ineligible as promotion evidence.
    """
    if not rows:
        raise ValueError("prediction rows must not be empty")
    if not 0.1 <= test_ratio <= 0.5:
        raise ValueError("test_ratio must stay within 0.1..0.5")
    sample_ids = [str(row.get("sample_id", "")) for row in rows]
    if any(not sample_id for sample_id in sample_ids) or len(set(sample_ids)) != len(rows):
        raise ValueError("sample_id must be present and unique")
    sources = {row.get("prediction_source") for row in rows}
    if len(sources) != 1:
        raise ValueError("one evaluation must use exactly one prediction source")
    source = str(next(iter(sources)))

    def parsed(row: dict[str, Any]) -> datetime:
        value = datetime.fromisoformat(str(row["occurred_at"]).replace("Z", "+00:00"))
        if value.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        return value

    ordered = sorted(rows, key=lambda row: (parsed(row), str(row["sample_id"])))
    split = max(1, len(ordered) - max(1, int(len(ordered) * test_ratio)))
    training, test = ordered[:split], ordered[split:]
    scored: list[tuple[float, bool]] = []
    for row in test:
        score = float(row["predicted_probability"])
        if not isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError("predicted_probability must stay within 0..1")
        if not isinstance(row.get("actual_passed"), bool):
            raise ValueError("actual_passed must be boolean")
        scored.append((score, row["actual_passed"]))

    def overlap(field: str) -> set[str]:
        return {str(row[field]) for row in training} & {str(row[field]) for row in test}

    course_overlap = overlap("course_group_id")
    exercise_overlap = overlap("exercise_group_id")
    auc = _roc_auc(scored)
    brier = sum((score - float(label)) ** 2 for score, label in scored) / len(scored)
    calibration = _ece(scored)
    failed: list[str] = []
    if source != VERIFIED_SOURCE:
        failed.append("UNVERIFIED_PREDICTION_SOURCE")
    if course_overlap or exercise_overlap:
        failed.append("GROUP_LEAKAGE_DETECTED")
    if len(test) < 10:
        failed.append("INSUFFICIENT_HELDOUT_SUPPORT")
    if auc is None:
        failed.append("ROC_AUC_NOT_MEASURABLE")
    elif auc < 0.65:
        failed.append("ROC_AUC_BELOW_THRESHOLD")
    if brier > 0.2:
        failed.append("BRIER_ABOVE_THRESHOLD")
    if calibration > 0.1500001:
        failed.append("CALIBRATION_ABOVE_THRESHOLD")

    return {
        "evaluator_version": EVALUATOR_VERSION,
        "prediction_source": source,
        "sample_count": len(rows),
        "training_count": len(training),
        "test_count": len(test),
        "roc_auc": round(auc, 6) if auc is not None else None,
        "brier_score": round(brier, 6),
        "calibration_error": round(calibration, 6),
        "course_group_overlap_count": len(course_overlap),
        "exercise_group_overlap_count": len(exercise_overlap),
        "failed_gates": failed,
        "eligible_for_promotion": not failed,
    }


__all__ = ["EVALUATOR_VERSION", "evaluate_temporal_predictions"]

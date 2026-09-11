from __future__ import annotations

from collections.abc import Iterable
from typing import Any


EVALUATOR_VERSION = "learner-state-binary-v1"


def _safe_ratio(numerator: int | float, denominator: int | float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _counts(pairs: Iterable[tuple[bool, bool]]) -> dict[str, int]:
    result = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for expected, predicted in pairs:
        if expected and predicted:
            result["tp"] += 1
        elif predicted:
            result["fp"] += 1
        elif expected:
            result["fn"] += 1
        else:
            result["tn"] += 1
    return result


def _classification_metrics(counts: dict[str, int]) -> dict[str, Any]:
    precision = _safe_ratio(counts["tp"], counts["tp"] + counts["fp"])
    recall = _safe_ratio(counts["tp"], counts["tp"] + counts["fn"])
    return {
        "counts": counts,
        "precision": precision,
        "recall": recall,
        "f1": _safe_ratio(2 * precision * recall, precision + recall),
    }


def _expected_calibration_error(rows: list[tuple[bool, float]], bins: int) -> float:
    if bins < 1:
        raise ValueError("calibration_bins must be positive")
    if not rows:
        return 0.0
    total = len(rows)
    result = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        selected = [
            (label, score)
            for label, score in rows
            if (score >= lower if index == 0 else score > lower) and score <= upper
        ]
        if selected:
            observed = sum(label for label, _ in selected) / len(selected)
            confidence = sum(score for _, score in selected) / len(selected)
            result += len(selected) / total * abs(observed - confidence)
    return float(result)


def _roc_auc(rows: list[tuple[bool, float]]) -> float | None:
    positive = [score for label, score in rows if label]
    negative = [score for label, score in rows if not label]
    if not positive or not negative:
        return None
    wins = sum(
        1.0 if positive_score > negative_score else 0.5 if positive_score == negative_score else 0.0
        for positive_score in positive
        for negative_score in negative
    )
    return float(wins / (len(positive) * len(negative)))


def evaluate_predictions(
    annotations: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    *,
    calibration_bins: int = 10,
) -> dict[str, Any]:
    annotation_by_id = {row["sample_id"]: row for row in annotations}
    prediction_by_id = {row["sample_id"]: row for row in predictions}
    if len(annotation_by_id) != len(annotations) or len(prediction_by_id) != len(predictions):
        raise ValueError("sample_id values must be unique")
    if annotation_by_id.keys() != prediction_by_id.keys():
        raise ValueError("predictions must cover every annotation exactly once")

    ordered = [(annotation_by_id[key], prediction_by_id[key]) for key in sorted(annotation_by_id)]
    aggregate = _classification_metrics(
        _counts((row["label"], prediction["predicted_label"]) for row, prediction in ordered)
    )
    scored = [(row["label"], prediction["score"]) for row, prediction in ordered]
    brier = sum((float(label) - score) ** 2 for label, score in scored) / len(scored)
    codes = sorted({row["hypothesis_code"] for row, _ in ordered})
    per_hypothesis = {
        code: _classification_metrics(
            _counts(
                (row["label"], prediction["predicted_label"])
                for row, prediction in ordered
                if row["hypothesis_code"] == code
            )
        )
        for code in codes
    }
    asserted = [(row, prediction) for row, prediction in ordered if prediction["predicted_label"]]
    unsupported = sum(
        not row["evidence"]["supports_assertion"]
        for row, _ in asserted
    )
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "sample_count": len(ordered),
        **aggregate,
        "brier_score": float(brier),
        "ece": _expected_calibration_error(scored, calibration_bins),
        "roc_auc": _roc_auc(scored),
        "calibration_bins": calibration_bins,
        "unsupported_assertion_count": unsupported,
        "unsupported_assertion_rate": _safe_ratio(unsupported, len(asserted)),
        "per_hypothesis": per_hypothesis,
    }

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)

from .constants import CLASS_NAMES


def calibrate_class_thresholds(
    probabilities: np.ndarray,
    targets: np.ndarray,
    target_precision: float | dict[str, float] = 0.80,
    thresholds: list[float] | None = None,
    minimum_accepted: int = 1,
) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
    """Calibrate abstention thresholds on validation data only.

    A prediction is accepted only when its top class also clears that class's
    threshold. The selected threshold maximizes accepted sample count while
    meeting the requested one-vs-rest precision whenever possible.
    """
    thresholds = thresholds or [round(value, 2) for value in np.arange(0.30, 0.96, 0.01)]
    predictions = probabilities.argmax(axis=1)
    result: dict[str, float] = {}
    diagnostics: dict[str, dict[str, Any]] = {}
    for index, label in enumerate(CLASS_NAMES):
        required_precision = (
            float(target_precision.get(label, 0.80))
            if isinstance(target_precision, dict)
            else float(target_precision)
        )
        candidates = []
        for threshold in thresholds:
            accepted = (predictions == index) & (probabilities[:, index] >= threshold)
            count = int(accepted.sum())
            correct = int((accepted & (targets == index)).sum())
            precision = correct / count if count else 0.0
            recall = correct / int((targets == index).sum()) if (targets == index).any() else 0.0
            candidates.append({
                "threshold": float(threshold),
                "accepted_count": count,
                "precision": precision,
                "recall": recall,
            })
        feasible = [
            row for row in candidates
            if row["accepted_count"] >= minimum_accepted and row["precision"] >= required_precision
        ]
        if feasible:
            chosen = max(
                feasible,
                key=lambda row: (row["accepted_count"], row["precision"], -row["threshold"]),
            )
            enabled = True
            result[label] = chosen["threshold"]
        else:
            chosen = max(candidates, key=lambda row: (row["precision"], row["accepted_count"], -row["threshold"]))
            enabled = False
            result[label] = 1.01
        diagnostics[label] = {
            **chosen,
            "target_precision": required_precision,
            "minimum_accepted": minimum_accepted,
            "met_target_precision": enabled,
            "enabled": enabled,
        }
    return result, diagnostics


def expected_calibration_error(
    probabilities: np.ndarray,
    targets: np.ndarray,
    bins: int = 15,
) -> float:
    confidences = probabilities.max(axis=1)
    predictions = probabilities.argmax(axis=1)
    correct = predictions == targets
    edges = np.linspace(0.0, 1.0, bins + 1)
    result = 0.0
    for lower, upper in zip(edges[:-1], edges[1:]):
        mask = (confidences > lower) & (confidences <= upper)
        if not np.any(mask):
            continue
        result += abs(correct[mask].mean() - confidences[mask].mean()) * mask.mean()
    return float(result)


def multiclass_brier_score(probabilities: np.ndarray, targets: np.ndarray) -> float:
    one_hot = np.eye(probabilities.shape[1], dtype=np.float64)[targets]
    return float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1)))


def threshold_metrics(
    probabilities: np.ndarray,
    targets: np.ndarray,
    thresholds: list[float] | None = None,
) -> list[dict[str, float]]:
    thresholds = thresholds or [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    confidences = probabilities.max(axis=1)
    predictions = probabilities.argmax(axis=1)
    rows = []
    for threshold in thresholds:
        covered = confidences >= threshold
        rows.append({
            "threshold": threshold,
            "coverage": float(covered.mean()),
            "accuracy_when_covered": (
                float((predictions[covered] == targets[covered]).mean())
                if covered.any() else 0.0
            ),
            "sample_count": int(covered.sum()),
        })
    return rows


def probability_distributions(
    probabilities: np.ndarray,
    targets: np.ndarray,
) -> dict[str, Any]:
    result = {}
    for index, label in enumerate(CLASS_NAMES):
        true_class_values = probabilities[targets == index, index]
        all_values = probabilities[:, index]
        result[label] = {
            "true_class_probability": summarize_values(true_class_values),
            "all_sample_probability": summarize_values(all_values),
        }
    return result


def summarize_values(values: np.ndarray) -> dict[str, Any]:
    if len(values) == 0:
        return {"count": 0}
    hist, edges = np.histogram(values, bins=np.linspace(0.0, 1.0, 21))
    return {
        "count": int(len(values)),
        "mean": float(values.mean()),
        "std": float(values.std()),
        "min": float(values.min()),
        "q25": float(np.quantile(values, 0.25)),
        "median": float(np.median(values)),
        "q75": float(np.quantile(values, 0.75)),
        "max": float(values.max()),
        "histogram_counts": hist.tolist(),
        "histogram_edges": edges.tolist(),
    }


def compute_classification_metrics(
    probabilities: np.ndarray,
    targets: np.ndarray,
    abstention_precision: float = 0.80,
) -> dict[str, Any]:
    predictions = probabilities.argmax(axis=1)
    report = classification_report(
        targets,
        predictions,
        labels=list(range(len(CLASS_NAMES))),
        target_names=CLASS_NAMES,
        zero_division=0,
        output_dict=True,
    )
    class_thresholds, class_threshold_metrics = calibrate_class_thresholds(
        probabilities,
        targets,
        target_precision=abstention_precision,
    )
    return {
        "accuracy": float(accuracy_score(targets, predictions)),
        "macro_f1": float(f1_score(targets, predictions, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(targets, predictions, average="weighted", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(targets, predictions)),
        "ece_15_bin": expected_calibration_error(probabilities, targets),
        "multiclass_brier_score": multiclass_brier_score(probabilities, targets),
        "classification_report": report,
        "confusion_matrix": confusion_matrix(
            targets,
            predictions,
            labels=list(range(len(CLASS_NAMES))),
        ).tolist(),
        "threshold_metrics": threshold_metrics(probabilities, targets),
        "probability_distributions": probability_distributions(probabilities, targets),
        "class_thresholds": class_thresholds,
        "class_threshold_metrics": class_threshold_metrics,
        "abstention_target_precision": abstention_precision,
        "sample_count": int(len(targets)),
    }

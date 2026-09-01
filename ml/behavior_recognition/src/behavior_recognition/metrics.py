from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)

from .constants import CLASS_NAMES, PRODUCT_CLASS_NAMES, product_label


@dataclass(frozen=True)
class EventInterval:
    label: str
    start_ms: int
    end_ms: int


def _event_iou(left: EventInterval, right: EventInterval) -> float:
    intersection = max(0, min(left.end_ms, right.end_ms) - max(left.start_ms, right.start_ms))
    union = max(left.end_ms, right.end_ms) - min(left.start_ms, right.start_ms)
    return intersection / union if union > 0 else 0.0


def event_classification_report(
    reference: list[EventInterval],
    predicted: list[EventInterval],
    *,
    observed_duration_ms: int,
    minimum_iou: float = 0.30,
) -> dict[str, Any]:
    """Greedily match same-label events and report product-level outcomes."""
    matched_reference: set[int] = set()
    matched_prediction: set[int] = set()
    phone_latencies: list[int] = []
    candidates: list[tuple[float, int, int]] = []
    for reference_index, expected in enumerate(reference):
        for prediction_index, actual in enumerate(predicted):
            if expected.label != actual.label:
                continue
            overlap = _event_iou(expected, actual)
            if overlap >= minimum_iou:
                candidates.append((overlap, reference_index, prediction_index))
    for _, reference_index, prediction_index in sorted(candidates, reverse=True):
        if reference_index in matched_reference or prediction_index in matched_prediction:
            continue
        matched_reference.add(reference_index)
        matched_prediction.add(prediction_index)
        if reference[reference_index].label == "PHONE_INTERACTION":
            phone_latencies.append(max(0, predicted[prediction_index].start_ms - reference[reference_index].start_ms))

    labels = sorted({event.label for event in reference + predicted})
    per_class: dict[str, dict[str, float | int]] = {}
    f1_values: list[float] = []
    for label in labels:
        true_positive = sum(reference[index].label == label for index in matched_reference)
        predicted_count = sum(event.label == label for event in predicted)
        reference_count = sum(event.label == label for event in reference)
        precision = true_positive / predicted_count if predicted_count else 0.0
        recall = true_positive / reference_count if reference_count else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1_values.append(f1)
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": reference_count,
        }

    unmatched_phone = sum(
        event.label == "PHONE_INTERACTION" and index not in matched_prediction
        for index, event in enumerate(predicted)
    )
    observed_hours = observed_duration_ms / 3_600_000 if observed_duration_ms > 0 else 0.0
    return {
        "event_macro_f1": float(np.mean(f1_values)) if f1_values else 0.0,
        "per_class": per_class,
        "false_reminders_per_hour": unmatched_phone / observed_hours if observed_hours else float("inf"),
        "phone_detection_p95_ms": float(np.percentile(phone_latencies, 95)) if phone_latencies else None,
        "matched_event_count": len(matched_reference),
    }


def softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    scaled = np.asarray(logits, dtype=np.float64) / max(float(temperature), 1e-6)
    scaled -= scaled.max(axis=1, keepdims=True)
    exp = np.exp(scaled)
    return (exp / exp.sum(axis=1, keepdims=True)).astype(np.float32)


def negative_log_likelihood(logits: np.ndarray, labels: np.ndarray, temperature: float) -> float:
    probabilities = softmax(logits, temperature)
    selected = probabilities[np.arange(len(labels)), labels]
    return float(-np.log(np.clip(selected, 1e-12, 1.0)).mean())


def fit_temperature(logits: np.ndarray, labels: np.ndarray) -> float:
    candidates = np.geomspace(0.25, 10.0, 240)
    losses = [negative_log_likelihood(logits, labels, value) for value in candidates]
    return float(candidates[int(np.argmin(losses))])


def apply_rejection(
    probabilities: np.ndarray,
    thresholds: np.ndarray,
    margin_threshold: float,
) -> np.ndarray:
    probabilities = np.asarray(probabilities)
    order = np.argsort(probabilities, axis=1)
    top = order[:, -1]
    top_probability = probabilities[np.arange(len(probabilities)), top]
    second_probability = probabilities[np.arange(len(probabilities)), order[:, -2]]
    accepted = (top_probability >= thresholds[top]) & (
        top_probability - second_probability >= margin_threshold
    )
    return np.where(accepted, top, -1)


def expected_calibration_error(
    probabilities: np.ndarray, labels: np.ndarray, bins: int = 15
) -> float:
    confidence = probabilities.max(axis=1)
    prediction = probabilities.argmax(axis=1)
    correctness = prediction == labels
    error = 0.0
    boundaries = np.linspace(0.0, 1.0, bins + 1)
    for lower, upper in zip(boundaries[:-1], boundaries[1:]):
        selected = (confidence > lower) & (confidence <= upper)
        if selected.any():
            error += selected.mean() * abs(correctness[selected].mean() - confidence[selected].mean())
    return float(error)


def multiclass_brier_score(probabilities: np.ndarray, labels: np.ndarray) -> float:
    one_hot = np.eye(probabilities.shape[1], dtype=np.float32)[labels]
    return float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1)))


def project_product_probabilities(
    labels: np.ndarray,
    probabilities: np.ndarray,
    class_names: tuple[str, ...],
) -> tuple[np.ndarray, np.ndarray]:
    """Project source-class targets and probabilities into the product label space."""
    labels = np.asarray(labels, dtype=np.int64)
    probabilities = np.asarray(probabilities, dtype=np.float32)
    if probabilities.ndim != 2 or labels.ndim != 1 or len(labels) != len(probabilities):
        raise ValueError("labels and probabilities must contain the same number of samples")
    if probabilities.shape[1] != len(class_names):
        raise ValueError("probability columns must match the source class contract")
    if len(class_names) != len(set(class_names)) or set(class_names) != set(CLASS_NAMES):
        raise ValueError(f"source class contract must contain exactly {list(CLASS_NAMES)}")
    if labels.size and (labels.min() < 0 or labels.max() >= len(class_names)):
        raise ValueError("label index is outside the source class contract")

    product_indices = {name: index for index, name in enumerate(PRODUCT_CLASS_NAMES)}
    source_to_product = np.asarray(
        [product_indices[product_label(name)] for name in class_names],
        dtype=np.int64,
    )
    product_probabilities = np.zeros(
        (len(probabilities), len(PRODUCT_CLASS_NAMES)),
        dtype=np.float32,
    )
    for source_index, product_index in enumerate(source_to_product):
        product_probabilities[:, product_index] += probabilities[:, source_index]
    return source_to_product[labels], product_probabilities


def classification_report(
    y_true: np.ndarray, probabilities: np.ndarray, class_names: tuple[str, ...]
) -> dict:
    y_true = np.asarray(y_true, dtype=np.int64)
    probabilities = np.asarray(probabilities, dtype=np.float32)
    prediction = probabilities.argmax(axis=1)
    labels = list(range(len(class_names)))
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, prediction, labels=labels, zero_division=0
    )
    per_class = {
        name: {
            "precision": float(precision[index]),
            "recall": float(recall[index]),
            "f1": float(f1[index]),
            "support": int(support[index]),
        }
        for index, name in enumerate(class_names)
    }
    phone_index = class_names.index("PHONE_INTERACTION") if "PHONE_INTERACTION" in class_names else None
    phone_auprc = None
    if phone_index is not None and len(np.unique(y_true == phone_index)) == 2:
        phone_auprc = float(average_precision_score(y_true == phone_index, probabilities[:, phone_index]))
    return {
        "accuracy": float(accuracy_score(y_true, prediction)),
        "macro_f1": float(f1_score(y_true, prediction, labels=labels, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, prediction)),
        "phone_interaction_auprc": phone_auprc,
        "per_class": per_class,
        "confusion_matrix": confusion_matrix(y_true, prediction, labels=labels).tolist(),
        "ece": expected_calibration_error(probabilities, y_true),
        "brier_score": multiclass_brier_score(probabilities, y_true),
    }

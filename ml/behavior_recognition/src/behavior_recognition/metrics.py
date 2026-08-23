from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)


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

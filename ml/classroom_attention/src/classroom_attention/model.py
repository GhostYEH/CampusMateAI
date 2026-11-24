"""A small, dependency-light logistic regression and model artifact.

The exported artifact is the single source of truth for Android inference:
feature order, median imputation, normalization, coefficients, Platt
calibration and threshold all live here. Training, feature selection and
calibration never see the held-out participant.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .features import FEATURE_LABELS, FEATURE_SETS
from .schema import ContractError

SCHEMA_VERSION = 1


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-min(value, 40.0))
        return 1.0 / (1.0 + z)
    z = math.exp(max(value, -40.0))
    return z / (1.0 + z)


@dataclass
class TrainingRows:
    participant: list[str]
    session: list[str]
    index: list[int]
    y: np.ndarray
    X: np.ndarray
    durations_ms: np.ndarray
    rows: list[dict[str, Any]]


def rows_to_matrix(
    rows: Iterable[dict[str, Any]],
    features: tuple[str, ...],
) -> tuple[np.ndarray, np.ndarray]:
    data: list[list[float]] = []
    labels: list[int] = []
    for row in rows:
        values = row.get("features", {})
        data.append([math.nan if values.get(name) is None else float(values[name]) for name in features])
        labels.append(1 if row.get("label") == "off_task" else 0)
    return np.asarray(data, dtype=float), np.asarray(labels, dtype=float)


def training_rows(
    rows: Iterable[dict[str, Any]],
    feature_set: str,
) -> TrainingRows:
    """Only observable, on/off-labelled windows enter supervised training."""
    features = FEATURE_SETS[feature_set]
    selected = [
        row
        for row in rows
        if row.get("label") in ("on_task", "off_task")
        and row.get("complete", True)
        and row.get("observable")
        and row.get("label_status", "labelled") == "labelled"
    ]
    if not selected:
        raise ContractError("训练折没有可用的 on_task/off_task 窗口")
    X, y = rows_to_matrix(selected, features)
    return TrainingRows(
        participant=[row["participant_id"] for row in selected],
        session=[row["session_id"] for row in selected],
        index=[int(row["index"]) for row in selected],
        y=y,
        X=X,
        durations_ms=np.asarray([float(row.get("duration_ms", 10_000)) for row in selected]),
        rows=selected,
    )


def median_impute(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    impute = np.zeros(X.shape[1], dtype=float)
    for column in range(X.shape[1]):
        values = X[:, column]
        good = values[~np.isnan(values)]
        impute[column] = float(np.median(good)) if good.size else 0.0
    filled = X.copy()
    for column in range(X.shape[1]):
        mask = np.isnan(filled[:, column])
        filled[mask, column] = impute[column]
    return filled, impute


def mean_std(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = X.mean(axis=0)
    std = X.std(axis=0, ddof=0)
    std[std < 1e-8] = 1.0
    return mean, std


def effect_sizes(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Absolute standardized mean difference per feature."""
    result = np.zeros(X.shape[1], dtype=float)
    for column in range(X.shape[1]):
        positive = X[y == 1, column]
        negative = X[y == 0, column]
        if positive.size == 0 or negative.size == 0:
            continue
        pooled = math.sqrt(
            (positive.var(ddof=0) + negative.var(ddof=0)) / 2.0
        ) or 1.0
        result[column] = abs(float(positive.mean() - negative.mean()) / pooled)
    return result


def select_features(
    X: np.ndarray,
    y: np.ndarray,
    names: tuple[str, ...],
    *,
    min_effect: float = 0.15,
    minimum: int = 4,
) -> list[int]:
    scores = effect_sizes(X, y)
    keep = [index for index, score in enumerate(scores) if score >= min_effect]
    if len(keep) < minimum:
        keep = list(np.argsort(-scores)[: min(minimum, len(names))])
    return sorted(keep)


def fit_logistic(
    X: np.ndarray,
    y: np.ndarray,
    *,
    l2: float = 1e-3,
    learning_rate: float = 0.35,
    iterations: int = 700,
) -> tuple[np.ndarray, float]:
    n, d = X.shape
    weights = np.zeros(d, dtype=float)
    positives = float(y.sum())
    negatives = float(n - positives)
    if positives == 0 or negatives == 0:
        base = positives / n
        base = min(max(base, 1e-4), 1 - 1e-4)
        return weights, math.log(base / (1 - base))
    sample_weight = np.where(y > 0, n / (2.0 * positives), n / (2.0 * negatives))
    intercept = math.log(positives / negatives)
    for _ in range(iterations):
        logits = X @ weights + intercept
        probabilities = 1.0 / (1.0 + np.exp(-np.clip(logits, -40, 40)))
        residual = (probabilities - y) * sample_weight
        gradient = X.T @ residual / n + l2 * weights
        gradient_intercept = float(residual.sum() / n)
        weights -= learning_rate * gradient
        intercept -= learning_rate * gradient_intercept
    return weights, float(intercept)


def fit_platt(logits: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Fit p = sigmoid(a * logit + b) on training-fold out-of-fold logits."""
    if len(logits) == 0 or y.min() == y.max():
        return 1.0, 0.0
    a, b = 1.0, 0.0
    learning_rate = 0.05
    for _ in range(800):
        probabilities = 1.0 / (1.0 + np.exp(-np.clip(a * logits + b, -40, 40)))
        residual = probabilities - y
        gradient_a = float(np.mean(residual * logits))
        gradient_b = float(np.mean(residual))
        a -= learning_rate * gradient_a
        b -= learning_rate * gradient_b
    return float(a), float(b)


def predict_logit(
    values: dict[str, Any],
    feature_order: list[str],
    impute: dict[str, float],
    normalization: dict[str, dict[str, float]],
    coefficients: list[float],
    intercept: float,
) -> float:
    logit = intercept
    for name, coefficient in zip(feature_order, coefficients):
        raw = values.get(name)
        value = float(impute[name]) if raw is None else float(raw)
        stats = normalization[name]
        normalized = (value - float(stats["mean"])) / float(stats["std"] or 1.0)
        logit += coefficient * normalized
    return min(max(logit, -40.0), 40.0)


def predict_probability(logit: float, calibration: dict[str, Any]) -> float:
    if calibration.get("type") == "platt":
        return sigmoid(float(calibration.get("a", 1.0)) * logit + float(calibration.get("b", 0.0)))
    return sigmoid(logit)


def build_model(
    rows: list[dict[str, Any]],
    *,
    feature_set: str,
    model_version: str,
    calibration: tuple[float, float],
    threshold: float,
    training_metadata: dict[str, Any],
    release: dict[str, Any],
) -> dict[str, Any]:
    """Fit on all provided rows (a training fold) and return the artifact."""
    if feature_set not in FEATURE_SETS:
        raise ContractError(f"未知 feature_set: {feature_set}")
    prepared = training_rows(rows, feature_set)
    names = FEATURE_SETS[feature_set]
    filled, impute = median_impute(prepared.X)
    selected = select_features(filled, prepared.y, names)
    X = filled[:, selected]
    mean, std = mean_std(X)
    X = (X - mean) / std
    coefficients, intercept = fit_logistic(X, prepared.y)
    feature_order = [names[index] for index in selected]
    a, b = calibration
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": model_version,
        "feature_set": feature_set,
        "feature_order": feature_order,
        "feature_labels": {name: FEATURE_LABELS[name] for name in feature_order},
        "missing_policy": "median_impute",
        "impute": {name: float(impute[index]) for name, index in zip(names, range(len(names)))},
        "normalization": {
            name: {"mean": float(mean[position]), "std": float(std[position])}
            for position, name in enumerate(feature_order)
        },
        "coefficients": [float(value) for value in coefficients],
        "intercept": float(intercept),
        "calibration": {"type": "platt", "a": float(a), "b": float(b)},
        "decision_threshold": float(threshold),
        "coverage_gate": {"min_valid_coverage": 0.5, "min_face_visible_ratio": 0.2},
        "training": training_metadata,
        "release": release,
    }


def oof_logits(
    rows: list[dict[str, Any]],
    feature_set: str,
    participants: list[str],
    *,
    folds: int = 5,
) -> tuple[np.ndarray, np.ndarray]:
    """Out-of-fold logits inside the training fold, grouped by participant."""
    prepared = training_rows(rows, feature_set)
    names = FEATURE_SETS[feature_set]
    unique = sorted(set(prepared.participant))
    fold_count = min(folds, len(unique))
    if fold_count < 2:
        return np.zeros(len(prepared.y)), prepared.y
    assignment = {participant: position % fold_count for position, participant in enumerate(unique)}
    logits = np.zeros(len(prepared.y), dtype=float)
    for fold in range(fold_count):
        train_mask = np.asarray(
            [assignment[participant] != fold for participant in prepared.participant]
        )
        test_mask = ~train_mask
        if not test_mask.any():
            continue
        filled, impute = median_impute(prepared.X[train_mask])
        selected = select_features(filled, prepared.y[train_mask], names)
        X_train = filled[:, selected]
        mean, std = mean_std(X_train)
        X_train = (X_train - mean) / std
        coefficients, intercept = fit_logistic(X_train, prepared.y[train_mask])
        X_test = prepared.X[test_mask][:, selected].copy()
        for column, index in enumerate(selected):
            mask = np.isnan(X_test[:, column])
            X_test[mask, column] = impute[index]
        X_test = (X_test - mean) / std
        logits[test_mask] = X_test @ coefficients + intercept
    return logits, prepared.y


def predict_rows(model: dict[str, Any], rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    feature_order = model["feature_order"]
    impute = model["impute"]
    normalization = model["normalization"]
    coefficients = model["coefficients"]
    results: list[dict[str, Any]] = []
    for row in rows:
        logit = predict_logit(
            row.get("features", {}),
            feature_order,
            impute,
            normalization,
            coefficients,
            model["intercept"],
        )
        probability = predict_probability(logit, model["calibration"])
        results.append(
            {
                "participant_id": row["participant_id"],
                "session_id": row["session_id"],
                "window_index": row["index"],
                "start_offset_ms": row["start_offset_ms"],
                "duration_ms": row.get("duration_ms", 10_000),
                "label": row.get("label"),
                "observable": bool(row.get("observable")),
                "dominant_stage": row.get("dominant_stage"),
                "logit": logit,
                "probability": probability,
                "predicted": "off_task" if probability >= model["decision_threshold"] else "on_task",
            }
        )
    return results


def save_model(path: Path, model: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(model, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_model(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"模型 schema_version 不是 {SCHEMA_VERSION}")
    required = {
        "model_version",
        "feature_set",
        "feature_order",
        "feature_labels",
        "missing_policy",
        "impute",
        "normalization",
        "coefficients",
        "intercept",
        "calibration",
        "decision_threshold",
        "coverage_gate",
        "release",
    }
    missing = required - set(payload)
    if missing:
        raise ContractError(f"模型缺少字段: {sorted(missing)}")
    if len(payload["feature_order"]) != len(payload["coefficients"]):
        raise ContractError("模型特征数与系数数不一致")
    if payload["missing_policy"] != "median_impute":
        raise ContractError("只支持 median_impute 缺失值策略")
    return payload

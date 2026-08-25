from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar
from sklearn.metrics import accuracy_score, precision_recall_curve

from .constants import CLASS_NAMES
from .metrics import calibrate_class_thresholds, expected_calibration_error, multiclass_brier_score


PER_CLASS_PRECISION_TARGETS = {
    "angry": 0.90,
    "disgust": 0.90,
    "fear": 0.90,
    "happy": 0.85,
    "neutral": 0.85,
    "sad": 0.90,
    "surprise": 0.85,
}


def softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    values = np.exp(shifted)
    return values / values.sum(axis=1, keepdims=True)


def nll(probabilities: np.ndarray, targets: np.ndarray) -> float:
    return float(-np.log(np.clip(probabilities[np.arange(len(targets)), targets], 1e-8, 1.0)).mean())


def fit_temperature(probabilities: np.ndarray, targets: np.ndarray) -> float:
    logits = np.log(np.clip(probabilities, 1e-8, 1.0))

    def objective(log_temperature: float) -> float:
        return nll(softmax(logits / np.exp(log_temperature)), targets)

    result = minimize_scalar(objective, bounds=(-2.0, 2.0), method="bounded", options={"xatol": 1e-4})
    return float(np.exp(result.x))


def coverage_rows(probabilities: np.ndarray, targets: np.ndarray, label: str) -> list[dict]:
    rows = []
    confidence = probabilities.max(axis=1)
    predictions = probabilities.argmax(axis=1)
    for threshold in np.arange(0.20, 0.96, 0.05):
        accepted = confidence >= threshold
        rows.append({
            "strategy": label,
            "threshold": round(float(threshold), 2),
            "coverage": float(accepted.mean()),
            "accuracy_when_covered": float(accuracy_score(targets[accepted], predictions[accepted])) if accepted.any() else None,
            "sample_count": int(accepted.sum()),
        })
    return rows


def choose_threshold(probabilities: np.ndarray, targets: np.ndarray, target_precision: float = 0.80) -> float:
    confidence = probabilities.max(axis=1)
    predictions = probabilities.argmax(axis=1)
    candidates = np.arange(0.20, 0.96, 0.01)
    feasible = []
    for threshold in candidates:
        accepted = confidence >= threshold
        if not accepted.any():
            continue
        precision = float((predictions[accepted] == targets[accepted]).mean())
        if precision >= target_precision:
            feasible.append((int(accepted.sum()), float(threshold), precision))
    if feasible:
        return max(feasible, key=lambda row: (row[0], -row[1]))[1]
    return 0.70


def calibrate(args: argparse.Namespace) -> None:
    validation = np.load(args.validation_predictions)
    test = np.load(args.test_predictions)
    val_probabilities = validation["probabilities"]
    val_targets = validation["targets"].astype(int)
    test_probabilities = test["probabilities"]
    test_targets = test["targets"].astype(int)
    temperature = fit_temperature(val_probabilities, val_targets)
    val_calibrated = softmax(np.log(np.clip(val_probabilities, 1e-8, 1.0)) / temperature)
    test_calibrated = softmax(np.log(np.clip(test_probabilities, 1e-8, 1.0)) / temperature)
    threshold = choose_threshold(val_calibrated, val_targets)
    class_thresholds, class_diagnostics = calibrate_class_thresholds(
        val_calibrated,
        val_targets,
        target_precision=PER_CLASS_PRECISION_TARGETS,
        minimum_accepted=int(getattr(args, "minimum_accepted_per_class", 25)),
    )
    thresholds = {
        "selection_split": "validation",
        "strategy": "temperature_scaled_confidence",
        "temperature": temperature,
        "uniform_confidence_threshold": threshold,
        "class_order": CLASS_NAMES,
        "per_class_thresholds": class_thresholds,
        "per_class_precision_targets": PER_CLASS_PRECISION_TARGETS,
        "per_class_enabled": {
            name: bool(class_diagnostics[name]["enabled"])
            for name in CLASS_NAMES
        },
        "per_class_diagnostics": class_diagnostics,
        "unknown_policy": "abstain when top-1 confidence is below its class threshold or the class is disabled",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "thresholds.json").write_text(json.dumps(thresholds, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = coverage_rows(val_calibrated, val_targets, "validation_temperature_scaled")
    rows.extend(coverage_rows(test_calibrated, test_targets, "test_temperature_scaled_locked"))
    with (args.output_dir / "coverage_accuracy.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    pr_rows = []
    for index, name in enumerate(CLASS_NAMES):
        binary_targets = (val_targets == index).astype(int)
        if not binary_targets.any():
            continue
        precision, recall, thresholds_pr = precision_recall_curve(binary_targets, val_calibrated[:, index])
        for precision_value, recall_value, threshold_value in zip(precision[:-1], recall[:-1], thresholds_pr):
            pr_rows.append({"class": name, "precision": float(precision_value), "recall": float(recall_value), "threshold": float(threshold_value)})
    with (args.output_dir / "per_class_precision_recall.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["class", "precision", "recall", "threshold"])
        writer.writeheader()
        writer.writerows(pr_rows)

    def locked_metrics(probabilities: np.ndarray, targets: np.ndarray) -> dict:
        confidence = probabilities.max(axis=1)
        predictions = probabilities.argmax(axis=1)
        required = np.asarray([class_thresholds[CLASS_NAMES[index]] for index in predictions])
        accepted = confidence >= required
        return {
            "coverage": float(accepted.mean()),
            "accuracy_when_covered": float((predictions[accepted] == targets[accepted]).mean()) if accepted.any() else None,
            "accepted_count": int(accepted.sum()),
            "sample_count": int(len(targets)),
            "ece_15_bin": expected_calibration_error(probabilities, targets),
            "multiclass_brier_score": multiclass_brier_score(probabilities, targets),
        }

    report = {
        "model": args.model,
        "validation": {
            "temperature": temperature,
            "nll_before": nll(val_probabilities, val_targets),
            "nll_after": nll(val_calibrated, val_targets),
            "ece_before": expected_calibration_error(val_probabilities, val_targets),
            "ece_after": expected_calibration_error(val_calibrated, val_targets),
            "locked_threshold": threshold,
            "locked_metrics": locked_metrics(val_calibrated, val_targets),
        },
        "test_once_after_lock": locked_metrics(test_calibrated, test_targets),
        "selection_rule": "temperature and confidence threshold selected on validation only; test used once after lock",
    }
    (args.output_dir / "calibration.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Calibration report",
        "",
        "Temperature scaling and threshold selection were performed on validation only.",
        "The test row is a single locked evaluation and was not used for selection.",
        "",
        "```json",
        json.dumps(report, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    (args.output_dir / "calibration_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validation-predictions", type=Path, required=True)
    parser.add_argument("--test-predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default="resnet18")
    parser.add_argument("--minimum-accepted-per-class", type=int, default=25)
    calibrate(parser.parse_args())


if __name__ == "__main__":
    main()

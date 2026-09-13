from __future__ import annotations

import pytest

from learner_state_evaluation.metrics import evaluate_predictions


def annotation(sample_id: str, code: str, label: bool, sufficient: bool = True) -> dict:
    return {
        "sample_id": sample_id,
        "scenario_code": code,
        "label": label,
        "evidence": {"attempt_count": 2 if sufficient else 1, "supports_assertion": sufficient},
    }


def prediction(sample_id: str, label: bool, score: float) -> dict:
    return {"sample_id": sample_id, "predicted_label": label, "score": score}


def test_binary_metrics_and_per_scenario_counts_are_hand_checkable() -> None:
    annotations = [
        annotation("1", "deadline_risk", True),
        annotation("2", "deadline_risk", False),
        annotation("3", "deadline_risk", False),
        annotation("4", "schedule_conflict", True),
        annotation("5", "schedule_conflict", True),
        annotation("6", "schedule_conflict", False),
    ]
    predictions = [
        prediction("1", True, 0.9),
        prediction("2", True, 0.8),
        prediction("3", False, 0.2),
        prediction("4", True, 0.7),
        prediction("5", False, 0.4),
        prediction("6", False, 0.1),
    ]

    report = evaluate_predictions(annotations, predictions, calibration_bins=2)

    assert report["counts"] == {"tp": 2, "fp": 1, "tn": 2, "fn": 1}
    assert report["precision"] == pytest.approx(2 / 3)
    assert report["recall"] == pytest.approx(2 / 3)
    assert report["f1"] == pytest.approx(2 / 3)
    assert report["per_scenario"]["deadline_risk"]["counts"] == {
        "tp": 1,
        "fp": 1,
        "tn": 1,
        "fn": 0,
    }


def test_brier_and_ece_use_positive_class_score() -> None:
    annotations = [annotation("1", "deadline_risk", True), annotation("2", "deadline_risk", False)]
    predictions = [prediction("1", True, 0.8), prediction("2", False, 0.3)]

    report = evaluate_predictions(annotations, predictions, calibration_bins=2)

    assert report["brier_score"] == pytest.approx(0.065)
    assert report["ece"] == pytest.approx(0.25)
    assert report["roc_auc"] == 1.0


def test_zero_denominators_are_reported_as_zero() -> None:
    annotations = [annotation("1", "deadline_risk", False)]
    predictions = [prediction("1", False, 0.1)]

    report = evaluate_predictions(annotations, predictions)

    assert report["precision"] == 0.0
    assert report["recall"] == 0.0
    assert report["f1"] == 0.0
    assert report["roc_auc"] is None


def test_positive_prediction_with_single_attempt_counts_as_unsupported_assertion() -> None:
    annotations = [annotation("1", "deadline_risk", False, sufficient=False)]
    predictions = [prediction("1", True, 0.8)]

    report = evaluate_predictions(annotations, predictions)

    assert report["unsupported_assertion_count"] == 1
    assert report["unsupported_assertion_rate"] == 1.0

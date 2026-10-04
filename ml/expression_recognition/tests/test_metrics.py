import numpy as np

from expression_recognition.metrics import (
    compute_classification_metrics,
    expected_calibration_error,
    threshold_metrics,
)


def test_perfect_predictions_have_perfect_primary_metrics():
    targets = np.arange(7)
    probabilities = np.eye(7) * 0.9 + (np.ones((7, 7)) - np.eye(7)) * (0.1 / 6)
    result = compute_classification_metrics(probabilities, targets)
    assert result["accuracy"] == 1.0
    assert result["macro_f1"] == 1.0
    assert result["balanced_accuracy"] == 1.0
    assert expected_calibration_error(probabilities, targets) == pytest.approx(0.1)


def test_threshold_coverage_is_monotonic():
    probabilities = np.array([[0.7, 0.3], [0.55, 0.45], [0.4, 0.6]])
    targets = np.array([0, 1, 1])
    rows = threshold_metrics(probabilities, targets, [0.5, 0.6, 0.8])
    assert [row["coverage"] for row in rows] == [1.0, 2 / 3, 0.0]


def test_locked_metrics_do_not_select_thresholds_from_test_labels(monkeypatch):
    def forbidden_calibration(*args, **kwargs):
        raise AssertionError("Locked evaluation must not fit thresholds")

    monkeypatch.setattr("expression_recognition.metrics.calibrate_class_thresholds", forbidden_calibration)
    result = compute_classification_metrics(np.eye(7), np.arange(7), calibrate_abstention=False)
    assert result["accuracy"] == 1.0
    assert result["macro_f1"] == 1.0
    assert "class_thresholds" not in result
    assert "class_threshold_metrics" not in result
    assert "abstention_target_precision" not in result


def test_validation_metrics_still_calibrate_thresholds():
    result = compute_classification_metrics(np.eye(7), np.arange(7))
    assert set(result["class_thresholds"]) == {
        "angry", "disgust", "fear", "happy", "neutral", "sad", "surprise",
    }


import pytest

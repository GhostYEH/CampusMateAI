import numpy as np
import pytest

from behavior_recognition.constants import CLASS_NAMES
from behavior_recognition.metrics import (
    apply_rejection,
    classification_report,
    fit_temperature,
    project_product_probabilities,
)
from behavior_recognition.calibrate import search_rejection_thresholds


def test_low_margin_prediction_is_rejected():
    """Catches ambiguous probabilities being forced into a behavior class."""
    probabilities = np.array([[0.36, 0.34, 0.20, 0.10]], dtype=np.float32)
    result = apply_rejection(
        probabilities,
        thresholds=np.array([0.4, 0.4, 0.4, 0.4]),
        margin_threshold=0.08,
    )
    assert result.tolist() == [-1]


def test_classification_report_exposes_per_class_and_calibration_metrics():
    """Catches aggregate accuracy hiding a failed minority class."""
    y_true = np.array([0, 1, 2, 3])
    probabilities = np.array(
        [
            [0.8, 0.1, 0.05, 0.05],
            [0.1, 0.7, 0.1, 0.1],
            [0.1, 0.1, 0.7, 0.1],
            [0.1, 0.1, 0.2, 0.6],
        ],
        dtype=np.float32,
    )
    report = classification_report(y_true, probabilities, ("A", "B", "C", "D"))
    assert report["accuracy"] == 1.0
    assert report["macro_f1"] == 1.0
    assert report["balanced_accuracy"] == 1.0
    assert report["per_class"]["D"]["support"] == 1
    assert report["confusion_matrix"] == [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    assert 0.0 <= report["ece"] <= 1.0
    assert report["brier_score"] > 0.0


def test_temperature_fit_reduces_overconfident_nll():
    """Catches calibration returning an invalid or counterproductive temperature."""
    logits = np.array([[8.0, 0.0], [8.0, 0.0], [0.0, 8.0]], dtype=np.float32)
    labels = np.array([0, 1, 1])
    temperature = fit_temperature(logits, labels)
    assert temperature > 1.0


def test_rejection_search_returns_valid_threshold_contract():
    """Catches calibration emitting thresholds Android cannot apply."""
    probabilities = np.eye(4, dtype=np.float32) * 0.8 + 0.05
    labels = np.arange(4)
    result = search_rejection_thresholds(probabilities, labels, min_coverage=0.75)
    assert len(result["class_thresholds"]) == 4
    assert 0.0 <= result["margin_threshold"] <= 1.0
    assert result["coverage"] >= 0.75


def test_product_projection_sums_read_and_write_before_argmax():
    """Catches collapsing source Top-1 instead of summing product probabilities."""
    labels = np.array([0, 2])
    probabilities = np.array(
        [
            [0.31, 0.30, 0.39, 0.00],
            [0.10, 0.10, 0.70, 0.10],
        ],
        dtype=np.float32,
    )

    product_labels, product_probabilities = project_product_probabilities(
        labels,
        probabilities,
        CLASS_NAMES,
    )

    assert product_labels.tolist() == [0, 1]
    np.testing.assert_allclose(
        product_probabilities,
        np.array([[0.61, 0.39, 0.00], [0.20, 0.70, 0.10]], dtype=np.float32),
    )


def test_product_projection_rejects_incomplete_source_contract():
    """Catches silently evaluating probabilities with a missing trainable class."""
    with pytest.raises(ValueError, match="source class contract"):
        project_product_probabilities(
            np.array([0]),
            np.array([[0.8, 0.1, 0.1]], dtype=np.float32),
            ("READ", "WRITE", "PHONE_INTERACTION"),
        )

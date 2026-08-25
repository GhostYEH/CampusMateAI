import numpy as np
from argparse import Namespace

from expression_recognition.calibrate import calibrate
from expression_recognition.metrics import calibrate_class_thresholds


def test_class_is_disabled_when_precision_target_is_unreachable() -> None:
    probabilities = np.array([
        [0.90, 0.10, 0, 0, 0, 0, 0],
        [0.80, 0.20, 0, 0, 0, 0, 0],
        [0.70, 0.30, 0, 0, 0, 0, 0],
    ])
    targets = np.array([0, 1, 1])

    thresholds, diagnostics = calibrate_class_thresholds(
        probabilities,
        targets,
        target_precision={"angry": 0.90},
        thresholds=[0.70, 0.80, 0.90],
        minimum_accepted=2,
    )

    assert thresholds["angry"] > 1.0
    assert diagnostics["angry"]["enabled"] is False
    assert diagnostics["angry"]["met_target_precision"] is False


def test_per_class_precision_targets_select_most_coverage() -> None:
    probabilities = np.array([
        [0.95, 0.05, 0, 0, 0, 0, 0],
        [0.85, 0.15, 0, 0, 0, 0, 0],
        [0.75, 0.25, 0, 0, 0, 0, 0],
        [0.10, 0.90, 0, 0, 0, 0, 0],
    ])
    targets = np.array([0, 0, 1, 1])

    thresholds, diagnostics = calibrate_class_thresholds(
        probabilities,
        targets,
        target_precision={"angry": 0.90, "disgust": 0.80},
        thresholds=[0.70, 0.80, 0.90],
        minimum_accepted=1,
    )

    assert thresholds["angry"] == 0.80
    assert diagnostics["angry"]["accepted_count"] == 2
    assert diagnostics["angry"]["enabled"] is True
    assert thresholds["disgust"] == 0.70


def test_calibration_artifact_contains_precision_first_class_gates(tmp_path) -> None:
    probabilities = np.array([
        [0.95, 0.01, 0.01, 0.01, 0.01, 0.00, 0.01],
        [0.85, 0.01, 0.01, 0.01, 0.01, 0.10, 0.01],
        [0.75, 0.01, 0.01, 0.01, 0.01, 0.20, 0.01],
    ])
    targets = np.array([0, 5, 5])
    validation = tmp_path / "validation.npz"
    test = tmp_path / "test.npz"
    np.savez(validation, probabilities=probabilities, targets=targets)
    np.savez(test, probabilities=probabilities, targets=targets)
    output = tmp_path / "output"

    calibrate(Namespace(
        validation_predictions=validation,
        test_predictions=test,
        output_dir=output,
        model="fixture",
        minimum_accepted_per_class=2,
    ))

    import json
    artifact = json.loads((output / "thresholds.json").read_text(encoding="utf-8"))
    assert artifact["per_class_precision_targets"]["sad"] == 0.90
    assert artifact["per_class_enabled"]["sad"] is False
    assert artifact["per_class_thresholds"]["sad"] > 1.0

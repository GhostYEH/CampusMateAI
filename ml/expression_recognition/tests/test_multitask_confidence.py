import numpy as np
import pytest
import torch

from expression_recognition.multitask_confidence import (
    LABEL_NAMES, POSITIVE_DEFINITION, calibrate_checkpoint, confidence_probabilities, fit_confidence_calibration,
)


def test_three_states_can_all_have_high_probability_without_competing_with_expressions():
    output = {"expression_logits": torch.tensor([[0., 0., 0., 0., 9., 0., 0.]]),
              "state_logits": torch.tensor([[6., 5., 4.]])}
    probabilities = confidence_probabilities(output)
    assert probabilities.shape == (1, 10)
    assert probabilities[0, 4] > .99
    assert torch.all(probabilities[0, 7:] > .98)
    assert probabilities[0, :7].sum().item() == pytest.approx(1)
    assert probabilities.sum().item() > 3.9


def test_validation_fit_corrects_overconfidence_without_changing_expression_ranking():
    # Confident half-right predictions should receive a higher temperature.
    expressions = np.tile([8., 0., 0., 0., 0., 0., 0.], (40, 1))
    targets = np.tile([0, 1], 20)
    states = np.tile(np.linspace(-2, 2, 40)[:, None] + 3., (1, 3))
    state_targets = np.tile((np.arange(40) >= 20)[:, None], (1, 3)).astype(np.int64)
    calibration = fit_confidence_calibration(expressions, targets, states, state_targets)
    assert calibration["expression_temperature"] > 1
    assert calibration["validation_nll_after"] < calibration["validation_nll_before"]
    assert calibration["fitted_on"] == "validation"
    assert all(item["fitted"] for item in calibration["state_fit"])
    assert all(scale >= 0 for scale in calibration["state_scales"])
    output = {"expression_logits": torch.tensor(expressions), "state_logits": torch.tensor(states)}
    probabilities = confidence_probabilities(output, calibration)
    assert torch.isfinite(probabilities).all()
    assert probabilities[:, :7].argmax(-1).eq(0).all()
    assert probabilities[0, 7:].max() < .5
    assert probabilities[-1, 7:].min() > .5


def test_one_class_validation_is_marked_uncalibrated_and_inverted_scores_are_constant():
    expressions = np.zeros((12, 7))
    labels = np.arange(12) % 7
    states = np.tile(np.arange(12)[:, None], (1, 3))
    targets = np.stack([np.zeros(12), np.arange(12) < 6, np.arange(12) >= 6], 1)
    calibration = fit_confidence_calibration(expressions, labels, states, targets)
    assert calibration["state_fit"][0]["fitted"] is False
    assert calibration["state_scales"][0] == 1
    assert calibration["state_scales"][1] == 0
    assert calibration["state_biases"][1] == pytest.approx(0)


def test_calibration_rejects_wrong_labels_nonfinite_values_and_reordered_contract():
    with pytest.raises(ValueError):
        fit_confidence_calibration(np.zeros((2, 7)), np.array([0, 7]), np.zeros((2, 3)), np.zeros((2, 3)))
    with pytest.raises(ValueError):
        fit_confidence_calibration(np.full((2, 7), np.nan), np.array([0, 1]), np.zeros((2, 3)), np.zeros((2, 3)))
    calibration = {"label_order": list(reversed(LABEL_NAMES))}
    with pytest.raises(ValueError, match="label order"):
        confidence_probabilities({"expression_logits": torch.zeros(1, 7), "state_logits": torch.zeros(1, 3)}, calibration)


@pytest.mark.parametrize("split,source_digest,message", [
    ("test", "unused", "never test"), ("validation", "wrong", "different checkpoint"),
])
def test_calibration_rejects_test_predictions_and_mismatched_model(tmp_path, monkeypatch, split, source_digest, message):
    from expression_recognition.multitask_model import MultitaskExpressionStateModel

    monkeypatch.setattr(MultitaskExpressionStateModel, "from_checkpoint", lambda path: None)
    source = tmp_path / "source.pt"
    source.write_bytes(b"locked-model")
    predictions = tmp_path / "predictions.npz"
    np.savez(predictions, split=np.array(split), checkpoint_sha256=np.array(source_digest),
             state_positive_definition=np.array(POSITIVE_DEFINITION))
    target = tmp_path / "calibrated.pt"
    with pytest.raises(ValueError, match=message):
        calibrate_checkpoint(source, predictions, target)
    assert not target.exists()

import numpy as np
import pytest
import torch

from expression_recognition.export_multitask_mobile import (
    NhwcMultitaskLogits,
    calibrate_validation_thresholds,
    validate_mobile_export_checkpoint,
)
from expression_recognition.multitask_confidence import LABEL_NAMES, confidence_probabilities
from expression_recognition.multitask_model import MultiTaskExpressionModel
from test_multitask_model import TinyResNet, _config


def _calibration():
    return {
        "label_order": LABEL_NAMES,
        "expression_temperature": 1.0471285480508996,
        "state_scales": [0.6608489616943151, 0.8023012756049598, 0.5501442230714629],
        "state_biases": [-0.11038139222478235, -1.8821206392472292, -1.8834415679743548],
        "positive_definition": "DAiSEE level >= 2",
        "fitted_on": "validation",
        "source_checkpoint_sha256": "source-digest",
        "predictions_sha256": "unused",
    }


def test_per_frame_raw_logits_reproduce_calibrated_four_frame_clip():
    torch.manual_seed(29)
    model = MultiTaskExpressionModel(TinyResNet(), _config()).eval()
    wrapper = NhwcMultitaskLogits(model).eval()
    calibration = _calibration()
    frames = torch.randn(1, 4, 3, 96, 96)
    with torch.inference_mode():
        clip = model(frames)
        frame_logits = wrapper(frames[0].permute(0, 2, 3, 1).contiguous())
        torch_clip = confidence_probabilities(clip, calibration)
        frame_mean = frame_logits.mean(dim=0, keepdim=True)
        mobile_logits = {"expression_logits": frame_mean[:, :7], "state_logits": frame_mean[:, 7:]}
        mobile_clip = confidence_probabilities(mobile_logits, calibration)
    torch.testing.assert_close(mobile_clip, torch_clip, rtol=1e-6, atol=1e-7)


def test_threshold_export_rejects_test_predictions_even_when_hashes_match(tmp_path):
    from expression_recognition.learning_state_experiment import file_digest

    path = tmp_path / "predictions.npz"
    np.savez(path, split=np.array("test"), checkpoint_sha256=np.array("source-digest"),
             expression_logits=np.zeros((7, 7)), expression_targets=np.arange(7))
    calibration = _calibration()
    calibration["predictions_sha256"] = file_digest(path)
    with pytest.raises(ValueError, match="only be derived from validation"):
        calibrate_validation_thresholds({"confidence_calibration": calibration}, path)


@pytest.mark.parametrize("checkpoint", [
    {"candidate_only": False, "expression_guard_passed": True},
    {"selection_split": "test", "candidate_only": False, "expression_guard_passed": True},
    {"selection_split": "validation", "candidate_only": True, "expression_guard_passed": True},
    {"selection_split": "validation", "candidate_only": False, "expression_guard_passed": False},
])
def test_mobile_export_requires_explicit_validation_selected_guarded_checkpoint(checkpoint):
    with pytest.raises(ValueError):
        validate_mobile_export_checkpoint(checkpoint)

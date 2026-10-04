import numpy as np
import pytest
import torch
from torch import nn

from expression_recognition.constants import CLASS_NAMES
from expression_recognition.learning_state_model import (
    FrozenExpressionLearningStateModel,
    STATE_NAMES,
    learning_state_metrics,
    validate_expression_contract,
)
from expression_recognition.models import build_model


@pytest.fixture(autouse=True)
def _limit_torch_threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        yield
    finally:
        torch.set_num_threads(previous)


def _config(**overrides):
    config = {
        "model": "resnet18",
        "input_size": 96,
        "input_channels": 3,
        "normalization": {
            "mean": [0.485, 0.456, 0.406],
            "std": [0.229, 0.224, 0.225],
        },
        "class_names": CLASS_NAMES.copy(),
        "pretrained": False,
    }
    config.update(overrides)
    return config


def test_extension_preserves_original_single_image_expression_output_and_frozen_state():
    torch.manual_seed(17)
    config = _config()
    original = build_model(config, allow_download=False).eval()
    inputs = torch.randn(2, 3, 96, 96)
    with torch.no_grad():
        expected = original(inputs)
    original_state = {key: value.clone() for key, value in original.state_dict().items()}

    model = FrozenExpressionLearningStateModel(original, config)
    model.train()
    result = model(inputs)

    assert tuple(result["expression_logits"].shape) == (2, 7)
    assert tuple(result["state_logits"].shape) == (2, 3, 4)
    torch.testing.assert_close(result["expression_logits"], expected, rtol=0, atol=0)
    assert not model.backbone.training
    assert all(not parameter.requires_grad for parameter in model.backbone.parameters())
    for name, value in model.backbone.state_dict().items():
        torch.testing.assert_close(value, original_state[name], rtol=0, atol=0)
    assert any(parameter.requires_grad for parameter in model.state_heads.parameters())


def test_video_pools_features_and_original_expression_logits_over_frames():
    class TinyBackbone(nn.Module):
        """Small deterministic ResNet-shaped fixture with visible frame values."""

        def __init__(self):
            super().__init__()
            self.projection = nn.Conv2d(3, 512, 1, bias=False)
            self.pool = nn.AdaptiveAvgPool2d(1)
            self.fc = nn.Linear(512, 7)
            with torch.no_grad():
                self.projection.weight.zero_()
                self.projection.weight[:3, :, 0, 0] = torch.eye(3)
                self.fc.weight.zero_()
                self.fc.bias.zero_()
                self.fc.weight[:, :3] = torch.arange(21, dtype=torch.float32).reshape(7, 3)

        def children(self):
            return iter((self.projection, self.pool, self.fc))

    model = FrozenExpressionLearningStateModel(TinyBackbone(), _config())
    frames = torch.zeros(2, 3, 3, 96, 96)
    for frame in range(frames.shape[1]):
        frames[:, frame] = float(frame + 1)
    frame_logits = []
    for frame in frames.unbind(1):
        features = model.backbone.pool(model.backbone.projection(frame)).flatten(1)
        frame_logits.append(model.backbone.fc(features))
    frame_logits = torch.stack(frame_logits, dim=1)

    result = model(frames)

    expected_features = torch.zeros(2, 512)
    expected_features[:, :3] = 2.0
    torch.testing.assert_close(model.extract_features(frames), expected_features)
    torch.testing.assert_close(result["expression_logits"], frame_logits.mean(dim=1))


def test_three_independent_heads_can_predict_high_intensity_together():
    model = FrozenExpressionLearningStateModel(
        build_model(_config(), allow_download=False), _config()
    )
    with torch.no_grad():
        for head in model.state_heads:
            head.weight.zero_()
            head.bias.copy_(torch.tensor([0.0, 1.0, 2.0, 3.0]))

    logits = model.state_logits_from_features(torch.zeros(1, 512))

    assert STATE_NAMES == ("boredom", "confusion", "frustration")
    torch.testing.assert_close(logits.argmax(dim=-1), torch.tensor([[3, 3, 3]]))


@pytest.mark.parametrize(
    "change",
    [
        {"model": "mobilenet_v3_small"},
        {"input_size": 48},
        {"input_channels": 1},
        {"normalization": {"mean": [0.0, 0.0, 0.0], "std": [1.0, 1.0, 1.0]}},
        {"class_names": list(reversed(CLASS_NAMES))},
    ],
)
def test_expression_contract_rejects_incompatible_source(change):
    config = _config()
    config.update(change)
    with pytest.raises(ValueError):
        validate_expression_contract(config)


def test_expression_checkpoint_loader_disables_pretrained_downloads(tmp_path, monkeypatch):
    import expression_recognition.learning_state_model as learning_state_model

    config = _config()
    backbone = build_model(config, allow_download=False)
    checkpoint_path = tmp_path / "expression.pt"
    torch.save(
        {"config": config, "class_names": CLASS_NAMES, "model_state": backbone.state_dict()},
        checkpoint_path,
    )
    original_builder = learning_state_model.build_model
    requested = []

    def local_builder(checkpoint_config, allow_download=True):
        requested.append(allow_download)
        return original_builder(checkpoint_config, allow_download=allow_download)

    monkeypatch.setattr(learning_state_model, "build_model", local_builder)

    loaded = FrozenExpressionLearningStateModel.from_expression_checkpoint(checkpoint_path)

    assert requested == [False]
    assert all(not parameter.requires_grad for parameter in loaded.backbone.parameters())


def test_metrics_include_all_four_levels_and_fit_majority_only_on_train_labels():
    targets = np.array([[0, 1, 2], [0, 1, 2], [1, 1, 2]], dtype=np.int64)
    predictions = np.array([[0, 1, 2], [1, 0, 2], [1, 1, 2]], dtype=np.int64)
    train_targets = np.array([[3, 0, 1], [3, 0, 1], [2, 0, 1]], dtype=np.int64)

    metrics = learning_state_metrics(targets, predictions, train_targets)

    boredom = metrics["states"]["boredom"]
    assert metrics["levels"] == [0, 1, 2, 3]
    assert boredom["support"] == [2, 1, 0, 0]
    assert np.asarray(boredom["confusion_matrix"]).shape == (4, 4)
    # F1 for absent target levels is zero and still contributes to the fixed-four macro.
    assert boredom["macro_f1"] == pytest.approx((2 / 3 + 2 / 3) / 4)
    assert metrics["majority_baseline"]["majority_levels"] == {
        "boredom": 3,
        "confusion": 0,
        "frustration": 1,
    }
    assert metrics["majority_baseline"]["fitted_on"] == "train"
    assert metrics["selection_score"] == metrics["mean_macro_f1"]


@pytest.mark.parametrize(
    "targets,predictions",
    [
        (np.empty((0, 3), dtype=np.int64), np.empty((0, 3), dtype=np.int64)),
        (np.zeros((2, 2), dtype=np.int64), np.zeros((2, 2), dtype=np.int64)),
        (np.zeros((2, 3), dtype=np.float32), np.zeros((2, 3), dtype=np.int64)),
        (np.zeros((2, 3), dtype=np.int64), np.full((2, 3), 4, dtype=np.int64)),
        (np.zeros((2, 3), dtype=np.int64), np.zeros((3, 3), dtype=np.int64)),
    ],
)
def test_metrics_reject_invalid_targets_or_predictions(targets, predictions):
    with pytest.raises(ValueError):
        learning_state_metrics(targets, predictions)


def test_metrics_reject_empty_or_malformed_training_labels():
    valid = np.zeros((2, 3), dtype=np.int64)
    with pytest.raises(ValueError):
        learning_state_metrics(valid, valid, np.empty((0, 3), dtype=np.int64))
    with pytest.raises(ValueError):
        learning_state_metrics(valid, valid, np.zeros((2, 4), dtype=np.int64))

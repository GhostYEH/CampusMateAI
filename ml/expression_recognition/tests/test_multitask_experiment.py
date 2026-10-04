from argparse import Namespace

import numpy as np
import pytest
import torch
from torch import nn

from expression_recognition.constants import CLASS_NAMES
from expression_recognition.multitask_experiment import (
    binary_positive_weights, binary_state_targets, evaluate_multitask, train_multitask,
)


def test_daisee_threshold_creates_three_independent_cooccurring_binary_targets():
    levels = np.array([[0, 2, 3], [1, 0, 2], [2, 3, 0]], dtype=np.int64)
    np.testing.assert_array_equal(binary_state_targets(levels),
                                  [[0, 1, 1], [0, 0, 1], [1, 1, 0]])
    weights = binary_positive_weights(torch.tensor([[0., 1., 1.], [0., 0., 1.], [1., 1., 0.]]))
    torch.testing.assert_close(weights, torch.tensor([2., 0.5, 0.5]))


@pytest.mark.parametrize("values", [np.zeros((2, 4), dtype=np.int64), np.full((2, 3), 4), np.zeros((2, 3), np.float32)])
def test_binary_mapping_rejects_missing_or_malformed_joint_labels(values):
    with pytest.raises(ValueError):
        binary_state_targets(values)


def test_training_reads_only_train_and_validation_splits_and_writes_provenance(tmp_path, monkeypatch):
    import expression_recognition.multitask_experiment as experiment
    from expression_recognition.multitask_model import MULTITASK_VERSION, STATE_NAMES

    class FakeBackbone(nn.Module):
        def __init__(self):
            super().__init__()
            self.layer4 = nn.Linear(1, 1)
            self.fc = nn.Linear(1, 7)

    class FakeJoint(nn.Module):
        config = {"model": "fixture"}

        def __init__(self):
            super().__init__()
            self.backbone = FakeBackbone()
            self.state_head = nn.Linear(1, 3)

        @classmethod
        def from_expression_checkpoint(cls, _):
            return cls()

        def train(self, mode=True):
            return super().train(mode)

        def forward(self, x):
            scalar = x.reshape(x.shape[0], -1).mean(dim=1, keepdim=True)
            return {"expression_logits": self.backbone.fc(scalar), "state_logits": self.state_head(scalar)}

    class FakeTeacher(nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = FakeBackbone()

        def forward(self, x):
            scalar = x.reshape(x.shape[0], -1).mean(dim=1, keepdim=True)
            return self.backbone.fc(scalar)

    class TinyDataset:
        def __init__(self, n=4):
            self.rows = [(None, [i % 4, (i + 1) % 4, (i + 2) % 4]) for i in range(n)]

        def __len__(self):
            return len(self.rows)

    def make_batches():
        return [(torch.ones(2, 3, 96, 96), torch.tensor([0, 1]))]

    splits_seen = []

    def fake_expression_loader(_manifest, split, *_args):
        splits_seen.append(("expression", split))
        return TinyDataset(), make_batches()

    def fake_state_loader(_manifest, split, *_args):
        splits_seen.append(("state", split))
        return TinyDataset(), [(torch.ones(2, 4, 3, 96, 96), torch.tensor([[0, 2, 3], [1, 0, 2]]))]

    # Training now imports the canonical spelling; replace that import too.
    monkeypatch.setattr(experiment, "MultitaskExpressionStateModel", FakeJoint)
    monkeypatch.setattr(experiment, "build_model", lambda *_args, **_kwargs: FakeTeacher())
    monkeypatch.setattr(experiment, "_loader", fake_expression_loader)
    monkeypatch.setattr(experiment, "_state_loader", fake_state_loader)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(experiment, "seed_everything", lambda *_: None)

    checkpoint = tmp_path / "source.pt"
    teacher = FakeTeacher()
    torch.save({"model_state": teacher.state_dict()}, checkpoint)
    expression_manifest = tmp_path / "expression.csv"
    daisee_manifest = tmp_path / "daisee.csv"
    expression_manifest.write_text("fixture", encoding="utf-8")
    daisee_manifest.write_text("fixture", encoding="utf-8")
    output_dir = tmp_path / "run"
    args = Namespace(checkpoint=checkpoint, expression_manifest=expression_manifest,
                     daisee_manifest=daisee_manifest, output_dir=output_dir, epochs=1,
                     batch_size=2, state_batch_size=2, workers=0, learning_rate=1e-3,
                     state_learning_rate=1e-3, max_expression_f1_drop=1.0, allow_cpu=True,
                     seed=4, teacher_temperature=2.0, teacher_kl_weight=0.5)
    report = train_multitask(args)
    assert all(split in ("train", "validation") for _, split in splits_seen)
    assert report["checkpoint_version"] == MULTITASK_VERSION
    assert report["state_positive_definition"] == "DAiSEE level >= 2"
    assert report["training_state_positive_counts"] == [2, 2, 2]
    assert report["deployment_ready"] is False
    with np.load(output_dir / "validation_predictions.npz") as predictions:
        assert predictions["expression_logits"].shape == (2, 7)
        assert predictions["state_logits"].shape == (2, 3)
        assert predictions["state_targets"].shape == (2, 3)
        assert predictions["split"].item() == "validation"
        assert len(predictions["checkpoint_sha256"].item()) == 64


def test_test_report_uses_checkpoint_calibration_but_prediction_archive_keeps_raw_logits(tmp_path, monkeypatch):
    import expression_recognition.multitask_experiment as experiment
    from expression_recognition.multitask_model import MULTITASK_CLASS_ORDER, MULTITASK_VERSION

    config = {"model": "resnet18", "input_size": 96, "input_channels": 3,
              "normalization": {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]},
              "class_names": list(CLASS_NAMES), "pretrained": False}
    calibration = {"label_order": list(MULTITASK_CLASS_ORDER), "expression_temperature": 1.5,
                   "state_scales": [2.0, 0.5, 1.0], "state_biases": [1.0, -1.0, 2.0]}
    checkpoint = {"checkpoint_version": MULTITASK_VERSION, "config": config, "model_state": {},
                  "class_order": list(MULTITASK_CLASS_ORDER), "state_positive_definition": "DAiSEE level >= 2",
                  "selection_split": "validation", "expression_guard_passed": True,
                  "training_state_counts": [1, 1, 1], "training_state_sample_count": 2,
                  "confidence_calibration": calibration}

    class FakeModel:
        def __init__(self):
            self.config = config

        @classmethod
        def from_checkpoint(cls, _path):
            return cls()

        def to(self, _device):
            return self

        def eval(self):
            return self

        def __call__(self, inputs):
            n = len(inputs)
            expression = torch.tensor([[3., 0., 0., 0., 0., 0., 0.]]).repeat(n, 1)
            states = torch.zeros(n, 3)
            return {"expression_logits": expression, "state_logits": states}

    class Dataset:
        def __len__(self):
            return 2

    expression_batches = [(torch.zeros(2, 3, 96, 96), torch.tensor([0, 1]))]
    state_batches = [(torch.zeros(2, 4, 3, 96, 96), torch.tensor([[2, 0, 3], [0, 2, 1]]))]
    seen_splits = []
    monkeypatch.setattr(experiment, "MultitaskExpressionStateModel", FakeModel)
    monkeypatch.setattr(experiment, "_loader", lambda _m, split, *_a: (seen_splits.append(split) or Dataset(), expression_batches))
    monkeypatch.setattr(experiment, "_state_loader", lambda _m, split, *_a: (seen_splits.append(split) or Dataset(), state_batches))
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    checkpoint_path = tmp_path / "calibrated.pt"
    torch.save(checkpoint, checkpoint_path)
    expression_manifest, daisee_manifest = tmp_path / "expression.csv", tmp_path / "daisee.csv"
    expression_manifest.write_text("fixture", encoding="utf-8")
    daisee_manifest.write_text("fixture", encoding="utf-8")
    args = Namespace(checkpoint=checkpoint_path, expression_manifest=expression_manifest,
                     daisee_manifest=daisee_manifest, output_dir=tmp_path / "test-report",
                     batch_size=2, state_batch_size=2, workers=0)

    report = evaluate_multitask(args)

    assert seen_splits == ["test", "test"]
    assert report["calibration_applied"] is True
    assert report["confidence_semantics"] == "validation_calibrated_model_probability"
    assert report["states"]["per_state"]["boredom"]["brier_score"] != report["raw_states"]["per_state"]["boredom"]["brier_score"]
    with np.load(args.output_dir / "test_predictions.npz") as predictions:
        np.testing.assert_array_equal(predictions["state_logits"], np.zeros((2, 3), dtype=np.float32))
        assert predictions["split"].item() == "test"

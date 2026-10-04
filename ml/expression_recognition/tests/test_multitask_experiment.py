from argparse import Namespace

import numpy as np
import pytest
import torch
from torch import nn

from expression_recognition.constants import CLASS_NAMES
from expression_recognition.multitask_experiment import (
    _build_teacher, _state_training_config, binary_positive_weights, binary_state_targets, evaluate_multitask,
    state_sample_weights, train_multitask,
)


def test_daisee_threshold_creates_three_independent_cooccurring_binary_targets():
    levels = np.array([[0, 2, 3], [1, 0, 2], [2, 3, 0]], dtype=np.int64)
    np.testing.assert_array_equal(binary_state_targets(levels),
                                  [[0, 1, 1], [0, 0, 1], [1, 1, 0]])
    weights = binary_positive_weights(torch.tensor([[0., 1., 1.], [0., 0., 1.], [1., 1., 0.]]))
    torch.testing.assert_close(weights, torch.tensor([2., 0.5, 0.5]))


def test_balanced_state_sampling_uses_training_positive_contributions_and_is_bounded():
    targets = torch.tensor([[1., 0., 0.], [1., 0., 1.], [0., 1., 0.], [0., 0., 0.]])
    weights = state_sample_weights(targets)
    assert torch.isfinite(weights).all()
    assert float(weights.max()) <= 5.0
    assert weights[1] > weights[0]
    assert weights[3] > 0


def test_mild_state_augmentation_is_a_copy_and_disables_synthetic_corruptions():
    config = {"augmentation": {"rotation_degrees": 8, "jpeg_probability": 0.4}}
    adjusted = _state_training_config(config, "mild")
    assert config["augmentation"] == {"rotation_degrees": 8, "jpeg_probability": 0.4}
    assert adjusted["augmentation"]["rotation_degrees"] == 3
    assert adjusted["augmentation"]["jpeg_probability"] == 0
    assert adjusted["augmentation"]["occlusion_probability"] == 0
    assert adjusted["_crop_scale"] == [0.95, 1.0]
    assert _state_training_config(config, "none")["_disable_augmentation"] is True


def test_teacher_source_initial_is_frozen_deepcopy_and_original_loads_source_weights(tmp_path, monkeypatch):
    import expression_recognition.multitask_experiment as experiment

    class Model(nn.Module):
        def __init__(self):
            super().__init__()
            self.config = {"model": "fixture"}
            self.backbone = nn.Sequential(nn.Linear(2, 3))

    original = Model()
    initial = Model()
    with torch.no_grad():
        original.backbone[0].weight.fill_(4)
        initial.backbone[0].weight.fill_(7)
    source_path = tmp_path / "teacher-source.pt"
    torch.save({"model_state": original.backbone.state_dict()}, source_path)
    monkeypatch.setattr(experiment, "build_model", lambda *_args, **_kwargs: Model().backbone)

    initial_teacher = _build_teacher(initial, source_path, "initial", torch.device("cpu"))
    original_teacher = _build_teacher(initial, source_path, "original", torch.device("cpu"))

    torch.testing.assert_close(initial_teacher[0].weight, torch.full((3, 2), 7.0))
    torch.testing.assert_close(original_teacher[0].weight, torch.full((3, 2), 4.0))
    assert initial_teacher[0].weight.data_ptr() != initial.backbone[0].weight.data_ptr()
    assert all(parameter.requires_grad is False for parameter in initial_teacher.parameters())
    assert all(parameter.requires_grad is False for parameter in original_teacher.parameters())
    assert not initial_teacher.training and not original_teacher.training
    with torch.no_grad():
        initial_teacher[0].weight.zero_()
    torch.testing.assert_close(initial.backbone[0].weight, torch.full((3, 2), 7.0))


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
    assert report["teacher_source"] == "original"
    assert report["teacher_checkpoint_sha256"] == experiment.file_digest(checkpoint)
    with np.load(output_dir / "validation_predictions.npz") as predictions:
        assert predictions["expression_logits"].shape == (2, 7)
        assert predictions["state_logits"].shape == (2, 3)
        assert predictions["state_targets"].shape == (2, 3)
        assert predictions["split"].item() == "validation"
        assert len(predictions["checkpoint_sha256"].item()) == 64


def test_training_can_initialize_joint_checkpoint_and_records_hash_and_baseline(tmp_path, monkeypatch):
    import expression_recognition.multitask_experiment as experiment

    class TinyBackbone(nn.Module):
        def __init__(self):
            super().__init__()
            self.layer4 = nn.Linear(1, 1)
            self.fc = nn.Linear(1, 7)

    class Joint(nn.Module):
        config = {"model": "fixture"}
        instances = []

        def __init__(self):
            super().__init__()
            self.backbone = TinyBackbone()
            self.state_head = nn.Linear(1, 3)
            self.__class__.instances.append(self)

        @classmethod
        def from_checkpoint(cls, path):
            model = cls()
            model.load_state_dict(torch.load(path, weights_only=False)["model_state"])
            model.loaded_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            model.confidence_calibration = {"old": True}
            return model

        def forward(self, x):
            scalar = x.reshape(x.shape[0], -1).mean(dim=1, keepdim=True)
            return {"expression_logits": self.backbone.fc(scalar), "state_logits": self.state_head(scalar)}

    class Teacher(nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = TinyBackbone()

        def forward(self, x):
            scalar = x.reshape(x.shape[0], -1).mean(dim=1, keepdim=True)
            return self.backbone.fc(scalar)

    class Dataset:
        def __init__(self):
            self.rows = [(None, [0, 2, 3]), (None, [1, 0, 2])]

        def __len__(self):
            return len(self.rows)

    monkeypatch.setattr(experiment, "MultitaskExpressionStateModel", Joint)
    monkeypatch.setattr(experiment, "build_model", lambda *_a, **_k: Teacher())
    monkeypatch.setattr(experiment, "_loader", lambda *_a: (Dataset(), [(torch.ones(2, 3, 2, 2), torch.tensor([0, 1]))]))
    monkeypatch.setattr(experiment, "_state_loader", lambda *_a, **_k: (
        Dataset(), [(torch.ones(2, 4, 3, 2, 2), torch.tensor([[0, 2, 3], [1, 0, 2]]))]))
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(experiment, "seed_everything", lambda *_: None)
    teacher = Teacher()
    teacher_path, init_path = tmp_path / "teacher.pt", tmp_path / "joint.pt"
    torch.save({"model_state": teacher.state_dict()}, teacher_path)
    initialized = Joint()
    with torch.no_grad():
        initialized.state_head.weight.fill_(2.5)
        initialized.state_head.bias.fill_(1.5)
    torch.save({"model_state": initialized.state_dict(), "selection_split": "validation",
                "expression_guard_passed": True, "candidate_only": False}, init_path)
    expression_manifest, state_manifest = tmp_path / "expression.csv", tmp_path / "states.csv"
    expression_manifest.write_text("fixture", encoding="utf-8")
    state_manifest.write_text("fixture", encoding="utf-8")
    args = Namespace(checkpoint=teacher_path, initialize_from=init_path,
                     expression_manifest=expression_manifest, daisee_manifest=state_manifest,
                     output_dir=tmp_path / "run-init", epochs=1, batch_size=2, state_batch_size=2,
                     workers=0, learning_rate=1e-8, state_learning_rate=1e-8,
                     max_expression_f1_drop=1.0, allow_cpu=True, seed=4,
                     teacher_temperature=2.0, teacher_kl_weight=0.5)
    report = train_multitask(args)
    trained = Joint.instances[-1]
    torch.testing.assert_close(trained.loaded_state["state_head.weight"], torch.full((3, 1), 2.5))
    assert trained.confidence_calibration is None
    assert report["initialize_checkpoint_sha256"] == experiment.file_digest(init_path)
    assert report["baseline_expression"] == report["training_settings"]["baseline_joint_expression"]


def test_negative_state_loss_weight_is_rejected_before_any_training(tmp_path):
    args = Namespace(epochs=1, batch_size=1, state_batch_size=1, workers=0, learning_rate=1e-3,
                     state_learning_rate=1e-3, max_expression_f1_drop=0.01, teacher_kl_weight=0.5,
                     teacher_temperature=2.0, state_loss_weight=-0.1, output_dir=tmp_path / "run")
    with pytest.raises(ValueError, match="State loss weight"):
        train_multitask(args)


@pytest.mark.parametrize("metadata", [
    {"selection_split": "validation", "expression_guard_passed": True, "candidate_only": True},
    {"selection_split": "validation", "expression_guard_passed": False, "candidate_only": False},
    {"selection_split": "validation", "expression_guard_passed": True},
])
def test_unselected_or_guard_failed_joint_checkpoint_cannot_warmstart(tmp_path, monkeypatch, metadata):
    import expression_recognition.multitask_experiment as experiment

    class ForbiddenModel:
        @classmethod
        def from_checkpoint(cls, _path):
            pytest.fail("unselected warm-start must be rejected before loading model weights")

    def forbidden_teacher(*_args, **_kwargs):
        pytest.fail("unselected warm-start must be rejected before loading the teacher")

    monkeypatch.setattr(experiment, "MultitaskExpressionStateModel", ForbiddenModel)
    monkeypatch.setattr(experiment, "build_model", forbidden_teacher)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(experiment, "seed_everything", lambda *_: None)
    warmstart = tmp_path / "candidate.pt"
    torch.save(metadata, warmstart)
    output_dir = tmp_path / "must-not-be-created"
    args = Namespace(checkpoint=tmp_path / "teacher.pt", initialize_from=warmstart,
                     expression_manifest=tmp_path / "expression.csv", daisee_manifest=tmp_path / "states.csv",
                     output_dir=output_dir, epochs=1, batch_size=1, state_batch_size=1, workers=0,
                     learning_rate=1e-3, state_learning_rate=1e-3, max_expression_f1_drop=0.01,
                     teacher_kl_weight=0.5, teacher_temperature=2.0, allow_cpu=True, seed=1)
    with pytest.raises(ValueError, match="selected validation checkpoint"):
        train_multitask(args)
    assert not output_dir.exists()


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

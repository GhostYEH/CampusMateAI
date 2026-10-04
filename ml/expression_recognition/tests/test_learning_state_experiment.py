from argparse import Namespace

import numpy as np
import pytest
import torch

from expression_recognition.learning_state_experiment import (
    evaluate_extension, frozen_digest, state_class_weights, state_loss, train_extension,
)


def test_class_weights_use_three_independent_training_distributions():
    labels = torch.tensor([[0, 1, 3], [0, 2, 3], [0, 2, 0], [1, 3, 0]])
    weights = state_class_weights(labels)
    assert weights.shape == (3, 4)
    torch.testing.assert_close(weights.mean(1), torch.ones(3))
    assert weights[0, 0] < weights[0, 1]
    assert weights[1, 2] < weights[1, 1]
    assert weights[2, 0] == weights[2, 3]
    assert weights.isfinite().all()


@pytest.mark.parametrize("labels", [torch.empty(0, 3, dtype=torch.long), torch.zeros(2, 4, dtype=torch.long),
                                  torch.full((2, 3), 4), torch.zeros(2, 3)])
def test_class_weights_reject_invalid_labels(labels):
    with pytest.raises(ValueError):
        state_class_weights(labels)


def test_loss_supervises_cooccurring_states_independently():
    logits = torch.zeros(2, 3, 4, requires_grad=True)
    labels = torch.full((2, 3), 3, dtype=torch.long)
    loss = state_loss(logits, labels, torch.ones(3, 4))
    loss.backward()
    assert loss.item() == pytest.approx(np.log(4))
    assert torch.all(logits.grad[:, :, 3] < 0)
    assert torch.all(logits.grad[:, :, :3] > 0)


def test_training_selects_on_validation_without_accessing_test(tmp_path, monkeypatch):
    from expression_recognition import learning_state_model

    class TinyFrozenExtension(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.config = {"model": "fixture"}
            self.backbone = torch.nn.Linear(1, 7).requires_grad_(False)
            self.state_heads = torch.nn.ModuleList(torch.nn.Linear(512, 4) for _ in range(3))

        def state_logits_from_features(self, features):
            return torch.stack([head(features) for head in self.state_heads], 1)

    model = TinyFrozenExtension()
    before = frozen_digest(model)
    monkeypatch.setattr(learning_state_model.FrozenExpressionLearningStateModel,
                        "from_expression_checkpoint", lambda _: model)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    labels = np.tile(np.arange(4)[:, None], (1, 3)).astype(np.int64)
    features = np.zeros((4, 512), dtype=np.float32)
    features[:, :4] = np.eye(4)
    seen = []

    def extract(_, manifest, split, *args):
        assert split in ("train", "validation")
        seen.append(split)
        return features, labels

    monkeypatch.setattr("expression_recognition.learning_state_experiment.extract_clip_features", extract)
    source = tmp_path / "source.pt"
    source.write_bytes(b"fixture-source")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("fixture-manifest", encoding="utf-8")
    args = Namespace(checkpoint=source, manifest=manifest, output_dir=tmp_path / "run", epochs=2,
                     learning_rate=0.01, batch_size=4, seed=1, workers=0, feature_batch_size=4, allow_cpu=True)
    report = train_extension(args)
    assert seen == ["train", "validation"]
    assert report["frozen_expression_unchanged"]
    assert frozen_digest(model) == before
    checkpoint = torch.load(args.output_dir / "best.pt", weights_only=False)
    assert checkpoint["state_order"] == ["boredom", "confusion", "frustration"]
    assert checkpoint["selection_split"] == "validation"
    assert checkpoint["deployment_ready"] is False
    assert report["best_epoch"] in (1, 2)
    with pytest.raises(FileExistsError):
        train_extension(args)


def test_test_evaluation_rejects_legacy_seven_class_checkpoint(tmp_path):
    source = tmp_path / "legacy.pt"
    torch.save({"config": {}, "model_state": {}}, source)
    with pytest.raises(ValueError, match="validation-selected"):
        evaluate_extension(Namespace(checkpoint=source, output_dir=tmp_path / "test"))

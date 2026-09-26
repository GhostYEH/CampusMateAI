import csv
from pathlib import Path

import pytest
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from expression_recognition import occlusion_experiment as experiment


def test_fixed_occlusion_is_batch_independent_and_keeps_clean_input() -> None:
    images = torch.zeros(3, 3, 16, 16)
    mean = [0.5] * 3
    std = [0.5] * 3
    masked = experiment.occlude_batch(images, mean=mean, std=std, seed=17)
    separately = torch.cat([
        experiment.occlude_batch(images[index:index + 1], mean=mean, std=std, seed=17, first_index=index)
        for index in range(3)
    ])
    assert torch.equal(masked, separately)
    assert torch.equal(images, torch.zeros_like(images))
    assert all(torch.any(masked[index] != images[index]) for index in range(3))
    assert set(masked.unique().tolist()) == {-1.0, 0.0}


def test_clean_anchor_loss_updates_student_but_not_teacher() -> None:
    clean = torch.randn(2, 7, requires_grad=True)
    masked = torch.randn(2, 7, requires_grad=True)
    teacher = torch.randn(2, 7, requires_grad=True)
    loss = experiment.anchored_loss(clean, masked, teacher, torch.tensor([1, 2]), nn.CrossEntropyLoss())
    loss.backward()
    assert clean.grad is not None and torch.any(clean.grad != 0)
    assert masked.grad is not None and torch.any(masked.grad != 0)
    assert teacher.grad is None


def test_evaluation_uses_all_seven_classes_and_fixed_masks() -> None:
    model = nn.Sequential(nn.Flatten(), nn.Linear(3 * 8 * 8, 7))
    loader = DataLoader(TensorDataset(torch.zeros(7, 3, 8, 8), torch.arange(7)), batch_size=3)
    config = {"normalization": {"mean": [0.5] * 3, "std": [0.5] * 3}}
    first = experiment.evaluate_pair(model, loader, torch.device("cpu"), config, 42)
    second = experiment.evaluate_pair(model, loader, torch.device("cpu"), config, 42)
    assert first == second
    assert first["samples"] == 7
    assert len(first["occluded_per_class_f1"]) == 7


def test_experiment_writes_comparison_from_same_checkpoint(tmp_path: Path, monkeypatch) -> None:
    class TinyModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc = nn.Linear(3, 7)

        def forward(self, images):
            return self.fc(images.mean(dim=(2, 3)))

    monkeypatch.setattr(experiment, "build_model", lambda config, allow_download=False: TinyModel())
    manifest = tmp_path / "included.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "label_index", "status", "split"])
        writer.writeheader()
        for split in ("train", "validation"):
            for label in range(7):
                path = tmp_path / f"{split}-{label}.png"
                Image.new("RGB", (16, 16), color=(label * 20, 50, 100)).save(path)
                writer.writerow({"path": str(path), "label_index": label, "status": "included", "split": split})
    config = {
        "model": "resnet18", "seed": 8, "input_size": 16, "input_channels": 3,
        "batch_size": 7, "num_workers": 0, "weight_decay": 0.0,
        "normalization": {"mean": [0.5] * 3, "std": [0.5] * 3},
        "augmentation": {},
    }
    checkpoint = tmp_path / "initial.pt"
    torch.save({"config": config, "model_state": TinyModel().state_dict()}, checkpoint)
    args = type("Args", (), {
        "checkpoint": checkpoint, "manifest": manifest, "output_dir": tmp_path / "result",
        "epochs": 1, "batch_size": 7, "learning_rate": 1e-3,
        "num_workers": 0, "max_train_batches": 1, "cpu": True,
    })()
    result = experiment.run_experiment(args)
    assert result["smoke"] is True
    assert set(result["arms"]) == {"hard_occlusion", "clean_anchor"}
    assert (args.output_dir / "comparison.json").is_file()
    assert all((args.output_dir / arm / "best.pt").is_file() for arm in result["arms"])
    with pytest.raises(FileExistsError):
        experiment.run_experiment(args)

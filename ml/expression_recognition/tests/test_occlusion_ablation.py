import csv
from pathlib import Path

import pytest
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from expression_recognition import occlusion_ablation as oa


def test_occlusion_is_batch_independent_fixed_and_keeps_clean_input() -> None:
    images = torch.zeros(3, 3, 16, 16)
    mean = [0.5] * 3
    std = [0.5] * 3
    masked, regions = oa.occlude_batch(images, mean=mean, std=std, seed=17)
    separately = []
    sep_regions = []
    for index in range(3):
        m, r = oa.occlude_batch(images[index:index + 1], mean=mean, std=std, seed=17, first_index=index)
        separately.append(m)
        sep_regions.extend(r)
    assert torch.equal(masked, torch.cat(separately))
    assert regions == sep_regions
    assert torch.equal(images, torch.zeros_like(images))  # clean input untouched
    assert all(torch.any(masked[i] != images[i]) for i in range(3))
    assert set(masked.unique().tolist()) == {-1.0, 0.0}
    assert set(regions).issubset({0, 1, 2})


def test_severe_stress_geometry_differs_from_standard() -> None:
    images = torch.zeros(1, 3, 32, 32)
    mean = [0.5] * 3
    std = [0.5] * 3
    std_masked, _ = oa.occlude_batch(images, mean=mean, std=std, seed=5)
    stress_masked, _ = oa.occlude_batch(
        images, mean=mean, std=std, seed=5,
        box_width_range=oa.STRESS_BOX_WIDTH, box_height_range=oa.STRESS_BOX_HEIGHT,
    )
    # locked stress boxes are strictly larger in expectation -> more masked pixels
    assert int((stress_masked[0] != 0).sum()) > int((std_masked[0] != 0).sum())


def test_anchored_loss_normalization_is_fixed_convex_combination() -> None:
    torch.manual_seed(0)
    clean = torch.randn(4, 7)
    masked = torch.randn(4, 7)
    teacher = torch.randn(4, 7)
    labels = torch.tensor([0, 1, 2, 3])
    ce = nn.CrossEntropyLoss()
    # teacher_weight=0 reduces to the supervised convex combination
    l_full = oa.anchored_loss(clean, masked, teacher, labels, ce, teacher_weight=0.0,
                              lambda_clean=0.5, lambda_masked=0.5)
    expected = 0.5 * ce(clean, labels) + 0.5 * ce(masked, labels)
    assert torch.allclose(l_full, expected, atol=1e-6)
    # lambda_clean=1, lambda_masked=0 reduces to pure clean CE (same scale as arm B)
    l_clean = oa.anchored_loss(clean, masked, teacher, labels, ce, teacher_weight=0.0,
                               lambda_clean=1.0, lambda_masked=0.0)
    assert torch.allclose(l_clean, ce(clean, labels), atol=1e-6)
    with pytest.raises(ValueError):
        oa.anchored_loss(clean, masked, teacher, labels, ce, lambda_clean=0.6, lambda_masked=0.6)


def test_anchored_loss_updates_student_not_teacher() -> None:
    clean = torch.randn(2, 7, requires_grad=True)
    masked = torch.randn(2, 7, requires_grad=True)
    teacher = torch.randn(2, 7, requires_grad=True)
    loss = oa.anchored_loss(clean, masked, teacher, torch.tensor([1, 2]), nn.CrossEntropyLoss())
    loss.backward()
    assert clean.grad is not None and torch.any(clean.grad != 0)
    assert masked.grad is not None and torch.any(masked.grad != 0)
    assert teacher.grad is None


def test_arm_losses_dispatch_correctly() -> None:
    class Tiny(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc = nn.Linear(3, 7)

        def forward(self, images):
            return self.fc(images.mean(dim=(2, 3)))

    model = Tiny()
    clean = torch.randn(4, 3, 8, 8)
    masked = torch.randn(4, 3, 8, 8)
    labels = torch.tensor([0, 1, 2, 3])
    teacher_clean = torch.randn(4, 7)
    ce = nn.CrossEntropyLoss()
    config = {"distill_temperature": 2.0, "distill_teacher_weight": 0.5,
              "distill_lambda_clean": 0.5, "distill_lambda_masked": 0.5}
    b = oa.arm_loss("B_plain", model, clean, masked, teacher_clean, labels, ce, config)
    assert torch.allclose(b, ce(model(clean), labels), atol=1e-6)
    c = oa.arm_loss("C_hard_occlusion", model, clean, masked, teacher_clean, labels, ce, config)
    assert torch.allclose(c, ce(model(masked), labels), atol=1e-6)
    d = oa.arm_loss("D_clean_anchor", model, clean, masked, teacher_clean, labels, ce, config)
    assert d.item() > 0


def _write_tiny_manifest(tmp_path: Path) -> Path:
    manifest = tmp_path / "included.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "label_index", "status", "split"])
        writer.writeheader()
        for split in ("train", "validation"):
            for label in range(7):
                path = tmp_path / f"{split}-{label}.png"
                Image.new("RGB", (16, 16), color=(label * 20, 50, 100)).save(path)
                writer.writerow({"path": str(path), "label_index": label, "status": "included", "split": split})
    return manifest


def test_run_produces_four_arms_from_same_checkpoint(tmp_path: Path, monkeypatch) -> None:
    class TinyModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc = nn.Linear(3, 7)

        def forward(self, images):
            return self.fc(images.mean(dim=(2, 3)))

    monkeypatch.setattr(oa, "build_model", lambda config, allow_download=False: TinyModel())
    manifest = _write_tiny_manifest(tmp_path)
    config = {
        "model": "resnet18", "seed": 8, "input_size": 16, "input_channels": 3,
        "batch_size": 7, "num_workers": 0, "weight_decay": 0.0,
        "normalization": {"mean": [0.5] * 3, "std": [0.5] * 3},
        "augmentation": {}, "gradient_clip_norm": 1.0,
    }
    checkpoint = tmp_path / "initial.pt"
    torch.save({"config": config, "model_state": TinyModel().state_dict()}, checkpoint)
    args = type("Args", (), {
        "checkpoint": checkpoint, "manifest": manifest, "output_dir": tmp_path / "result",
        "epochs": 1, "batch_size": 7, "learning_rate": 1e-3, "num_workers": 0,
        "max_train_batches": 1, "cpu": True, "seed": 8, "overwrite": False,
        "temperature": 2.0, "teacher_weight": 0.5, "lambda_clean": 0.5, "lambda_masked": 0.5,
    })()
    result = oa.run(args)
    assert set(result["arms"]) == {"A_baseline", "B_plain", "C_hard_occlusion", "D_clean_anchor"}
    assert result["smoke"] is True
    for arm in ("B_plain", "C_hard_occlusion", "D_clean_anchor"):
        assert (args.output_dir / arm / "best.pt").is_file()
        assert (args.output_dir / arm / "history.json").is_file()
        assert (args.output_dir / arm / "run_info.json").is_file()
    assert (args.output_dir / "A_baseline" / "metrics.json").is_file()
    assert (args.output_dir / "results.json").is_file()
    # each arm records identical optimizer update count (same data, same schedule)
    updates = {arm: result["arms"][arm]["run_info"]["optimizer_updates"] for arm in
               ("B_plain", "C_hard_occlusion", "D_clean_anchor")}
    assert len(set(updates.values())) == 1
    # D processes two views per update, B/C one
    assert result["arms"]["D_clean_anchor"]["run_info"]["views_processed"] == 2 * updates["D_clean_anchor"]
    assert result["arms"]["B_plain"]["run_info"]["views_processed"] == updates["B_plain"]
    # metric payload has the required fields
    ev = result["arms"]["A_baseline"]["eval"]
    for key in ("clean", "occluded", "occluded_stress_severe", "occluded_by_region"):
        assert key in ev
    assert len(ev["clean"]["per_class"]) == 7
    assert len(ev["clean"]["confusion_matrix"]) == 7
    with pytest.raises(FileExistsError):
        oa.run(args)


def test_evaluation_masks_are_seed_fixed() -> None:
    model = nn.Sequential(nn.Flatten(), nn.Linear(3 * 8 * 8, 7))
    loader = DataLoader(TensorDataset(torch.zeros(7, 3, 8, 8), torch.arange(7)), batch_size=3)
    config = {"normalization": {"mean": [0.5] * 3, "std": [0.5] * 3}}
    first = oa.evaluate_model(model, loader, torch.device("cpu"), config, 42, 43)
    second = oa.evaluate_model(model, loader, torch.device("cpu"), config, 42, 43)
    assert first == second
    assert first["clean"]["samples"] == 7
    assert sum(first["region_counts"].values()) == 7

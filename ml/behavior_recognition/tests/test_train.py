import csv
from pathlib import Path

import yaml
import torch
from PIL import Image

from behavior_recognition.train import select_best_epoch, train_model


def test_checkpoint_selection_uses_macro_f1_then_loss():
    """Catches best-checkpoint selection drifting back to overall accuracy."""
    rows = [
        {"epoch": 1, "val_macro_f1": 0.61, "val_loss": 0.8},
        {"epoch": 2, "val_macro_f1": 0.64, "val_loss": 0.9},
        {"epoch": 3, "val_macro_f1": 0.64, "val_loss": 0.7},
    ]
    assert select_best_epoch(rows) == 3


def _write_manifest(path: Path, images: list[Path], labels: list[int]) -> None:
    fields = [
        "sample_id", "source", "image_path", "label_path", "source_class_id",
        "target_name", "target_index", "split", "group_id", "center_x",
        "center_y", "width", "height", "sha256", "split_reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, (image, label) in enumerate(zip(images, labels)):
            writer.writerow(
                {
                    "sample_id": str(index), "source": "tiny", "image_path": str(image),
                    "label_path": "", "source_class_id": str(label), "target_name": "x",
                    "target_index": str(label), "split": path.stem, "group_id": f"g{index}",
                    "center_x": "0.5", "center_y": "0.5", "width": "0.8",
                    "height": "0.8", "sha256": str(index), "split_reason": "test",
                }
            )


def test_tiny_cpu_training_saves_reloadable_checkpoint(tmp_path: Path):
    """Catches training loops that cannot complete and persist their best state."""
    images = []
    labels = []
    for label in range(4):
        for copy in range(2):
            path = tmp_path / f"{label}_{copy}.jpg"
            Image.new("RGB", (48, 48), color=(label * 50, copy * 20, 30)).save(path)
            images.append(path)
            labels.append(label)
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    _write_manifest(manifests / "train.csv", images, labels)
    _write_manifest(manifests / "val.csv", images, labels)
    config = tmp_path / "config.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "seed": 7, "input_mode": "roi", "pretrained": False,
                "batch_size": 4, "num_workers": 0, "max_epochs": 1,
                "early_stopping_patience": 1, "learning_rate": 0.001,
                "weight_decay": 0.0, "label_smoothing": 0.0,
                "gradient_clip_norm": 1.0, "amp": False,
            }
        ),
        encoding="utf-8",
    )
    checkpoint = train_model(config, manifests, tmp_path / "run", device_override="cpu")
    assert checkpoint.name == "best.pt"
    assert checkpoint.is_file()
    assert (tmp_path / "run" / "history.csv").is_file()
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    assert payload["epoch"] == 1
    assert "model_state" in payload

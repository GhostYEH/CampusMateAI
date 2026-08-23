import csv
from pathlib import Path

import torch
from PIL import Image

from behavior_recognition.data import BehaviorDataset, crop_normalized_box


def test_expanded_roi_is_nonempty_and_clipped():
    """Catches ROI expansion producing empty or out-of-bounds crops."""
    image = Image.new("RGB", (100, 80), color=(10, 30, 50))
    crop = crop_normalized_box(image, 0.05, 0.05, 0.20, 0.20, expansion=1.25)
    assert crop.width > 0
    assert crop.height > 0
    assert crop.size == (18, 14)


def test_validation_dataset_is_deterministic(tmp_path: Path):
    """Catches random augmentation leaking into validation metrics."""
    image_path = tmp_path / "sample.jpg"
    Image.new("RGB", (100, 80), color=(30, 60, 90)).save(image_path)
    manifest = tmp_path / "val.csv"
    fields = [
        "sample_id", "source", "image_path", "label_path", "source_class_id",
        "target_name", "target_index", "split", "group_id", "center_x",
        "center_y", "width", "height", "sha256", "split_reason",
    ]
    row = dict.fromkeys(fields, "")
    row.update(
        sample_id="x", source="tiny", image_path=str(image_path), target_name="READ",
        target_index="0", split="val", group_id="g", center_x="0.5",
        center_y="0.5", width="0.5", height="0.5", sha256="abc",
    )
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)
    dataset = BehaviorDataset(manifest, mode="roi", training=False)
    first, first_label = dataset[0]
    second, second_label = dataset[0]
    assert first.shape == (3, 224, 224)
    assert torch.equal(first, second)
    assert first_label == second_label == 0

import csv
import json
from pathlib import Path

from PIL import Image

from behavior_recognition.temporal_data import TemporalBehaviorDataset


def test_temporal_dataset_returns_ordered_frame_tensor(tmp_path: Path):
    images = []
    for index, color in enumerate((20, 80, 140)):
        path = tmp_path / f"{index}.jpg"
        Image.new("RGB", (64, 48), color=(color, 30, 40)).save(path)
        images.append(str(path))
    manifest = tmp_path / "train.csv"
    fields = [
        "window_id", "video_id", "track_id", "split", "target_name",
        "target_index", "frame_paths", "boxes",
    ]
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "window_id": "w1", "video_id": "4001", "track_id": "t1",
                "split": "train", "target_name": "READ", "target_index": 0,
                "frame_paths": json.dumps(images),
                "boxes": json.dumps([[0.5, 0.5, 0.8, 0.8]] * 3),
            }
        )

    frames, label = TemporalBehaviorDataset(manifest, training=False)[0]

    assert frames.shape == (3, 3, 224, 224)
    assert label == 0
    assert not frames[0].equal(frames[1])


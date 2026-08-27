from __future__ import annotations

import csv
import json
from pathlib import Path

import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

from .constants import IMAGE_SIZE, IMAGENET_MEAN, IMAGENET_STD
from .data import crop_normalized_box


def build_temporal_transform(training: bool) -> transforms.Compose:
    operations: list = [transforms.Resize((IMAGE_SIZE, IMAGE_SIZE), antialias=True)]
    if training:
        operations.append(transforms.ColorJitter(brightness=0.15, contrast=0.15))
    operations.extend(
        [transforms.ToTensor(), transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD)]
    )
    return transforms.Compose(operations)


class TemporalBehaviorDataset(Dataset):
    def __init__(self, manifest_path: Path, training: bool = False):
        with manifest_path.open(encoding="utf-8", newline="") as handle:
            self.rows = list(csv.DictReader(handle))
        self.transform = build_temporal_transform(training)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        frame_paths = json.loads(row["frame_paths"])
        boxes = json.loads(row["boxes"])
        if len(frame_paths) != len(boxes) or not frame_paths:
            raise ValueError(f"Invalid temporal window: {row['window_id']}")
        frames = []
        for path, box in zip(frame_paths, boxes):
            with Image.open(path) as opened:
                image = crop_normalized_box(opened.convert("RGB"), *map(float, box))
                frames.append(self.transform(image))
        return torch.stack(frames), int(row["target_index"])


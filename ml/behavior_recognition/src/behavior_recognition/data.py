from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

from .constants import IMAGE_SIZE, IMAGENET_MEAN, IMAGENET_STD


def crop_normalized_box(
    image: Image.Image,
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    expansion: float = 1.25,
) -> Image.Image:
    image_width, image_height = image.size
    half_width = width * expansion / 2.0
    half_height = height * expansion / 2.0
    left = max(0, round((center_x - half_width) * image_width))
    top = max(0, round((center_y - half_height) * image_height))
    right = min(image_width, round((center_x + half_width) * image_width))
    bottom = min(image_height, round((center_y + half_height) * image_height))
    if right <= left or bottom <= top:
        raise ValueError("Expanded ROI is empty")
    return image.crop((left, top, right, bottom))


def build_transforms(training: bool):
    operations: list = [transforms.Resize((IMAGE_SIZE, IMAGE_SIZE), antialias=True)]
    if training:
        operations.extend(
            [
                transforms.ColorJitter(brightness=0.15, contrast=0.15),
                transforms.RandomAffine(degrees=7, translate=(0.06, 0.06), scale=(0.92, 1.08)),
                transforms.RandomApply([transforms.GaussianBlur(3)], p=0.12),
            ]
        )
    operations.extend(
        [
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )
    if training:
        operations.append(transforms.RandomErasing(p=0.12, scale=(0.02, 0.10)))
    return transforms.Compose(operations)


class BehaviorDataset(Dataset):
    def __init__(
        self,
        manifest_path: Path,
        mode: str = "roi",
        training: bool = False,
        records: list[dict[str, str]] | None = None,
    ):
        if mode not in {"roi", "full"}:
            raise ValueError(f"Unsupported input mode: {mode}")
        self.mode = mode
        self.training = training
        if records is None:
            with manifest_path.open(encoding="utf-8", newline="") as handle:
                records = list(csv.DictReader(handle))
        self.records = records
        self.transform = build_transforms(training)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int):
        record = self.records[index]
        with Image.open(record["image_path"]) as opened:
            image = opened.convert("RGB")
            if self.mode == "roi":
                image = crop_normalized_box(
                    image,
                    float(record["center_x"]),
                    float(record["center_y"]),
                    float(record["width"]),
                    float(record["height"]),
                )
            tensor = self.transform(image)
        return tensor, int(record["target_index"])

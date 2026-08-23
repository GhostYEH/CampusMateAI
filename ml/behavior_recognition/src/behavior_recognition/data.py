from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

from .constants import IMAGE_SIZE, IMAGENET_MEAN, IMAGENET_STD


def cache_path_for_record(cache_dir: Path, sample_id: str) -> Path:
    key = hashlib.sha256(sample_id.encode("utf-8")).hexdigest()
    return cache_dir / key[:2] / f"{key}.jpg"


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


def materialize_roi_cache(
    records: list[dict[str, str]], cache_dir: Path, workers: int = 8
) -> int:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for record in records:
        destination = cache_path_for_record(cache_dir, record["sample_id"])
        if not destination.is_file():
            grouped[record["image_path"]].append(record)

    def process(group: tuple[str, list[dict[str, str]]]) -> int:
        image_path, image_records = group
        created = 0
        with Image.open(image_path) as opened:
            image = opened.convert("RGB")
            for record in image_records:
                destination = cache_path_for_record(cache_dir, record["sample_id"])
                if destination.is_file():
                    continue
                crop = crop_normalized_box(
                    image,
                    float(record["center_x"]),
                    float(record["center_y"]),
                    float(record["width"]),
                    float(record["height"]),
                ).resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.BILINEAR)
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_suffix(".tmp")
                crop.save(temporary, format="JPEG", quality=90, optimize=False)
                temporary.replace(destination)
                created += 1
        return created

    if not grouped:
        return 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        return sum(executor.map(process, grouped.items()))


class BehaviorDataset(Dataset):
    def __init__(
        self,
        manifest_path: Path,
        mode: str = "roi",
        training: bool = False,
        records: list[dict[str, str]] | None = None,
        cache_dir: Path | None = None,
    ):
        if mode not in {"roi", "full"}:
            raise ValueError(f"Unsupported input mode: {mode}")
        self.mode = mode
        self.training = training
        self.cache_dir = cache_dir
        if records is None:
            with manifest_path.open(encoding="utf-8", newline="") as handle:
                records = list(csv.DictReader(handle))
        self.records = records
        self.transform = build_transforms(training)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int):
        record = self.records[index]
        cached = (
            cache_path_for_record(self.cache_dir, record["sample_id"])
            if self.cache_dir is not None and self.mode == "roi"
            else None
        )
        source_path = cached if cached is not None and cached.is_file() else Path(record["image_path"])
        with Image.open(source_path) as opened:
            image = opened.convert("RGB")
            if self.mode == "roi" and source_path == Path(record["image_path"]):
                image = crop_normalized_box(
                    image,
                    float(record["center_x"]),
                    float(record["center_y"]),
                    float(record["width"]),
                    float(record["height"]),
                )
            tensor = self.transform(image)
        return tensor, int(record["target_index"])

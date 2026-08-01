from __future__ import annotations

import csv
import io
import random
from collections import Counter
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from torch.utils.data import BatchSampler, DataLoader, Dataset, Sampler, WeightedRandomSampler
from torchvision import transforms
from torchvision.transforms import InterpolationMode

from .constants import CLASS_NAMES


class RandomJpegCompression:
    """Simulate camera/app pipelines that recompress frames before inference."""

    def __init__(self, probability: float, quality_range: tuple[int, int]):
        self.probability = probability
        self.quality_range = quality_range

    def __call__(self, image: Image.Image) -> Image.Image:
        if random.random() >= self.probability:
            return image
        quality = random.randint(*self.quality_range)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=False)
        buffer.seek(0)
        with Image.open(buffer) as compressed:
            return compressed.convert(image.mode).copy()


class ManifestDataset(Dataset):
    def __init__(self, manifest_path: str | Path, split: str, transform: Any):
        with Path(manifest_path).open("r", encoding="utf-8-sig", newline="") as handle:
            self.rows = [
                row for row in csv.DictReader(handle)
                if row["status"] == "included" and row["split"] == split
            ]
        if not self.rows:
            raise ValueError(f"No included samples for split '{split}' in {manifest_path}")
        self.transform = transform

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int]:
        row = self.rows[index]
        with Image.open(row["source_path"]) as image:
            image.load()
            tensor = self.transform(image)
        return tensor, int(row["label_index"])

    @property
    def targets(self) -> list[int]:
        return [int(row["label_index"]) for row in self.rows]


class BalancedBatchSampler(BatchSampler):
    """Draw equal class counts per batch without changing the validation/test protocol."""

    def __init__(self, targets: list[int], batch_size: int, seed: int = 20260731):
        self.targets = targets
        self.batch_size = batch_size
        self.seed = seed
        self.class_indices = {label: [i for i, target in enumerate(targets) if target == label] for label in range(len(CLASS_NAMES))}
        self.classes = [label for label, values in self.class_indices.items() if values]
        self.batches = len(targets) // batch_size

    def __iter__(self):
        generator = torch.Generator().manual_seed(self.seed)
        per_class = max(1, self.batch_size // len(self.classes))
        for _ in range(self.batches):
            batch = []
            for label in self.classes:
                indices = self.class_indices[label]
                choices = torch.randint(len(indices), (per_class,), generator=generator).tolist()
                batch.extend(indices[index] for index in choices)
            if len(batch) > self.batch_size:
                batch = batch[: self.batch_size]
            while len(batch) < self.batch_size:
                label = self.classes[len(batch) % len(self.classes)]
                indices = self.class_indices[label]
                batch.append(indices[int(torch.randint(len(indices), (1,), generator=generator))])
            yield batch

    def __len__(self) -> int:
        return self.batches


def build_transforms(config: dict, training: bool):
    input_size = int(config["input_size"])
    channels = int(config["input_channels"])
    augmentation = config.get("augmentation", {})
    operations = []
    if training:
        operations.extend([
            transforms.RandomResizedCrop(
                input_size,
                scale=(0.85, 1.0),
                ratio=(0.9, 1.1),
                interpolation=InterpolationMode.BILINEAR,
            ),
            transforms.RandomHorizontalFlip(
                p=float(augmentation.get("horizontal_flip_probability", 0.5))
            ),
            transforms.RandomAffine(
                degrees=float(augmentation.get("rotation_degrees", 8)),
                translate=(
                    float(augmentation.get("translate_fraction", 0.08)),
                    float(augmentation.get("translate_fraction", 0.08)),
                ),
                scale=tuple(augmentation.get("scale", [0.9, 1.1])),
                interpolation=InterpolationMode.BILINEAR,
            ),
        ])
    else:
        operations.append(
            transforms.Resize((input_size, input_size), interpolation=InterpolationMode.BILINEAR)
        )
    if channels == 3:
        operations.append(transforms.Grayscale(num_output_channels=3))
    else:
        operations.append(transforms.Grayscale(num_output_channels=1))
    if training:
        operations.append(
            transforms.ColorJitter(
                brightness=float(augmentation.get("brightness", 0.0)),
                contrast=float(augmentation.get("contrast", 0.0)),
            )
        )
        blur_kernel = int(augmentation.get("blur_kernel_size", 3))
        if blur_kernel % 2 == 0:
            blur_kernel += 1
        operations.append(
            transforms.RandomApply(
                [
                    transforms.GaussianBlur(
                        kernel_size=blur_kernel,
                        sigma=tuple(augmentation.get("blur_sigma", [0.1, 1.8])),
                    )
                ],
                p=float(augmentation.get("blur_probability", 0.0)),
            )
        )
        operations.append(
            RandomJpegCompression(
                probability=float(augmentation.get("jpeg_probability", 0.0)),
                quality_range=tuple(augmentation.get("jpeg_quality", [45, 90])),
            )
        )
    operations.extend([
        transforms.ToTensor(),
    ])
    if training:
        operations.append(
            transforms.RandomErasing(
                p=float(augmentation.get("occlusion_probability", 0.0)),
                scale=tuple(augmentation.get("occlusion_scale", [0.02, 0.18])),
                ratio=tuple(augmentation.get("occlusion_ratio", [0.3, 3.3])),
                value=0.0,
            )
        )
    operations.append(
        transforms.Normalize(
            mean=config["normalization"]["mean"],
            std=config["normalization"]["std"],
        )
    )
    return transforms.Compose(operations)


def class_weights(targets: list[int]) -> torch.Tensor:
    counts = Counter(targets)
    total = len(targets)
    weights = [total / (len(CLASS_NAMES) * counts[index]) for index in range(len(CLASS_NAMES))]
    tensor = torch.tensor(weights, dtype=torch.float32)
    return tensor / tensor.mean()


def create_loader(
    manifest_path: str | Path,
    split: str,
    config: dict,
    training: bool,
    batch_size_override: int | None = None,
) -> tuple[ManifestDataset, DataLoader]:
    dataset = ManifestDataset(
        manifest_path,
        split,
        build_transforms(config, training=training),
    )
    workers = int(config.get("num_workers", 0))
    sampler = None
    batch_sampler = None
    sampling = config.get("sampling", "shuffle")
    if training and sampling == "weighted":
        weights = class_weights(dataset.targets)
        sample_weights = torch.tensor(
            [float(weights[target]) for target in dataset.targets],
            dtype=torch.double,
        )
        sampler = WeightedRandomSampler(
            sample_weights,
            num_samples=len(sample_weights),
            replacement=True,
        )
    elif training and sampling == "balanced_batch":
        batch_sampler = BalancedBatchSampler(dataset.targets, int(config["batch_size"]), int(config.get("seed", 20260731)))
    loader_common = {
        "num_workers": workers,
        "pin_memory": torch.cuda.is_available(),
        "persistent_workers": workers > 0,
    }
    if batch_sampler is not None:
        loader = DataLoader(dataset, batch_sampler=batch_sampler, **loader_common)
    else:
        loader = DataLoader(
            dataset,
            batch_size=batch_size_override or int(config["batch_size"]),
            shuffle=training and sampler is None,
            sampler=sampler,
            drop_last=training,
            **loader_common,
        )
    return dataset, loader

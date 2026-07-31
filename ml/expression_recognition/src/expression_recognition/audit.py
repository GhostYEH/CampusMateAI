from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, UnidentifiedImageError
from sklearn.model_selection import train_test_split
from tqdm import tqdm

from .constants import CLASS_NAMES, CLASS_TO_INDEX
from .utils import save_json


@dataclass
class ImageRecord:
    source_path: str
    original_split: str
    split: str
    label: str
    label_index: int
    sha256: str
    width: int
    height: int
    channels: int
    image_format: str
    status: str = "included"
    reason: str = ""
    canonical_path: str = ""


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(block_size):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_image(path: Path, original_split: str, label: str) -> ImageRecord:
    digest = sha256_file(path)
    try:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            channels = len(image.getbands())
            image_format = image.format or ""
    except (OSError, ValueError, UnidentifiedImageError) as error:
        return ImageRecord(
            str(path.resolve()), original_split, "", label, CLASS_TO_INDEX[label],
            digest, 0, 0, 0, "", "quarantined", f"decode_error:{type(error).__name__}", "",
        )
    issues = []
    if (width, height) != (48, 48):
        issues.append(f"unexpected_size:{width}x{height}")
    if channels != 1:
        issues.append(f"unexpected_channels:{channels}")
    if image_format.upper() not in {"JPEG", "JPG"}:
        issues.append(f"unexpected_format:{image_format}")
    status = "quarantined" if issues else "included"
    return ImageRecord(
        str(path.resolve()), original_split, original_split, label, CLASS_TO_INDEX[label],
        digest, width, height, channels, image_format, status, ";".join(issues), "",
    )


def discover_images(dataset_root: Path) -> list[tuple[Path, str, str]]:
    discovered: list[tuple[Path, str, str]] = []
    for split in ("train", "test"):
        for label in CLASS_NAMES:
            directory = dataset_root / split / label
            if not directory.is_dir():
                raise FileNotFoundError(f"Missing dataset directory: {directory}")
            for path in sorted(directory.iterdir(), key=lambda value: value.name.casefold()):
                if path.is_file():
                    discovered.append((path, split, label))
    return discovered


def apply_duplicate_policy(records: list[ImageRecord]) -> dict[str, int]:
    hash_groups: dict[str, list[ImageRecord]] = defaultdict(list)
    for record in records:
        if record.sha256:
            hash_groups[record.sha256].append(record)

    exact_duplicate_groups = 0
    cross_split_groups = 0
    conflict_groups = 0
    for group in hash_groups.values():
        if len(group) <= 1:
            continue
        exact_duplicate_groups += 1
        valid_group = [record for record in group if record.status == "included"]
        labels = {record.label for record in valid_group}
        if len(labels) > 1:
            conflict_groups += 1
            for record in group:
                record.status = "quarantined"
                record.reason = "cross_label_hash_conflict"
                record.split = ""
            continue
        if not valid_group:
            continue
        splits = {record.original_split for record in valid_group}
        if len(splits) > 1:
            cross_split_groups += 1
        canonical = min(
            valid_group,
            key=lambda record: (
                0 if record.original_split == "test" and len(splits) > 1 else 1,
                record.source_path.casefold(),
            ),
        )
        canonical.canonical_path = canonical.source_path
        for record in valid_group:
            record.canonical_path = canonical.source_path
            if record is canonical:
                continue
            record.status = "excluded"
            record.split = ""
            record.reason = (
                "cross_split_duplicate_keep_test"
                if len(splits) > 1
                else "same_split_exact_duplicate"
            )
    return {
        "exact_duplicate_groups": exact_duplicate_groups,
        "cross_split_duplicate_groups": cross_split_groups,
        "cross_label_conflict_groups": conflict_groups,
    }


def assign_validation_split(
    records: list[ImageRecord],
    validation_fraction: float,
    seed: int,
) -> None:
    candidates = [
        record for record in records
        if record.status == "included" and record.original_split == "train"
    ]
    if not candidates:
        raise ValueError("No clean training records remain after audit")
    indices = list(range(len(candidates)))
    labels = [record.label for record in candidates]
    train_indices, validation_indices = train_test_split(
        indices,
        test_size=validation_fraction,
        random_state=seed,
        stratify=labels,
    )
    train_set = set(train_indices)
    for index, record in enumerate(candidates):
        record.split = "train" if index in train_set else "validation"
    for record in records:
        if record.status == "included" and record.original_split == "test":
            record.split = "test"


FIELDNAMES = list(ImageRecord.__dataclass_fields__.keys())


def write_csv(path: Path, rows: Iterable[ImageRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def nested_counts(records: Iterable[ImageRecord], split_field: str) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        split = getattr(record, split_field)
        counts[split][record.label] += 1
    return {
        split: {label: counter.get(label, 0) for label in CLASS_NAMES}
        for split, counter in sorted(counts.items())
    }


def audit_dataset(
    dataset_root: Path,
    output_dir: Path,
    validation_fraction: float = 0.15,
    seed: int = 20260731,
) -> dict:
    dataset_root = dataset_root.resolve()
    files = discover_images(dataset_root)
    records = [
        inspect_image(path, split, label)
        for path, split, label in tqdm(files, desc="Auditing images", unit="image")
    ]
    pre_clean_counts = nested_counts(records, "original_split")
    duplicate_stats = apply_duplicate_policy(records)
    assign_validation_split(records, validation_fraction, seed)

    included = [record for record in records if record.status == "included"]
    excluded = [record for record in records if record.status == "excluded"]
    quarantined = [record for record in records if record.status == "quarantined"]
    post_clean_counts = nested_counts(included, "split")
    reason_counts = Counter(record.reason for record in excluded + quarantined)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "included.csv", included)
    write_csv(output_dir / "excluded.csv", excluded)
    write_csv(output_dir / "quarantined.csv", quarantined)
    write_csv(output_dir / "all_records.csv", records)

    report = {
        "dataset_root": str(dataset_root),
        "seed": seed,
        "validation_fraction": validation_fraction,
        "class_order": CLASS_NAMES,
        "total_files": len(records),
        "included_files": len(included),
        "excluded_files": len(excluded),
        "quarantined_files": len(quarantined),
        "pre_clean_counts": pre_clean_counts,
        "post_clean_counts": post_clean_counts,
        "duplicate_statistics": duplicate_stats,
        "reason_counts": dict(sorted(reason_counts.items())),
        "format_counts": dict(Counter(record.image_format for record in records)),
        "size_counts": dict(Counter(f"{record.width}x{record.height}" for record in records)),
        "channel_counts": dict(Counter(str(record.channels) for record in records)),
    }
    save_json(output_dir / "audit_report.json", report)
    with (output_dir / "audit_report.txt").open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and manifest the FER-style dataset.")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--validation-fraction", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=20260731)
    args = parser.parse_args()
    report = audit_dataset(
        args.dataset_root,
        args.output_dir,
        args.validation_fraction,
        args.seed,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

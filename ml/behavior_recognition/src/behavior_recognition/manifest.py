from __future__ import annotations

import csv
import hashlib
import random
import re
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
from typing import Sequence

from .constants import CLASS_TO_INDEX
from .records import ManifestRecord, SourceSpec
from .yolo import parse_yolo_line, sanitize_box

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png")


def infer_group_id(source: str, stem: str) -> str:
    if re.fullmatch(r"\d{8,}", stem):
        token = stem[:4]
    else:
        match = re.match(r"([A-Za-z_-]+|\d{1,4})", stem)
        token = match.group(1) if match else stem
    return f"{source}:{token}"


def split_group_ids(grouped: dict[str, int], seed: int) -> dict[str, set[str]]:
    if not grouped:
        return {"train": set(), "val": set(), "test": set()}
    rng = random.Random(seed)
    decorated = [(group, count, rng.random()) for group, count in grouped.items()]
    ordered = sorted(decorated, key=lambda item: (-item[1], item[2], item[0]))
    result = {"train": set(), "val": set(), "test": set()}
    totals = {key: 0 for key in result}
    targets = {"train": 0.70, "val": 0.15, "test": 0.15}
    initial = ("train", "val", "test")
    for index, (group, count, _) in enumerate(ordered):
        if index < len(initial):
            split = initial[index]
        else:
            overall = max(1, sum(totals.values()))
            split = min(result, key=lambda key: totals[key] / (targets[key] * overall))
        result[split].add(group)
        totals[split] += count
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_image(root: Path, split: str, stem: str) -> Path | None:
    directory = root / "images" / split
    for suffix in IMAGE_SUFFIXES:
        candidate = directory / f"{stem}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def build_manifest(
    specs: Sequence[SourceSpec], output_dir: Path, seed: int
) -> dict[str, list[ManifestRecord]]:
    pending: list[ManifestRecord] = []
    seen_images: dict[str, Path] = {}
    for spec in specs:
        if not spec.root.is_dir():
            if spec.required_for_training:
                raise FileNotFoundError(f"Required source is missing: {spec.root}")
            continue
        for split_dir in ("train", "val", "test"):
            label_dir = spec.root / "labels" / split_dir
            if not label_dir.is_dir():
                continue
            for label_path in sorted(label_dir.glob("*.txt")):
                image_path = _find_image(spec.root, split_dir, label_path.stem)
                if image_path is None:
                    continue
                image_hash = _sha256(image_path)
                prior = seen_images.get(image_hash)
                if prior is not None and prior.resolve() != image_path.resolve():
                    continue
                seen_images[image_hash] = image_path
                group_id = infer_group_id(spec.name, label_path.stem)
                for box_index, line in enumerate(
                    label_path.read_text(encoding="utf-8").splitlines()
                ):
                    if not line.strip():
                        continue
                    try:
                        raw_box = parse_yolo_line(line)
                    except ValueError:
                        continue
                    box, _ = sanitize_box(raw_box)
                    target_name = spec.class_map.get(raw_box.class_id)
                    if box is None or target_name not in CLASS_TO_INDEX:
                        continue
                    pending.append(
                        ManifestRecord(
                            sample_id=f"{spec.name}:{label_path.stem}:{box_index}",
                            source=spec.name,
                            image_path=str(image_path.resolve()),
                            label_path=str(label_path.resolve()),
                            source_class_id=box.class_id,
                            target_name=target_name,
                            target_index=CLASS_TO_INDEX[target_name],
                            split="",
                            group_id=group_id,
                            center_x=box.center_x,
                            center_y=box.center_y,
                            width=box.width,
                            height=box.height,
                            sha256=image_hash,
                        )
                    )
    group_counts = Counter(record.group_id for record in pending)
    allocation = split_group_ids(dict(group_counts), seed)
    owner = {group: split for split, groups in allocation.items() for group in groups}
    manifests = {"train": [], "val": [], "test": []}
    for record in pending:
        split = owner[record.group_id]
        manifests[split].append(replace(record, split=split))
    output_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = list(ManifestRecord.__dataclass_fields__)
    for split, records in manifests.items():
        with (output_dir / f"{split}.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(asdict(record) for record in records)
    return manifests

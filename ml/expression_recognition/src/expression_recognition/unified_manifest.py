"""Unified multi-source expression dataset manifest builder.

Auto-detects every expression dataset under a root directory and merges them
into one auditable manifest that the training/evaluation pipeline consumes.

Supported on-disk layouts (all detected automatically, no hard-coded root):
  1. Class-folder layout (FER2013 style):
       <source>/<split>/<class>/*.<img>     e.g. 2013/train/angry/...
  2. Mixed train/test class-folder layout (archive style):
       <source>/<Train|Test>/<class>/*.<img> + optional labels.csv relabel
  3. Numeric-folder + CSV-label layout (RAF-DB style):
       <source>/<train|test>/<1..7>/*.<img>  + train_labels.csv / test_labels.csv

All sources are unified onto the Android contract class order:
    angry, disgust, fear, happy, neutral, sad, surprise

Cleaning rules (read-only; raw files are never modified):
  * SHA-256 exact deduplication across ALL sources at once.
  * Cross-label hash conflicts are quarantined (label noise, never coerced).
  * Cross-split duplicates keep the test-side canonical copy so the same image
    can never appear in both train and validation/test.
  * Train-pool images are stratified into train/validation by canonical label.
  * Every image originally in a test split is pooled into one independent test
    set used only for final evaluation.
"""

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


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SPLIT_KEYWORDS = {"train": "train", "test": "test", "val": "validation", "validation": "validation"}

# Text/numeric labels found on disk -> canonical class. Labels not present here
# (e.g. "contempt", "other", "unknown") are intentionally unmapped and dropped.
TEXT_LABEL_MAP = {
    "angry": "angry", "anger": "angry",
    "disgust": "disgust", "disgusted": "disgust",
    "fear": "fear", "fearful": "fear", "scared": "fear",
    "happy": "happy", "happiness": "happy", "smile": "happy",
    "neutral": "neutral",
    "sad": "sad", "sadness": "sad",
    "surprise": "surprise", "surprised": "surprise", "surpris": "surprise",
}

# RAF-DB compound label coding (verified by the 12,271 train-image count and
# the surprise<fear<disgust<angry<happy class-size ordering on disk).
RAFDB_NUMERIC_MAP = {
    "1": "surprise",
    "2": "fear",
    "3": "disgust",
    "4": "happy",
    "5": "sad",
    "6": "angry",
    "7": "neutral",
}


@dataclass
class UnifiedRecord:
    source_path: str
    source: str
    original_split: str
    split: str
    raw_label: str
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


def load_csv_labels(dataset_root: Path) -> dict[str, str]:
    """Return {normalized_image_basename: raw_label_string} from CSV files.

    Handles both RAF-DB style (image,label) and FER+ style (,pth,label,relFCs).
    """
    mapping: dict[str, str] = {}
    for csv_path in sorted(dataset_root.rglob("*.csv"), key=lambda p: str(p).casefold()):
        try:
            with csv_path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
                rows = list(csv.DictReader(handle))
        except OSError:
            continue
        if not rows:
            continue
        header = {key.casefold(): key for key in rows[0].keys()}
        path_key = next((header[key] for key in ("pth", "path", "filepath", "file", "image") if key in header), None)
        label_key = next((header[key] for key in ("label", "emotion", "expression") if key in header), None)
        if not path_key or not label_key:
            continue
        for row in rows:
            ref = (row.get(path_key) or "").strip()
            label = (row.get(label_key) or "").strip()
            if not ref or not label:
                continue
            # CSV paths may be "anger/image0000006.jpg" or "train_00001_aligned.jpg".
            basename = Path(ref.replace("/", "\\")).name.casefold()
            mapping[basename] = label
    return mapping


def canonical_label(raw: str) -> str | None:
    """Map any on-disk label onto the 7-class contract, or None to drop."""
    if not raw:
        return None
    key = raw.strip().casefold()
    if key in CLASS_TO_INDEX:
        return key
    if key in TEXT_LABEL_MAP:
        return TEXT_LABEL_MAP[key]
    if key in RAFDB_NUMERIC_MAP:
        return RAFDB_NUMERIC_MAP[key]
    return None


def detect_split_and_raw_label(source_root: Path, image_path: Path) -> tuple[str, str, str]:
    """Infer (original_split, raw_label, evidence) from path layout.

    Looks for a split keyword anywhere in the path; the label is the next path
    component after the split (class/numeric folder). Falls back to the image's
    immediate parent folder as the label.
    """
    parts = image_path.relative_to(source_root).parts
    lower_parts = [part.casefold() for part in parts]
    split = ""
    split_index = -1
    for index, part in enumerate(lower_parts):
        if part in SPLIT_KEYWORDS:
            split = SPLIT_KEYWORDS[part]
            split_index = index
            break
    raw_label = ""
    evidence = "unresolved"
    if split_index >= 0 and split_index + 1 < len(parts):
        raw_label = parts[split_index + 1]
        evidence = "directory"
    elif len(parts) >= 2:
        raw_label = parts[-2]
        evidence = "parent_directory"
    return split, raw_label, evidence


def discover_images(root: Path) -> list[UnifiedRecord]:
    """Walk every dataset subdirectory under root and collect image records."""
    root = root.resolve()
    records: list[UnifiedRecord] = []
    sources = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name.casefold())
    for source in sources:
        csv_labels = load_csv_labels(source)
        image_paths = sorted(
            (p for p in source.rglob("*") if p.is_file() and p.suffix.casefold() in IMAGE_EXTENSIONS),
            key=lambda p: str(p).casefold(),
        )
        for path in tqdm(image_paths, desc=f"scan {source.name}", unit="img", leave=False):
            original_split, folder_label, evidence = detect_split_and_raw_label(source, path)
            # Prefer the folder label: it is unambiguous (one image -> one folder).
            # Fall back to a CSV label only when the folder label cannot be mapped
            # (e.g. a flat CSV-only dataset with no class subfolders). This avoids
            # cross-split filename collisions in FER+-style relabel CSVs.
            label = canonical_label(folder_label)
            raw_label = folder_label
            if label is None:
                basename = path.name.casefold()
                csv_label = csv_labels.get(basename)
                if csv_label is not None:
                    raw_label = csv_label
                    label = canonical_label(csv_label)
                    evidence = "csv.label"
            digest = sha256_file(path)
            try:
                with Image.open(path) as image:
                    image.load()
                    width, height = image.size
                    channels = len(image.getbands())
                    image_format = image.format or ""
            except (OSError, ValueError, UnidentifiedImageError) as error:
                records.append(UnifiedRecord(
                    str(path.resolve()), source.name, original_split, "", raw_label,
                    "", -1, digest, 0, 0, 0, "", "quarantined", f"decode_error:{type(error).__name__}", "",
                ))
                continue
            if label is None:
                records.append(UnifiedRecord(
                    str(path.resolve()), source.name, original_split, "", raw_label,
                    "", -1, digest, width, height, channels, image_format,
                    "excluded", f"unmapped_label:{raw_label}", "",
                ))
                continue
            records.append(UnifiedRecord(
                str(path.resolve()), source.name, original_split, "", raw_label,
                label, CLASS_TO_INDEX[label], digest, width, height, channels, image_format,
                "included", evidence, "",
            ))
    return records


def apply_duplicate_policy(records: list[UnifiedRecord]) -> dict[str, int]:
    """Globally deduplicate by SHA-256; quarantine cross-label conflicts."""
    hash_groups: dict[str, list[UnifiedRecord]] = defaultdict(list)
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
                else "same_source_exact_duplicate"
            )
    return {
        "exact_duplicate_groups": exact_duplicate_groups,
        "cross_split_duplicate_groups": cross_split_groups,
        "cross_label_conflict_groups": conflict_groups,
    }


def assign_splits(records: list[UnifiedRecord], validation_fraction: float, seed: int) -> None:
    """Stratified train/validation split of the train pool; test pool is held out."""
    train_pool = [
        record for record in records
        if record.status == "included" and record.original_split == "train"
    ]
    if not train_pool:
        raise ValueError("No clean training records remain after deduplication")
    indices = list(range(len(train_pool)))
    labels = [record.label for record in train_pool]
    train_indices, validation_indices = train_test_split(
        indices,
        test_size=validation_fraction,
        random_state=seed,
        stratify=labels,
    )
    train_set = set(train_indices)
    for index, record in enumerate(train_pool):
        record.split = "train" if index in train_set else "validation"
    for record in records:
        if record.status == "included" and record.original_split == "test":
            record.split = "test"


FIELDNAMES = list(UnifiedRecord.__dataclass_fields__.keys())


def write_csv(path: Path, rows: Iterable[UnifiedRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def nested_counts(records: Iterable[UnifiedRecord], split_field: str) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        split = getattr(record, split_field)
        if record.label in CLASS_NAMES:
            counts[split][record.label] += 1
    return {
        split: {label: counter.get(label, 0) for label in CLASS_NAMES}
        for split, counter in sorted(counts.items())
        if split
    }


def build_unified_manifest(
    dataset_root: Path,
    output_dir: Path,
    validation_fraction: float = 0.15,
    seed: int = 20260731,
) -> dict:
    dataset_root = dataset_root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    records = discover_images(dataset_root)
    duplicate_stats = apply_duplicate_policy(records)
    assign_splits(records, validation_fraction, seed)

    included = [r for r in records if r.status == "included"]
    excluded = [r for r in records if r.status == "excluded"]
    quarantined = [r for r in records if r.status == "quarantined"]

    write_csv(output_dir / "included.csv", included)
    write_csv(output_dir / "excluded.csv", excluded)
    write_csv(output_dir / "quarantined.csv", quarantined)
    write_csv(output_dir / "all_records.csv", records)

    # Per-source inventory summary.
    sources_summary = []
    for source_name in sorted({r.source for r in records}):
        src_records = [r for r in records if r.source == source_name]
        sources_summary.append({
            "name": source_name,
            "image_count": len(src_records),
            "labels": dict(Counter(r.label for r in src_records if r.label)),
            "raw_labels": dict(Counter(r.raw_label for r in src_records)),
            "splits": dict(Counter(r.original_split for r in src_records)),
            "formats": dict(Counter(r.image_format for r in src_records if r.image_format)),
            "dimensions": dict(Counter(f"{r.width}x{r.height}" for r in src_records if r.width)),
            "channels": dict(Counter(str(r.channels) for r in src_records if r.channels)),
            "included": sum(1 for r in src_records if r.status == "included"),
            "excluded": sum(1 for r in src_records if r.status == "excluded"),
            "quarantined": sum(1 for r in src_records if r.status == "quarantined"),
        })

    label_mapping = {
        "canonical_class_order": CLASS_NAMES,
        "2013": {name: name for name in CLASS_NAMES},
        "archive (3)": {
            "anger": "angry", "disgust": "disgust", "fear": "fear",
            "happy": "happy", "neutral": "neutral", "sad": "sad",
            "surprise": "surprise", "contempt": None,
            "note": "CSV relabel preferred when present; contempt dropped (not in Android contract).",
        },
        "DATASET": {
            "mapping": RAFDB_NUMERIC_MAP,
            "dataset": "RAF-DB aligned (verified by 12,271-image train count)",
        },
        "unmapped_policy": "Drop unmapped labels; never coerce contempt/other/unknown into a canonical class.",
    }
    (output_dir / "label_mapping.json").write_text(
        json.dumps(label_mapping, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    report = {
        "dataset_root": str(dataset_root),
        "seed": seed,
        "validation_fraction": validation_fraction,
        "class_order": CLASS_NAMES,
        "total_files": len(records),
        "included_files": len(included),
        "excluded_files": len(excluded),
        "quarantined_files": len(quarantined),
        "sources": sources_summary,
        "pre_clean_counts": nested_counts(records, "original_split"),
        "post_clean_counts": nested_counts(included, "split"),
        "duplicate_statistics": duplicate_stats,
        "label_mapping": label_mapping,
    }
    save_json(output_dir / "dataset_inventory.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-detect and merge every expression dataset into one unified manifest."
    )
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--validation-fraction", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=20260731)
    args = parser.parse_args()
    report = build_unified_manifest(
        args.dataset_root, args.output_dir, args.validation_fraction, args.seed
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

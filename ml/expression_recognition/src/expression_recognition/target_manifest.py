"""Build privacy-audited manifests for consented front-camera expression data."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from .constants import CLASS_NAMES, CLASS_TO_INDEX
from .unified_manifest import sha256_file


REQUIRED_FIELDS = (
    "path",
    "label",
    "subject_id",
    "session_id",
    "device",
    "platform",
    "lighting",
    "pose",
    "occlusion",
    "consent",
)


@dataclass(frozen=True)
class TargetRecord:
    path: str
    label: str
    label_index: int
    subject_id: str
    session_id: str
    device: str
    platform: str
    lighting: str
    pose: str
    occlusion: str
    split: str
    sha256: str
    status: str
    reason: str


@dataclass(frozen=True)
class ManifestSummary:
    rows: list[TargetRecord]
    included_count: int
    excluded_count: int


def _clean(row: dict[str, str], field: str) -> str:
    return (row.get(field) or "").strip()


def _subject_split_map(records: list[TargetRecord], seed: int) -> dict[str, str]:
    counts = Counter(record.subject_id for record in records if record.status == "included")
    ordered = sorted(
        counts,
        key=lambda subject: (
            -counts[subject],
            hashlib.sha256(f"{seed}:{subject}".encode("utf-8")).hexdigest(),
        ),
    )
    splits = ("train", "test", "validation")
    targets = {"train": 0.65, "validation": 0.15, "test": 0.20}
    totals = {name: 0 for name in splits}
    ownership: dict[str, str] = {}
    sample_total = max(1, sum(counts.values()))
    for index, subject in enumerate(ordered):
        if index < len(splits):
            split = splits[index]
        else:
            split = min(
                splits,
                key=lambda name: (totals[name] + counts[subject]) / (targets[name] * sample_total),
            )
        ownership[subject] = split
        totals[split] += counts[subject]
    return ownership


def _resolve_sample(dataset_root: Path, relative_path: str) -> Path | None:
    candidate = (dataset_root / relative_path).resolve()
    try:
        candidate.relative_to(dataset_root)
    except ValueError:
        return None
    return candidate


def _write_manifest(output_dir: Path, rows: list[TargetRecord]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = list(TargetRecord.__dataclass_fields__)
    for name, selected in (
        ("all_records.csv", rows),
        ("included.csv", [row for row in rows if row.status == "included"]),
        ("excluded.csv", [row for row in rows if row.status == "excluded"]),
    ):
        with (output_dir / name).open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(asdict(row) for row in selected)


def build_target_manifest(
    dataset_root: Path,
    output_dir: Path,
    *,
    seed: int = 20260825,
) -> ManifestSummary:
    """Validate annotations, deduplicate images, and split by subject/session."""
    dataset_root = dataset_root.resolve()
    annotations = dataset_root / "annotations.csv"
    with annotations.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing_columns = set(REQUIRED_FIELDS) - set(reader.fieldnames or ())
        if missing_columns:
            raise ValueError(f"Missing annotation columns: {sorted(missing_columns)}")
        source_rows = list(reader)

    records: list[TargetRecord] = []
    hash_owners: dict[str, int] = {}
    conflicting_hashes: set[str] = set()
    for source in source_rows:
        values = {field: _clean(source, field) for field in REQUIRED_FIELDS}
        label = values["label"].casefold()
        consented = values["consent"].casefold() in {"1", "true", "yes", "y"}
        sample = _resolve_sample(dataset_root, values["path"])
        reason = ""
        digest = ""

        if not consented:
            reason = "missing_consent"
        elif any(not values[field] for field in REQUIRED_FIELDS if field not in {"consent"}):
            reason = "missing_metadata"
        elif label not in CLASS_TO_INDEX:
            reason = "invalid_label"
        elif sample is None:
            reason = "path_outside_dataset"
        elif not sample.is_file():
            reason = "missing_file"
        else:
            digest = sha256_file(sample)
            if digest in conflicting_hashes:
                reason = "cross_label_hash_conflict"
            elif digest in hash_owners:
                prior_index = hash_owners[digest]
                prior = records[prior_index]
                if prior.label != label:
                    records[prior_index] = replace(
                        prior,
                        split="",
                        status="excluded",
                        reason="cross_label_hash_conflict",
                    )
                    conflicting_hashes.add(digest)
                    reason = "cross_label_hash_conflict"
                else:
                    reason = "duplicate_sha256"

        included = not reason
        if included:
            hash_owners[digest] = len(records)
        subject_id = values["subject_id"]
        session_id = values["session_id"]
        records.append(TargetRecord(
            path=str(sample) if sample is not None else values["path"],
            label=label if label in CLASS_NAMES else values["label"],
            label_index=CLASS_TO_INDEX.get(label, -1),
            subject_id=subject_id,
            session_id=session_id,
            device=values["device"],
            platform=values["platform"].casefold(),
            lighting=values["lighting"].casefold(),
            pose=values["pose"].casefold(),
            occlusion=values["occlusion"].casefold(),
            split="",
            sha256=digest,
            status="included" if included else "excluded",
            reason=reason,
        ))

    ownership = _subject_split_map(records, seed)
    records = [
        replace(record, split=ownership[record.subject_id])
        if record.status == "included" else record
        for record in records
    ]
    _write_manifest(output_dir, records)
    return ManifestSummary(
        rows=records,
        included_count=sum(row.status == "included" for row in records),
        excluded_count=sum(row.status == "excluded" for row in records),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a consented target-domain expression manifest.")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260825)
    args = parser.parse_args()
    summary = build_target_manifest(args.dataset_root, args.output_dir, seed=args.seed)
    print(f"included={summary.included_count} excluded={summary.excluded_count}")


if __name__ == "__main__":
    main()

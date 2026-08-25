"""Build leak-resistant manifests for front-camera behavior events."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from dataclasses import asdict, dataclass, replace
from pathlib import Path


PRODUCT_LABELS = (
    "STUDY_ACTIVITY",
    "PHONE_INTERACTION",
    "NO_VISIBLE_STUDY",
    "UNCERTAIN",
)
REQUIRED_FIELDS = (
    "video_path",
    "subject_id",
    "session_id",
    "device",
    "start_ms",
    "end_ms",
    "label",
    "reviewer_id",
    "consent",
)


@dataclass(frozen=True)
class EventRecord:
    event_id: str
    video_path: str
    subject_id: str
    session_id: str
    device: str
    start_ms: int
    end_ms: int
    label: str
    reviewer_id: str
    video_sha256: str
    split: str
    status: str
    reason: str


@dataclass(frozen=True)
class EventManifestSummary:
    rows: list[EventRecord]
    included_count: int
    excluded_count: int


def _subject_split_map(records: list[EventRecord], seed: int) -> dict[str, str]:
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
    event_total = max(1, sum(counts.values()))
    for index, subject in enumerate(ordered):
        if index < len(splits):
            split = splits[index]
        else:
            split = min(
                splits,
                key=lambda name: (totals[name] + counts[subject]) / (targets[name] * event_total),
            )
        ownership[subject] = split
        totals[split] += counts[subject]
    return ownership


def _resolve_video(root: Path, relative_path: str) -> Path | None:
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def build_event_manifest(
    dataset_root: Path,
    output_dir: Path,
    *,
    seed: int = 20260825,
) -> EventManifestSummary:
    dataset_root = dataset_root.resolve()
    with (dataset_root / "annotations.csv").open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = set(REQUIRED_FIELDS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Missing annotation columns: {sorted(missing)}")
        annotations = list(reader)

    records: list[EventRecord] = []
    video_hash_cache: dict[str, str] = {}
    for index, annotation in enumerate(annotations):
        value = {field: (annotation.get(field) or "").strip() for field in REQUIRED_FIELDS}
        label = value["label"].upper()
        consented = value["consent"].casefold() in {"1", "true", "yes", "y"}
        video = _resolve_video(dataset_root, value["video_path"])
        try:
            start_ms = int(value["start_ms"])
            end_ms = int(value["end_ms"])
        except ValueError:
            start_ms = -1
            end_ms = -1

        reason = ""
        if not consented:
            reason = "missing_consent"
        elif any(not value[field] for field in REQUIRED_FIELDS if field != "consent"):
            reason = "missing_metadata"
        elif label not in PRODUCT_LABELS:
            reason = "invalid_label"
        elif start_ms < 0 or end_ms <= start_ms:
            reason = "invalid_time_range"
        elif video is None:
            reason = "path_outside_dataset"
        elif not video.is_file():
            reason = "missing_video"

        included = not reason
        video_hash = ""
        if included and video is not None:
            video_key = str(video)
            if video_key not in video_hash_cache:
                video_hash_cache[video_key] = _sha256_file(video)
            video_hash = video_hash_cache[video_key]
        event_identity = f"{value['subject_id']}:{value['session_id']}:{value['video_path']}:{start_ms}:{end_ms}:{index}"
        event_id = hashlib.sha256(event_identity.encode("utf-8")).hexdigest()[:20]
        records.append(EventRecord(
            event_id=event_id,
            video_path=str(video) if video is not None else value["video_path"],
            subject_id=value["subject_id"],
            session_id=value["session_id"],
            device=value["device"],
            start_ms=start_ms,
            end_ms=end_ms,
            label=label,
            reviewer_id=value["reviewer_id"],
            video_sha256=video_hash,
            split="",
            status="included" if included else "excluded",
            reason=reason,
        ))

    subjects_by_hash: dict[str, set[str]] = {}
    for record in records:
        if record.status == "included":
            subjects_by_hash.setdefault(record.video_sha256, set()).add(record.subject_id)
    cross_subject_hashes = {
        digest for digest, subjects in subjects_by_hash.items()
        if len(subjects) > 1
    }
    records = [
        replace(record, split="", status="excluded", reason="duplicate_video_cross_subject")
        if record.status == "included" and record.video_sha256 in cross_subject_hashes
        else record
        for record in records
    ]

    conflicts: set[int] = set()
    by_video: dict[str, list[int]] = {}
    for index, record in enumerate(records):
        if record.status == "included":
            by_video.setdefault(record.video_path, []).append(index)
    for indices in by_video.values():
        ordered = sorted(indices, key=lambda item: (records[item].start_ms, records[item].end_ms))
        for position, left_index in enumerate(ordered):
            left = records[left_index]
            for right_index in ordered[position + 1:]:
                right = records[right_index]
                if right.start_ms >= left.end_ms:
                    break
                if left.label != right.label:
                    conflicts.update((left_index, right_index))
    for index in conflicts:
        records[index] = replace(
            records[index],
            split="",
            status="excluded",
            reason="overlapping_label_conflict",
        )

    ownership = _subject_split_map(records, seed)
    records = [
        replace(record, split=ownership[record.subject_id])
        if record.status == "included" else record
        for record in records
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    fields = list(EventRecord.__dataclass_fields__)
    for filename, selected in (
        ("all_events.csv", records),
        ("included_events.csv", [row for row in records if row.status == "included"]),
        ("excluded_events.csv", [row for row in records if row.status == "excluded"]),
    ):
        with (output_dir / filename).open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(asdict(row) for row in selected)

    return EventManifestSummary(
        rows=records,
        included_count=sum(row.status == "included" for row in records),
        excluded_count=sum(row.status == "excluded" for row in records),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a consented front-camera behavior event manifest.")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260825)
    args = parser.parse_args()
    summary = build_event_manifest(args.dataset_root, args.output_dir, seed=args.seed)
    print(f"included={summary.included_count} excluded={summary.excluded_count}")


if __name__ == "__main__":
    main()

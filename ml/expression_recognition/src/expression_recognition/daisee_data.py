from __future__ import annotations

import argparse
import csv
import json
import math
import re
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from torch.utils.data import Dataset

SPLIT_DIRS = {"train": "Train", "validation": "Validation", "test": "Test"}
LABEL_FILES = {"train": "TrainLabels.csv", "validation": "ValidationLabels.csv", "test": "TestLabels.csv"}
STATE_COLUMNS = ("Boredom", "Confusion", "Frustration")
SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
_WORKER = threading.local()


@dataclass(frozen=True)
class Clip:
    split: str
    subject_id: str
    clip_id: str
    video_path: Path | None
    labels: tuple[int, int, int] | None
    reason: str = ""


def _read_labels(root: Path) -> tuple[dict[str, dict[str, tuple[int, int, int]]], dict[str, str]]:
    by_split: dict[str, dict[str, tuple[int, int, int]]] = {}
    subject_splits: dict[str, str] = {}
    clip_splits: dict[str, str] = {}
    for split, filename in LABEL_FILES.items():
        path = root / "Labels" / filename
        if not path.is_file():
            raise FileNotFoundError(f"Missing official DAiSEE labels: {path}")
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, skipinitialspace=True)
            fields = {field.strip() for field in (reader.fieldnames or [])}
            required = {"ClipID", *STATE_COLUMNS}
            if not required.issubset(fields):
                raise ValueError(f"{filename} must contain {sorted(required)}")
            labels: dict[str, tuple[int, int, int]] = {}
            for row_number, raw in enumerate(reader, start=2):
                row = {(key or "").strip(): (value or "").strip() for key, value in raw.items()}
                clip_id = row.get("ClipID", "")
                if not clip_id or not SAFE_ID.fullmatch(clip_id) or Path(clip_id).name != clip_id:
                    raise ValueError(f"Unsafe or empty ClipID in {filename}:{row_number}")
                clip_path = Path(clip_id)
                if clip_path.suffix.lower() not in {".avi", ".mp4"}:
                    raise ValueError(f"Unsupported DAiSEE clip extension in {filename}:{row_number}: {clip_id}")
                clip_id = clip_path.stem + ".avi"  # Normalize label and source extensions to the official clip stem.
                subject = clip_path.stem[:6]
                if not subject or not SAFE_ID.fullmatch(subject):
                    raise ValueError(f"Cannot derive a safe subject ID from {clip_id!r}")
                previous = subject_splits.setdefault(subject, split)
                if previous != split:
                    raise ValueError(f"Subject {subject} crosses DAiSEE splits {previous}/{split}")
                previous = clip_splits.setdefault(clip_id, split)
                if previous != split or clip_id in labels:
                    raise ValueError(f"Duplicate clip ID across official labels: {clip_id}")
                try:
                    values = tuple(int(row[column]) for column in STATE_COLUMNS)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Missing/non-integer state label in {filename}:{row_number}") from exc
                if any(value < 0 or value > 3 for value in values):
                    raise ValueError(f"State labels must be within 0..3 in {filename}:{row_number}")
                labels[clip_id] = values  # type: ignore[assignment]
        by_split[split] = labels
    return by_split, subject_splits


def _require_within(root: Path, path: Path, description: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{description} resolves outside the read-only dataset root: {path}") from exc
    return resolved


def _all_split_videos(split_root: Path) -> dict[str, tuple[str, Path]]:
    videos: dict[str, tuple[str, Path]] = {}
    for path in split_root.glob("*/*/*"):
        if not path.is_file() or path.suffix.lower() not in {".avi", ".mp4"}:
            continue
        resolved = path.resolve()
        try:
            resolved.relative_to(split_root.resolve())
        except ValueError as exc:
            raise ValueError(f"Video path escapes split directory: {path}") from exc
        subject, clip_name = path.parent.parent.name, path.stem + ".avi"
        if not SAFE_ID.fullmatch(subject) or not SAFE_ID.fullmatch(clip_name):
            raise ValueError(f"Unsafe subject/clip path under {split_root}: {path}")
        if clip_name in videos:
            raise ValueError(f"Duplicate clip ID in {split_root}: {clip_name}")
        videos[clip_name] = (subject, path)
    return videos


def _get_cascade(cv2: Any):
    cascade = getattr(_WORKER, "cascade", None)
    if cascade is None:
        cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(str(cascade_path))
        if cascade.empty():
            raise RuntimeError(f"Could not load Haar cascade: {cascade_path}")
        _WORKER.cascade = cascade
    return cascade


def _face_crop(cv2: Any, cascade: Any, frame: Any):
    height, width = frame.shape[:2]
    if not height or not width:
        return None
    scale = min(1.0, 480.0 / max(height, width))
    if scale < 1.0:
        small = cv2.resize(frame, (max(1, round(width * scale)), max(1, round(height * scale))))
    else:
        small = frame
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    found = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
    if len(found) == 0:
        return None
    x, y, w, h = max(found, key=lambda box: int(box[2]) * int(box[3]))
    x0, y0 = math.floor(x / scale), math.floor(y / scale)
    x1, y1 = math.ceil((x + w) / scale), math.ceil((y + h) / scale)
    pad_x, pad_y = round((x1 - x0) * 0.16), round((y1 - y0) * 0.20)
    x0, y0 = max(0, x0 - pad_x), max(0, y0 - pad_y)
    x1, y1 = min(width, x1 + pad_x), min(height, y1 + pad_y)
    crop = frame[y0:y1, x0:x1]
    return cv2.cvtColor(crop, cv2.COLOR_BGR2RGB) if crop.size else None


def _extract(clip: Clip, cache_root: Path, frames_per_clip: int) -> tuple[list[str], str]:
    import cv2  # Optional until extraction; keep package import lightweight.

    cap = cv2.VideoCapture(str(clip.video_path))
    try:
        if not cap.isOpened():
            return [], "unreadable_video"
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_count <= 0:
            return [], "empty_video"
        indices = [min(frame_count - 1, int((index + 0.5) * frame_count / frames_per_clip))
                   for index in range(frames_per_clip)]
        indices = list(dict.fromkeys(indices))
        cascade = _get_cascade(cv2)
        crops = []
        for frame_index in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if ok and frame is not None:
                crop = _face_crop(cv2, cascade, frame)
                if crop is not None:
                    crops.append(crop)
        if not crops:
            return [], "no_face"
        repeated = len(crops) < frames_per_clip
        crops.extend([crops[-1]] * (frames_per_clip - len(crops)))
        frame_dir = cache_root / "frames" / clip.split / clip.subject_id / Path(clip.clip_id).stem
        frame_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for index, crop in enumerate(crops):
            relative = Path("frames") / clip.split / clip.subject_id / Path(clip.clip_id).stem / f"{index:02d}.png"
            Image.fromarray(crop).save(cache_root / relative, format="PNG")
            paths.append(relative.as_posix())
        return paths, "repeated_last_valid_frame" if repeated else ""
    finally:
        cap.release()


def prepare_daisee(
    dataset_root: str | Path,
    output_dir: str | Path,
    frames_per_clip: int = 4,
    splits: tuple[str, ...] = ("train", "validation"),
    workers: int = 1,
    limit_per_split: int | None = None,
) -> dict[str, Any]:
    if frames_per_clip < 1 or workers < 1 or (limit_per_split is not None and limit_per_split < 1):
        raise ValueError("frames_per_clip/workers/limit_per_split must be positive")
    splits = tuple(splits)
    if not splits or len(set(splits)) != len(splits) or any(split not in SPLIT_DIRS for split in splits):
        raise ValueError(f"splits must be unique members of {tuple(SPLIT_DIRS)}")
    root, output = Path(dataset_root).resolve(), Path(output_dir).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"DAiSEE dataset root does not exist: {root}")
    try:
        output.relative_to(root)
    except ValueError:
        pass
    else:
        raise ValueError("output_dir must be outside the read-only source dataset")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output directory: {output}")
    if output == root:
        raise ValueError("output_dir cannot be the source dataset root")
    # Resolve every label source before opening it so symlinks cannot escape the read-only dataset.
    for filename in LABEL_FILES.values():
        label_path = _require_within(root, root / "Labels" / filename, "Label file")
        if not label_path.is_file():
            raise FileNotFoundError(f"Missing official DAiSEE labels: {label_path}")
    split_roots: dict[str, Path] = {}
    video_maps: dict[str, dict[str, tuple[str, Path]]] = {}
    for split in splits:
        split_root = _require_within(root, root / "DataSet" / SPLIT_DIRS[split], "Video split directory")
        if not split_root.is_dir():
            raise FileNotFoundError(f"Missing DAiSEE video split directory: {split_root}")
        split_roots[split] = split_root
        video_maps[split] = _all_split_videos(split_root)
    label_map, _ = _read_labels(root)  # Validate all official boundaries, without decoding unrequested splits.
    output.mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    for split in splits:
        split_root = split_roots[split]
        labels = label_map[split]
        videos = video_maps[split]
        clips: list[Clip] = []
        for clip_id, values in labels.items():
            subject = clip_id[:6]
            video_entry = videos.get(clip_id)
            if video_entry is not None and video_entry[0] != subject:
                raise ValueError(f"Video subject path does not match official label {clip_id}: {video_entry[0]}")
            video_path = video_entry[1] if video_entry is not None else None
            clips.append(Clip(split, subject, clip_id, video_path, values,
                              "missing_video" if video_path is None else ""))
        for clip_id, (subject, video_path) in videos.items():
            if clip_id not in labels:
                clips.append(Clip(split, subject, clip_id, video_path, None, "missing_annotation"))
        clips.sort(key=lambda item: item.clip_id)
        if limit_per_split is not None:
            clips = clips[:limit_per_split]
        ready = [clip for clip in clips if clip.video_path is not None and clip.labels is not None and not clip.reason]
        extracted: dict[str, tuple[list[str], str]] = {}
        completed = 0
        pool = ThreadPoolExecutor(max_workers=workers) if workers > 1 else None
        try:
            for offset in range(0, len(ready), 100):
                batch = ready[offset:offset + 100]
                if pool is None:
                    results = [_extract(clip, output, frames_per_clip) for clip in batch]
                else:
                    results = list(pool.map(lambda item: _extract(item, output, frames_per_clip), batch))
                extracted.update({clip.clip_id: result for clip, result in zip(batch, results)})
                completed += len(batch)
                print(f"DAiSEE {split}: {completed}/{len(ready)} videos processed", flush=True)
        finally:
            if pool is not None:
                pool.shutdown(wait=True)
        for clip in clips:
            frames, note = extracted.get(clip.clip_id, ([], ""))
            reason = clip.reason or ("" if frames else note)
            row: dict[str, Any] = {
                "split": split, "subject_id": clip.subject_id, "clip_id": clip.clip_id,
                "boredom": clip.labels[0] if clip.labels is not None else "",
                "confusion": clip.labels[1] if clip.labels is not None else "",
                "frustration": clip.labels[2] if clip.labels is not None else "",
                "frames": json.dumps(frames, ensure_ascii=False),
                "status": "included" if frames and not reason else "excluded",
                "reason": reason,
                "repeated_last_valid_frame": str(note == "repeated_last_valid_frame").lower(),
            }
            rows.append(row)
    fields = ["split", "subject_id", "clip_id", "boredom", "confusion", "frustration",
              "frames", "status", "reason", "repeated_last_valid_frame"]
    with (output / "manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    status_counts = Counter(row["status"] for row in rows)
    reason_counts = Counter(row["reason"] for row in rows if row["reason"])
    per_split = {}
    for split in splits:
        split_rows = [row for row in rows if row["split"] == split]
        per_split[split] = {
            "clips": len(split_rows),
            "included": sum(row["status"] == "included" for row in split_rows),
            "excluded": sum(row["status"] == "excluded" for row in split_rows),
            "repeated_last_valid_frame": sum(row["repeated_last_valid_frame"] == "true" for row in split_rows),
            "reason_counts": dict(sorted(Counter(row["reason"] for row in split_rows if row["reason"]).items())),
        }
    report = {"manifest": str(output / "manifest.csv"), "splits": list(splits), "clips": len(rows),
              "included": status_counts["included"], "excluded": status_counts["excluded"],
              "repeated_last_valid_frame": sum(row["repeated_last_valid_frame"] == "true" for row in rows),
              "reason_counts": dict(sorted(reason_counts.items())), "per_split": per_split}
    (output / "preparation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


class DAiSEEVideoDataset(Dataset):
    def __init__(self, manifest_path: str | Path, split: str, transform: Any, frames_per_clip: int = 4):
        if split not in SPLIT_DIRS or frames_per_clip < 1:
            raise ValueError("Invalid split or frames_per_clip")
        self.manifest_path = Path(manifest_path).resolve()
        self.cache_root = self.manifest_path.parent.resolve()
        self.transform = transform
        self.frames_per_clip = frames_per_clip
        with self.manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = [row for row in csv.DictReader(handle) if row.get("status") == "included" and row.get("split") == split]
        self.rows = []
        for row in rows:
            try:
                labels = [int(row[name]) for name in ("boredom", "confusion", "frustration")]
                frames = json.loads(row["frames"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError("Malformed included DAiSEE manifest row") from exc
            if any(label < 0 or label > 3 for label in labels):
                raise ValueError("DAiSEE labels must be in 0..3")
            if not isinstance(frames, list) or len(frames) != frames_per_clip:
                raise ValueError(f"Each included clip must contain exactly {frames_per_clip} frame paths")
            paths = []
            for relative in frames:
                if not isinstance(relative, str):
                    raise ValueError("Frame paths must be relative strings")
                candidate = (self.cache_root / relative).resolve()
                try:
                    candidate.relative_to(self.cache_root)
                except ValueError as exc:
                    raise ValueError(f"Frame path escapes cache directory: {relative}") from exc
                if not candidate.is_file():
                    raise FileNotFoundError(f"Cached DAiSEE frame is missing: {candidate}")
                paths.append(candidate)
            self.rows.append((paths, labels))
        if not self.rows:
            raise ValueError(f"No included DAiSEE clips for split {split!r}")

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        paths, labels = self.rows[index]
        tensors = []
        for path in paths:
            with Image.open(path) as image:
                image.load()
                tensors.append(self.transform(image))
        return torch.stack(tensors), torch.tensor(labels, dtype=torch.long)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare face-cropped DAiSEE video clips using official subject splits.")
    parser.add_argument("--dataset-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--frames-per-clip", type=int, default=4)
    parser.add_argument("--splits", nargs="+", choices=tuple(SPLIT_DIRS), default=["train", "validation"])
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--limit-per-split", type=int)
    args = parser.parse_args()
    print(json.dumps(prepare_daisee(args.dataset_root, args.output_dir, args.frames_per_clip,
                                    tuple(args.splits), args.workers, args.limit_per_split), indent=2))


if __name__ == "__main__":
    main()

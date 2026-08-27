from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .constants import CLASS_TO_INDEX
from .yolo import parse_yolo_line, sanitize_box


SOURCE_CLASS_MAP = {
    1: "READ",
    2: "WRITE",
    3: "PHONE_INTERACTION",
    5: "NO_VISIBLE_STUDY",
}


@dataclass(frozen=True)
class Detection:
    frame_number: int
    image_path: str
    target_name: str
    box: tuple[float, float, float, float]


@dataclass(frozen=True)
class TemporalWindow:
    window_id: str
    video_id: str
    track_id: str
    split: str
    target_name: str
    target_index: int
    frame_paths: tuple[str, ...]
    boxes: tuple[tuple[float, float, float, float], ...]


@dataclass(frozen=True)
class TemporalManifestSummary:
    windows: tuple[TemporalWindow, ...]
    video_count: int
    track_count: int
    window_count: int
    excluded_short_tracks: int


def video_id_from_stem(stem: str) -> str:
    match = re.fullmatch(r"(\d{4})\d+", stem)
    if not match:
        raise ValueError(f"Frame stem does not contain a four-digit video prefix: {stem}")
    return match.group(1)


def _box_iou(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    def corners(box):
        x, y, width, height = box
        return x - width / 2, y - height / 2, x + width / 2, y + height / 2

    lx1, ly1, lx2, ly2 = corners(left)
    rx1, ry1, rx2, ry2 = corners(right)
    intersection = max(0.0, min(lx2, rx2) - max(lx1, rx1)) * max(
        0.0, min(ly2, ry2) - max(ly1, ry1)
    )
    union = left[2] * left[3] + right[2] * right[3] - intersection
    return intersection / union if union > 0 else 0.0


def _center_distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


def _load_frames(dataset_root: Path) -> dict[str, dict[int, list[Detection]]]:
    videos: dict[str, dict[int, list[Detection]]] = {}
    for split in ("train", "val", "test"):
        image_dir = dataset_root / "images" / split
        label_dir = dataset_root / "labels" / split
        if not image_dir.is_dir() or not label_dir.is_dir():
            continue
        for label_path in sorted(label_dir.glob("*.txt")):
            image_path = next(
                (image_dir / f"{label_path.stem}{suffix}" for suffix in (".jpg", ".jpeg", ".png")
                 if (image_dir / f"{label_path.stem}{suffix}").is_file()),
                None,
            )
            if image_path is None:
                continue
            video_id = video_id_from_stem(label_path.stem)
            frame_number = int(label_path.stem[4:])
            detections: list[Detection] = []
            for line in label_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    raw = parse_yolo_line(line)
                    box, _ = sanitize_box(raw)
                except ValueError:
                    continue
                target_name = SOURCE_CLASS_MAP.get(raw.class_id)
                if box is None or target_name is None:
                    continue
                detections.append(
                    Detection(
                        frame_number,
                        str(image_path.resolve()),
                        target_name,
                        (box.center_x, box.center_y, box.width, box.height),
                    )
                )
            videos.setdefault(video_id, {})[frame_number] = detections
    return videos


def _build_tracks(frames: dict[int, list[Detection]], max_gap: int = 2) -> list[list[Detection]]:
    tracks: list[list[Detection]] = []
    for frame_number in sorted(frames):
        detections = frames[frame_number]
        candidates: list[tuple[float, float, int, int]] = []
        for track_index, track in enumerate(tracks):
            previous = track[-1]
            if frame_number - previous.frame_number > max_gap:
                continue
            for detection_index, detection in enumerate(detections):
                if previous.target_name != detection.target_name:
                    continue
                iou = _box_iou(previous.box, detection.box)
                distance = _center_distance(previous.box, detection.box)
                if iou >= 0.10 or distance <= 0.12:
                    candidates.append((-iou, distance, track_index, detection_index))
        used_tracks: set[int] = set()
        used_detections: set[int] = set()
        for _, _, track_index, detection_index in sorted(candidates):
            if track_index in used_tracks or detection_index in used_detections:
                continue
            tracks[track_index].append(detections[detection_index])
            used_tracks.add(track_index)
            used_detections.add(detection_index)
        for detection_index, detection in enumerate(detections):
            if detection_index not in used_detections:
                tracks.append([detection])
    return tracks


def _split_owners(windows: list[TemporalWindow], seed: int) -> dict[str, str]:
    counts: dict[str, int] = {}
    classes: dict[str, set[str]] = {}
    for window in windows:
        counts[window.video_id] = counts.get(window.video_id, 0) + 1
        classes.setdefault(window.video_id, set()).add(window.target_name)
    videos = sorted(counts)
    if len(videos) < 2:
        raise ValueError("Temporal training requires at least two independent source videos")
    validation = max(
        videos,
        key=lambda video: (
            len(classes[video]),
            counts[video],
            hashlib.sha256(f"{seed}:{video}".encode()).hexdigest(),
        ),
    )
    return {video: "val" if video == validation else "train" for video in videos}


def build_temporal_manifests(
    dataset_root: Path,
    output_dir: Path,
    *,
    sequence_length: int = 16,
    stride: int = 8,
    seed: int = 20260827,
) -> TemporalManifestSummary:
    if sequence_length < 2 or stride < 1:
        raise ValueError("sequence_length must be >= 2 and stride must be >= 1")
    videos = _load_frames(dataset_root)
    pending: list[TemporalWindow] = []
    track_count = 0
    excluded_short = 0
    for video_id, frames in sorted(videos.items()):
        for track_number, track in enumerate(_build_tracks(frames)):
            track_count += 1
            if len(track) < sequence_length:
                excluded_short += 1
                continue
            for start in range(0, len(track) - sequence_length + 1, stride):
                segment = track[start:start + sequence_length]
                target_name = segment[0].target_name
                pending.append(
                    TemporalWindow(
                        window_id=f"{video_id}:{track_number}:{start}",
                        video_id=video_id,
                        track_id=f"{video_id}:{track_number}",
                        split="",
                        target_name=target_name,
                        target_index=CLASS_TO_INDEX[target_name],
                        frame_paths=tuple(item.image_path for item in segment),
                        boxes=tuple(item.box for item in segment),
                    )
                )
    owners = _split_owners(pending, seed)
    windows = tuple(
        TemporalWindow(**{**asdict(window), "split": owners[window.video_id]})
        for window in pending
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = tuple(TemporalWindow.__dataclass_fields__)
    for split in ("train", "val"):
        with (output_dir / f"{split}.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for window in windows:
                if window.split != split:
                    continue
                row = asdict(window)
                row["frame_paths"] = json.dumps(row["frame_paths"], ensure_ascii=False)
                row["boxes"] = json.dumps(row["boxes"])
                writer.writerow(row)
    return TemporalManifestSummary(
        windows,
        len(videos),
        track_count,
        len(windows),
        excluded_short,
    )

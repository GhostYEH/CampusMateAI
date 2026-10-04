"""Read verified SAV keyframe annotations without inventing negative labels."""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

from .sav_labels import verified_action_names


def contained_file(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError("Expected a relative SAV file path")
    result = (root / value).resolve()
    if not result.is_relative_to(root) or not result.is_file():
        raise ValueError("SAV path escapes root or file is missing")
    return result


def build_sav_records(root: Path, split_dates: dict[str, list[str]]) -> tuple[dict, dict]:
    root = root.resolve()
    action_names, label_provenance = verified_action_names(root)
    if set(split_dates) != {"train", "val", "test"}:
        raise ValueError("Expected train/val/test date groups")
    date_to_split = {}
    for split, dates in split_dates.items():
        for date in dates:
            if not re.fullmatch(r"\d{8}", date) or date in date_to_split:
                raise ValueError("Duplicate or invalid split date")
            date_to_split[date] = split
    download = json.loads((root / "download_status.json").read_text(encoding="utf-8"))
    if download["total"] != 10 or len(download["records"]) != 10:
        raise ValueError("Expected the selected ten SAV source videos")
    source_keys = set()
    for item in download["records"]:
        key = item.get("clip_video_key", "")
        if item["status"] != "completed" or not re.fullmatch(r"\d{8}_\d+", key) or key in source_keys:
            raise ValueError("Incomplete or duplicate source video")
        if key[:8] not in date_to_split:
            raise ValueError("Source video has no date split")
        source_keys.add(key)
    wanted_clips = {c for c in (root / "clips_to_keep.txt").read_text(encoding="utf-8-sig").split()
                    if c.rsplit("_", 1)[0] in source_keys}
    if not wanted_clips:
        raise ValueError("No selected SAV clips")
    rows = {split: [] for split in split_dates}
    seen, files, seen_clips, digests, excluded = set(), {}, set(), {}, Counter()
    for clip in sorted(wanted_clips):
        path = contained_file(root, f"prepared_labels/{clip}.json")
        doc = json.loads(path.read_text(encoding="utf-8"))
        key = doc.get("source_video_key", "")
        if (doc.get("dataset") != "SAV" or doc.get("clip_id") != clip
                or key not in source_keys or clip.rsplit("_", 1)[0] != key):
            raise ValueError("SAV annotation schema or source mismatch")
        split = date_to_split[key[:8]]
        seen_clips.add(key)
        if not doc.get("people"):
            raise ValueError("Missing people annotations")
        for person in doc["people"]:
            action_ids = person["action_ids"]
            if (not action_ids or len(action_ids) != len(set(action_ids))
                    or any(type(i) is not int or i not in action_names for i in action_ids)):
                raise ValueError("Invalid SAV action ids")
            box = person["bbox_normalized_xyxy"]
            if (len(box) != 4 or any(not isinstance(x, (int, float)) or not math.isfinite(x) or not 0 <= x <= 1 for x in box)
                    or box[0] >= box[2] or box[1] >= box[3]):
                raise ValueError("Invalid SAV bounding box")
            entity = person["person_id"]
            if type(entity) is not int or entity < 0:
                raise ValueError("Invalid SAV person id")
            if person["timestamp_seconds"] != 1 or person["frame_index_1based"] != 31:
                raise ValueError("Expected official timestamp=1/frame31 annotations")
            expected_path = f"frames/{clip}/img_000031.jpg"
            if person["keyframe_path"] != expected_path:
                raise ValueError("Unexpected keyframe path")
            image = contained_file(root, person["keyframe_path"])
            sample_id = f"sav:{clip}:1:{entity}"
            if sample_id in seen:
                raise ValueError("Duplicate SAV annotated person")
            seen.add(sample_id)
            actions = {action_names[action_id] for action_id in action_ids}
            mask = ["read" in actions, "take_notes" in actions, False, False]
            if not any(mask):
                excluded[split] += 1
                continue
            if image not in files:
                files[image] = hashlib.sha256(image.read_bytes()).hexdigest()
            digest = files[image]
            if digest in digests and digests[digest] != split:
                raise ValueError("Cross-split SAV image hash overlap")
            digests[digest] = split
            x1, y1, x2, y2 = box
            rows[split].append({"sample_id": sample_id, "source": "SAV",
                "image_path": str(image), "center_x": (x1 + x2) / 2, "center_y": (y1 + y2) / 2,
                "width": x2 - x1, "height": y2 - y1, "source_video_key": key,
                "group_id": f"sav:{key}", "split": split, "sha256": digest,
                "class_mask": mask, "action_ids": action_ids})
    if seen_clips != source_keys or any(not records for records in rows.values()):
        raise ValueError("Missing SAV source or empty data split")
    summary = {
        split: {"samples": len(records), "source_videos": sorted({r["source_video_key"] for r in records}),
                "day_groups": sorted({r["source_video_key"][:8] for r in records}),
                "read_only": sum(r["class_mask"][0] and not r["class_mask"][1] for r in records),
                "write_only": sum(r["class_mask"][1] and not r["class_mask"][0] for r in records),
                "read_or_write": sum(r["class_mask"][0] and r["class_mask"][1] for r in records),
                "excluded_unmapped_people": excluded[split]}
        for split, records in rows.items()
    }
    summary["annotation_sha256"] = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                                      for path in [root / "clips_to_keep.txt", root / "download_status.json",
                                                   *sorted(root.glob("prepared_labels/*.json"))]}
    summary["label_provenance"] = label_provenance
    summary["limitations"] = "Date/video separation does not prove subject independence; unknown students; no phone labels; set labels preserve READ/WRITE ambiguity."
    return rows, summary

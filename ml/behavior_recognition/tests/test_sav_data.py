import json

import pytest
from PIL import Image

from behavior_recognition.sav_data import build_sav_records, contained_file


def fixture_dataset(root):
    dates = {"train": ["20200101"], "val": ["20200102"], "test": ["20200103"]}
    videos, clips = [], []
    for index in range(10):
        date = "20200101" if index < 6 else "20200102" if index < 8 else "20200103"
        key = f"{date}_{index:02d}"
        clip = f"{key}_1"
        clips.append(clip); videos.append({"status": "completed", "clip_video_key": key})
        frame = f"frames/{clip}/img_000031.jpg"
        (root / frame).parent.mkdir(parents=True)
        Image.new("RGB", (16, 16), color=(index * 20, 0, 0)).save(root / frame)
        person = {"person_id": 0, "action_ids": [1, 5, 10], "timestamp_seconds": 1,
                  "frame_index_1based": 31, "keyframe_path": frame,
                  "bbox_normalized_xyxy": [0.1, 0.1, 0.9, 0.9]}
        document = {"dataset": "SAV", "clip_id": clip, "source_video_key": key, "people": [person]}
        label = root / "prepared_labels" / f"{clip}.json"
        label.parent.mkdir(exist_ok=True); label.write_text(json.dumps(document), encoding="utf-8")
    (root / "download_status.json").write_text(json.dumps({"total": 10, "records": videos}), encoding="utf-8")
    (root / "clips_to_keep.txt").write_text("\n".join(clips), encoding="utf-8")
    return dates, clips


def test_sav_preserves_dual_labels_without_inventing_negative_examples(tmp_path):
    dates, clips = fixture_dataset(tmp_path)
    path = tmp_path / "prepared_labels" / f"{clips[0]}.json"
    document = json.loads(path.read_text())
    person = dict(document["people"][0]); person.update(person_id=1, action_ids=[1, 3])
    document["people"].append(person); path.write_text(json.dumps(document))
    rows, summary = build_sav_records(tmp_path, dates)
    assert len(rows["train"]) == 6
    assert all(row["class_mask"] == [True, True, False, False] for row in rows["train"])
    assert summary["train"]["excluded_unmapped_people"] == 1


def test_date_groups_cannot_overlap(tmp_path):
    dates, _ = fixture_dataset(tmp_path)
    dates["test"].append("20200101")
    with pytest.raises(ValueError, match="Duplicate"):
        build_sav_records(tmp_path, dates)


@pytest.mark.parametrize("change", ["duplicate_person", "invalid_bbox", "wrong_frame", "unknown_label"])
def test_sav_rejects_malformed_truth(tmp_path, change):
    dates, clips = fixture_dataset(tmp_path)
    path = tmp_path / "prepared_labels" / f"{clips[0]}.json"
    document = json.loads(path.read_text())
    person = document["people"][0]
    if change == "duplicate_person": document["people"].append(dict(person))
    elif change == "invalid_bbox": person["bbox_normalized_xyxy"] = [0.9, 0.1, 0.1, 0.9]
    elif change == "wrong_frame": person["frame_index_1based"] = 45
    else: person["action_ids"] = [99]
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError): build_sav_records(tmp_path, dates)


def test_cross_split_exact_image_duplicates_are_blocked(tmp_path):
    dates, clips = fixture_dataset(tmp_path)
    left = tmp_path / "frames" / clips[0] / "img_000031.jpg"
    right = tmp_path / "frames" / clips[-1] / "img_000031.jpg"
    right.write_bytes(left.read_bytes())
    with pytest.raises(ValueError, match="hash overlap"):
        build_sav_records(tmp_path, dates)


def test_contained_paths_cannot_escape_dataset(tmp_path):
    with pytest.raises(ValueError): contained_file(tmp_path, "../outside.jpg")

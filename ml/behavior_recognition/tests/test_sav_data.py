import json
import hashlib
from importlib.resources import files

import pytest
from PIL import Image

from behavior_recognition.sav_data import build_sav_records, contained_file
from behavior_recognition.sav_labels import LABEL_SHA256, LABEL_SOURCE, verified_action_names


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
    assert summary["label_provenance"]["source_url"] == LABEL_SOURCE
    assert summary["label_provenance"]["source_sha256"] == LABEL_SHA256
    assert summary["label_provenance"]["action_names"]["5"] == "read"
    assert summary["label_provenance"]["action_names"]["10"] == "take_notes"


def test_official_metadata_retains_read_and_take_notes_semantics(tmp_path):
    names, _ = verified_action_names(tmp_path)
    assert len(names) == 15
    dates, clips = fixture_dataset(tmp_path)
    path = tmp_path / "prepared_labels" / f"{clips[0]}.json"
    document = json.loads(path.read_text())
    read_id = next(key for key, name in names.items() if name == "read")
    write_id = next(key for key, name in names.items() if name == "take_notes")
    document["people"][0]["action_ids"] = [read_id]
    person = dict(document["people"][0], person_id=1, action_ids=[write_id])
    document["people"].append(person)
    path.write_text(json.dumps(document))
    rows, _ = build_sav_records(tmp_path, dates)
    assert rows["train"][0]["class_mask"] == [True, False, False, False]
    assert rows["train"][1]["class_mask"] == [False, True, False, False]


def test_packaged_metadata_cannot_be_changed_silently(tmp_path, monkeypatch):
    (tmp_path / "metadata").mkdir()
    (tmp_path / "metadata/sav_action_labels.pbtxt").write_bytes(b'item { name: "wrong" id: 5 }')
    monkeypatch.setattr("behavior_recognition.sav_labels.files", lambda _: tmp_path)
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        verified_action_names(tmp_path)


@pytest.mark.parametrize("change", ["swapped_names", "duplicate_id", "unknown_field"])
def test_conflicting_local_metadata_stops_before_labels_are_used(tmp_path, change):
    dates, _ = fixture_dataset(tmp_path)
    raw = files("behavior_recognition").joinpath("metadata/sav_action_labels.pbtxt").read_bytes()
    if change == "swapped_names":
        raw = raw.replace(b'"read"', b'"temporary"').replace(b'"take_notes"', b'"read"').replace(b'"temporary"', b'"take_notes"')
    elif change == "duplicate_id":
        raw = raw.replace(b"id: 5", b"id: 5\n  id: 10")
    else:
        raw = raw.replace(b"id: 5", b"id: 5\n  unverified: 1")
    local_path = tmp_path / "annotations/education_first_label.pbtxt"
    local_path.parent.mkdir()
    local_path.write_bytes(raw)
    with pytest.raises(ValueError, match="SAV label metadata"):
        build_sav_records(tmp_path, dates)


def test_local_metadata_formatting_can_change_without_changing_semantics(tmp_path):
    raw = files("behavior_recognition").joinpath("metadata/sav_action_labels.pbtxt").read_bytes()
    local_path = tmp_path / "annotations/education_first_label.pbtxt"
    local_path.parent.mkdir()
    local_raw = raw.replace(b"\n", b"\r\n")
    local_path.write_bytes(local_raw)
    names, audit = verified_action_names(tmp_path)
    assert names[5] == "read" and names[10] == "take_notes"
    assert audit["local_metadata_sha256"] == hashlib.sha256(local_raw).hexdigest()


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

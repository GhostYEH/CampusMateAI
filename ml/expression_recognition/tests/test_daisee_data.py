import csv
import json
import sys
import types

import numpy as np
import pytest
import torch
from PIL import Image

from expression_recognition.daisee_data import DAiSEEVideoDataset, _WORKER, prepare_daisee


def _write_labels(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ClipID", "Boredom", "Engagement", "Confusion", "Frustration "])
        writer.writeheader()
        writer.writerows(rows)


def _row(clip_id, boredom=0, confusion=1, frustration=3):
    return {"ClipID": clip_id, "Boredom": boredom, "Engagement": 2,
            "Confusion": confusion, "Frustration ": frustration}


def _dataset_root(tmp_path, train_rows=None, validation_rows=None, test_rows=None):
    root = tmp_path / "DAiSEE"
    labels = root / "Labels"
    _write_labels(labels / "TrainLabels.csv", train_rows or [_row("1100011002.avi")])
    _write_labels(labels / "ValidationLabels.csv", validation_rows or [_row("2200012002.avi")])
    _write_labels(labels / "TestLabels.csv", test_rows or [_row("3300013002.avi")])
    for split, subject, clip in [("Train", "110001", "1100011002"),
                                 ("Validation", "220001", "2200012002"),
                                 ("Test", "330001", "3300013002")]:
        video_dir = root / "DataSet" / split / subject / clip
        video_dir.mkdir(parents=True, exist_ok=True)
        (video_dir / f"{clip}.avi").write_bytes(b"mock video")
    return root


def _mock_cv2(monkeypatch, faces=True, frame_count=8):
    _WORKER.cascade = None
    seeks = []
    class Capture:
        def __init__(self, _path):
            self.index = 0

        def isOpened(self):
            return True

        def get(self, prop):
            return frame_count

        def set(self, _prop, value):
            self.index = int(value)
            seeks.append(self.index)
            return True

        def read(self):
            return True, np.full((8, 8, 3), self.index, dtype=np.uint8)

        def release(self):
            pass

    class Cascade:
        def __init__(self, _path):
            pass

        def empty(self):
            return False

        def detectMultiScale(self, *_args, **_kwargs):
            return [(1, 1, 5, 5)] if faces else []

    fake = types.SimpleNamespace(
        VideoCapture=Capture, CAP_PROP_FRAME_COUNT=1, CAP_PROP_POS_FRAMES=2,
        CascadeClassifier=Cascade, data=types.SimpleNamespace(haarcascades="mock-haar"),
        COLOR_BGR2GRAY=3, COLOR_BGR2RGB=4,
        resize=lambda frame, size: frame,
        cvtColor=lambda frame, _code: frame[:, :, ::-1] if frame.ndim == 3 else frame,
        seeks=seeks,
    )
    monkeypatch.setitem(sys.modules, "cv2", fake)
    return fake


def test_preparation_keeps_official_splits_reports_missing_and_unlabelled_and_loads_clip(tmp_path, monkeypatch):
    root = _dataset_root(tmp_path)
    # One labeled record with no video, plus one physical video with no annotation.
    train_label = root / "Labels" / "TrainLabels.csv"
    _write_labels(train_label, [_row("1100011002.avi"), _row("1100011003.avi", 2, 0, 1)])
    unlabelled = root / "DataSet" / "Train" / "110001" / "1100011004"
    unlabelled.mkdir(parents=True)
    (unlabelled / "1100011004.avi").write_bytes(b"mock video")
    _mock_cv2(monkeypatch)

    output = tmp_path / "prepared"
    result = prepare_daisee(root, output, splits=("train",), workers=1)

    assert result["included"] == 1 and result["excluded"] == 2
    assert result["reason_counts"] == {"missing_annotation": 1, "missing_video": 1}
    with (output / "manifest.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    included = next(row for row in rows if row["status"] == "included")
    assert included["split"] == "train"
    assert json.loads(included["frames"]) == [f"frames/train/110001/1100011002/{i:02d}.png" for i in range(4)]
    dataset = DAiSEEVideoDataset(output / "manifest.csv", "train", lambda _image: torch.zeros(3, 96, 96))
    frames, labels = dataset[0]
    assert frames.shape == (4, 3, 96, 96)
    assert labels.tolist() == [0, 1, 3]
    with Image.open(output / json.loads(included["frames"])[0]) as image:
        assert image.mode == "RGB"
    with pytest.raises(FileExistsError):
        prepare_daisee(root, output, splits=("train",))


def test_zero_face_clip_is_excluded_and_source_output_is_rejected(tmp_path, monkeypatch):
    root = _dataset_root(tmp_path)
    _mock_cv2(monkeypatch, faces=False)
    result = prepare_daisee(root, tmp_path / "prepared", splits=("train",))
    assert result["included"] == 0
    assert result["reason_counts"] == {"no_face": 1}
    with pytest.raises(ValueError, match="outside"):
        prepare_daisee(root, root / "derived", splits=("train",))


def test_mp4_source_matches_official_avi_clip_id(tmp_path, monkeypatch):
    root = _dataset_root(tmp_path)
    video_dir = root / "DataSet" / "Train" / "110001" / "1100011002"
    (video_dir / "1100011002.avi").rename(video_dir / "1100011002.mp4")
    _mock_cv2(monkeypatch)
    report = prepare_daisee(root, tmp_path / "prepared", splits=("train",))
    assert report["included"] == 1
    assert (tmp_path / "prepared" / "preparation_report.json").is_file()


def test_mp4_label_and_mp4_source_share_canonical_clip_id(tmp_path, monkeypatch):
    root = _dataset_root(tmp_path)
    _write_labels(root / "Labels" / "TrainLabels.csv", [_row("1100011002.mp4")])
    video_dir = root / "DataSet" / "Train" / "110001" / "1100011002"
    (video_dir / "1100011002.avi").rename(video_dir / "1100011002.mp4")
    _mock_cv2(monkeypatch)
    report = prepare_daisee(root, tmp_path / "prepared", splits=("train",))
    with (tmp_path / "prepared" / "manifest.csv").open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert report["included"] == 1
    assert row["clip_id"] == "1100011002.avi"


def test_avi_and_mp4_labels_with_same_stem_are_rejected(tmp_path):
    root = _dataset_root(tmp_path)
    _write_labels(root / "Labels" / "TrainLabels.csv", [_row("1100011002.avi"), _row("1100011002.mp4")])
    with pytest.raises(ValueError, match="Duplicate clip ID"):
        prepare_daisee(root, tmp_path / "prepared", splits=("train",))


def test_short_clip_decodes_unique_indices_then_repeats_last_valid_crop(tmp_path, monkeypatch):
    root = _dataset_root(tmp_path)
    fake_cv2 = _mock_cv2(monkeypatch, frame_count=3)
    output = tmp_path / "prepared"
    prepare_daisee(root, output, frames_per_clip=4, splits=("train",))
    with (output / "manifest.csv").open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert fake_cv2.seeks == [0, 1, 2]
    assert row["repeated_last_valid_frame"] == "true"
    assert len(json.loads(row["frames"])) == 4


def test_split_symlink_escape_fails_before_output_creation(tmp_path):
    root = _dataset_root(tmp_path)
    split_root = root / "DataSet" / "Train"
    outside = tmp_path / "outside"
    outside.mkdir()
    import shutil
    shutil.rmtree(split_root)
    try:
        split_root.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Directory symlink creation is unavailable: {exc}")
    output = tmp_path / "must-not-be-created"
    with pytest.raises(ValueError, match="outside the read-only dataset root"):
        prepare_daisee(root, output, splits=("train",))
    assert not output.exists()


def test_cross_split_subject_and_unsafe_cached_frame_are_rejected(tmp_path, monkeypatch):
    root = _dataset_root(tmp_path)
    _write_labels(root / "Labels" / "ValidationLabels.csv", [_row("1100012002.avi")])
    with pytest.raises(ValueError, match="crosses DAiSEE splits"):
        prepare_daisee(root, tmp_path / "prepared", splits=("train",))

    root = _dataset_root(tmp_path / "separate")
    _mock_cv2(monkeypatch)
    output = tmp_path / "cache"
    prepare_daisee(root, output, splits=("train",))
    manifest = output / "manifest.csv"
    with manifest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["frames"] = json.dumps(["../../escape.png"] * 4)
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="escapes cache"):
        DAiSEEVideoDataset(manifest, "train", lambda image: image)

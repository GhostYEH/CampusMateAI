import csv
from pathlib import Path

from PIL import Image

from behavior_recognition.temporal_manifest import (
    build_temporal_manifests,
    video_id_from_stem,
)


def _write_frame(root: Path, split: str, stem: str, rows: list[str]) -> None:
    image_dir = root / "images" / split
    label_dir = root / "labels" / split
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 48), color=(20, 30, 40)).save(image_dir / f"{stem}.jpg")
    (label_dir / f"{stem}.txt").write_text("\n".join(rows), encoding="utf-8")


def _tiny_source(root: Path) -> Path:
    for video_index, video_id in enumerate(("4001", "4002", "4003")):
        for frame in range(1, 5):
            split = "train" if (frame + video_index) % 2 else "val"
            stem = f"{video_id}{frame:04d}"
            label = 1 if video_id != "4003" else 3
            x = 0.30 + frame * 0.01
            _write_frame(root, split, stem, [f"{label} {x:.3f} 0.5 0.25 0.5"])
    return root


def test_video_prefix_is_the_first_four_digits():
    assert video_id_from_stem("40010234") == "4001"


def test_temporal_manifest_tracks_detections_and_keeps_video_in_one_split(tmp_path: Path):
    output = tmp_path / "manifest"
    summary = build_temporal_manifests(
        _tiny_source(tmp_path / "source"),
        output,
        sequence_length=2,
        stride=2,
        seed=7,
    )

    assert summary.video_count == 3
    assert summary.window_count == 6
    assert {row.video_id for row in summary.windows} == {"4001", "4002", "4003"}
    owners: dict[str, set[str]] = {}
    for row in summary.windows:
        owners.setdefault(row.video_id, set()).add(row.split)
        assert len(row.frame_paths) == 2
        assert len(row.boxes) == 2
    assert all(len(splits) == 1 for splits in owners.values())
    assert {row.split for row in summary.windows} == {"train", "val"}

    with (output / "train.csv").open(encoding="utf-8", newline="") as handle:
        train_rows = list(csv.DictReader(handle))
    with (output / "val.csv").open(encoding="utf-8", newline="") as handle:
        val_rows = list(csv.DictReader(handle))
    assert len(train_rows) + len(val_rows) == summary.window_count


def test_temporal_manifest_rejects_label_changes_within_a_track(tmp_path: Path):
    source = tmp_path / "source"
    for frame, source_label in enumerate((1, 1, 2, 2), start=1):
        _write_frame(
            source,
            "train",
            f"4001{frame:04d}",
            [f"{source_label} 0.5 0.5 0.3 0.5"],
        )
    for video_id in ("4002", "4003"):
        for frame in range(1, 3):
            _write_frame(source, "train", f"{video_id}{frame:04d}", ["3 0.5 0.5 0.3 0.5"])

    summary = build_temporal_manifests(
        source,
        tmp_path / "manifest",
        sequence_length=2,
        stride=2,
        seed=7,
    )

    labels_by_window = {tuple(row.target_name for _ in row.frame_paths) for row in summary.windows}
    assert labels_by_window <= {
        ("READ", "READ"),
        ("WRITE", "WRITE"),
        ("PHONE_INTERACTION", "PHONE_INTERACTION"),
    }

from pathlib import Path

from PIL import Image

from behavior_recognition.manifest import build_manifest, infer_group_id, split_group_ids
from behavior_recognition.records import SourceSpec


def test_group_never_crosses_splits():
    """Catches scene leakage caused by assigning individual frames."""
    grouped = {"scene_a": 20, "scene_b": 18, "scene_c": 12, "scene_d": 10}
    splits = split_group_ids(grouped, seed=20260823)
    owner = {}
    for split, groups in splits.items():
        for group in groups:
            assert group not in owner
            owner[group] = split
    assert set(owner) == set(grouped)


def test_numeric_video_prefix_becomes_group_id():
    """Catches adjacent SCB video frames being treated as independent samples."""
    assert infer_group_id("university", "40010060") == "university:4001"
    assert infer_group_id("university", "40020120") == "university:4002"


def test_duplicate_image_hash_survives_only_once(tmp_path: Path):
    """Catches exact image copies leaking into multiple dataset splits."""
    root = tmp_path / "source"
    for split in ("train", "val"):
        (root / "images" / split).mkdir(parents=True)
        (root / "labels" / split).mkdir(parents=True)
    image = Image.new("RGB", (40, 40), color=(10, 20, 30))
    image.save(root / "images" / "train" / "10010001.jpg")
    image.save(root / "images" / "val" / "20010001.jpg")
    for split, stem in (("train", "10010001"), ("val", "20010001")):
        (root / "labels" / split / f"{stem}.txt").write_text(
            "1 0.5 0.5 0.5 0.5\n", encoding="utf-8"
        )
    spec = SourceSpec("tiny", root, {1: "READ"}, required_for_training=True)
    manifests = build_manifest([spec], tmp_path / "manifests", seed=20260823)
    records = [record for values in manifests.values() for record in values]
    assert len(records) == 1
    assert len({record.sha256 for record in records}) == 1

from pathlib import Path

from PIL import Image

from expression_recognition.audit import audit_dataset
from expression_recognition.constants import CLASS_NAMES


def create_tree(root: Path) -> None:
    for split in ("train", "test"):
        for label in CLASS_NAMES:
            directory = root / split / label
            directory.mkdir(parents=True)
            for index in range(4):
                color = CLASS_NAMES.index(label) * 25 + index + (0 if split == "train" else 10)
                Image.new("L", (48, 48), color=color).save(
                    directory / f"{split}_{label}_{index}.jpg"
                )


def test_cross_split_duplicate_keeps_test_and_conflict_is_quarantined(tmp_path):
    root = tmp_path / "dataset"
    create_tree(root)
    duplicate = (root / "test" / "happy" / "test_happy_0.jpg").read_bytes()
    (root / "train" / "happy" / "duplicate.jpg").write_bytes(duplicate)
    conflict = (root / "test" / "sad" / "test_sad_0.jpg").read_bytes()
    (root / "train" / "fear" / "conflict.jpg").write_bytes(conflict)

    report = audit_dataset(root, tmp_path / "manifests", validation_fraction=0.5, seed=7)

    assert report["duplicate_statistics"]["cross_split_duplicate_groups"] >= 1
    assert report["duplicate_statistics"]["cross_label_conflict_groups"] >= 1
    assert report["reason_counts"]["cross_split_duplicate_keep_test"] >= 1
    assert report["reason_counts"]["cross_label_hash_conflict"] >= 2

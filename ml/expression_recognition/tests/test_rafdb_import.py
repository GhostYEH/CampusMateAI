import pytest
from PIL import Image

from expression_recognition.unified_manifest import build_unified_manifest, discover_verified_rafdb, RAFDB_ZERO_BASED_MAP


def create_raf(root, prefix):
    for raw_label in range(7):
        directory = root / str(raw_label)
        directory.mkdir(parents=True)
        Image.new("RGB", (100, 100), color=(raw_label * 30, 20, 10)).save(directory / f"{prefix}_{raw_label:05d}.jpg")


def test_verified_raf_mapping_and_local_valid_directory_preserve_official_test(tmp_path):
    create_raf(tmp_path / "train", "train")
    create_raf(tmp_path / "valid", "test")
    unrelated = tmp_path / "train/test"
    unrelated.mkdir()
    Image.new("RGB", (100, 100)).save(unrelated / "train_99999.jpg")
    records = discover_verified_rafdb(tmp_path / "train", tmp_path / "valid")
    assert len(records) == 14
    assert all(record.label == RAFDB_ZERO_BASED_MAP[record.raw_label] for record in records)
    assert next(record for record in records if record.raw_label == "0").label == "surprise"
    assert {record.original_split for record in records if "valid" in record.source_path} == {"test"}
    assert all(record.width == 100 and record.channels == 3 for record in records)


def test_verified_raf_rejects_filename_from_wrong_official_split(tmp_path):
    create_raf(tmp_path / "train", "train")
    create_raf(tmp_path / "test", "train")
    with pytest.raises(ValueError, match="official split"):
        discover_verified_rafdb(tmp_path / "train", tmp_path / "test")


def test_explicit_raf_inside_auto_root_is_not_imported_twice_with_wrong_labels(tmp_path):
    root = tmp_path / "raw"
    create_raf(root / "train", "train")
    create_raf(root / "valid", "test")
    for raw_label in range(7):
        for index in (1, 2):
            Image.new("RGB", (100, 100), color=(raw_label * 30, 20 + index * 20, 10)).save(
                root / "train" / str(raw_label) / f"train_{raw_label:03d}{index:02d}.jpg")
    report = build_unified_manifest(root, tmp_path / "manifest", 0.5, 7,
                                    raf_train_root=root / "train", raf_test_root=root / "valid")
    assert report["quarantined_files"] == 0
    assert report["included_files"] == 21
    assert len(report["sources"]) == 1
    assert report["sources"][0]["name"] == "RAFDB_zero_based_verified"

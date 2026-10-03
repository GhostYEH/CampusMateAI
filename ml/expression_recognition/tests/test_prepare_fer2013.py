import csv

import numpy as np
import pytest
from PIL import Image

from expression_recognition.prepare_fer2013 import prepare_fer2013
from expression_recognition.unified_manifest import (
    UnifiedRecord, apply_duplicate_policy, assign_splits, discover_images,
)


def write_source(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["emotion", "pixels", "Usage"])
        writer.writeheader()
        writer.writerows(rows)


def test_csv_conversion_preserves_pixels_label_order_and_official_splits(tmp_path):
    source = tmp_path / "fer2013.csv"
    pixels = np.arange(2304) % 256
    rows = [{"emotion": label, "pixels": " ".join(map(str, pixels)), "Usage": usage}
            for label, usage in [("0", "Training"), ("4", "PublicTest"), ("6", "PrivateTest")]]
    write_source(source, rows)
    original = source.read_bytes()
    root = tmp_path / "prepared"
    report = prepare_fer2013(source, root / "FER2013")
    assert source.read_bytes() == original
    assert report["split_counts"] == {"train": 1, "validation": 1, "test": 1}
    records = discover_images(root)
    assign_splits(records, 0.15, 7)
    assert {(record.label, record.split) for record in records} == {
        ("angry", "train"), ("sad", "validation"), ("neutral", "test"),
    }
    with Image.open(root / "FER2013/train/angry/fer0000000.png") as image:
        assert image.mode == "L"
        np.testing.assert_array_equal(np.asarray(image).reshape(-1), pixels)
    with pytest.raises(FileExistsError):
        prepare_fer2013(source, root / "FER2013")


@pytest.mark.parametrize("bad_pixels", ["0 1", " ".join(["256"] * 2304), " ".join(["-1"] * 2304)])
def test_bad_pixel_rows_are_quarantined_instead_of_wrapped_or_reshaped(tmp_path, bad_pixels):
    source = tmp_path / "fer2013.csv"
    write_source(source, [{"emotion": "3", "pixels": bad_pixels, "Usage": "Training"}])
    report = prepare_fer2013(source, tmp_path / "prepared")
    assert report["included"] == 0
    assert report["reason_counts"] == {"invalid_pixels": 1}
    assert not list((tmp_path / "prepared").rglob("*.png"))


def record(source, split, label, digest):
    return UnifiedRecord(f"{source}/{split}/{digest}.png", source, split, "", label, label, 0,
                         digest, 48, 48, 1, "PNG")


def test_duplicate_train_copy_never_replaces_official_validation_copy():
    rows = [record("A", "train", "happy", "same"), record("Z", "validation", "happy", "same")]
    apply_duplicate_policy(rows)
    assert rows[0].status == "excluded"
    assert rows[0].reason == "cross_split_duplicate_keep_validation"
    assert rows[1].status == "included"


def test_explicit_validation_sources_remain_fixed_while_other_sources_are_stratified():
    rows = [record("FER", "train", "happy", "fertrain"),
            record("FER", "validation", "happy", "ferval"),
            record("FER", "test", "happy", "fertest")]
    rows.extend(record("RAF", "train", "happy", str(index)) for index in range(20))
    assign_splits(rows, 0.25, 7)
    assert [row.split for row in rows[:3]] == ["train", "validation", "test"]
    assert sum(row.split == "validation" for row in rows[3:]) == 5


def test_removed_official_validation_does_not_silently_resplit_training():
    rows = [record("FER", "train", "happy", str(index)) for index in range(20)]
    rows.extend([record("FER", "validation", "happy", "duplicate"),
                 record("FER", "test", "happy", "duplicate")])
    apply_duplicate_policy(rows)
    with pytest.raises(ValueError, match="No clean official validation"):
        assign_splits(rows, 0.25, 7)
    assert not any(row.split == "validation" for row in rows[:20])

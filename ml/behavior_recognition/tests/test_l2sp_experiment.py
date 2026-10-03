import json
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from behavior_recognition.constants import CLASS_NAMES
from behavior_recognition.l2sp_experiment import (
    audit_splits, cache_path, checkpoint_rank, eligible, run_experiment, score,
    select_arm, verify_prepared_cache,
)


def record(sample, split, group, digest, index=0, name="READ"):
    return {"sample_id": sample, "split": split, "group_id": group,
            "sha256": digest, "target_index": str(index), "target_name": name}


def rows():
    return {s: [record(s, s, f"video-{s}", f"hash-{s}")]
            for s in ("train", "val", "test")}


@pytest.mark.parametrize("key", ["sample_id", "group_id", "sha256"])
def test_split_audit_rejects_leakage(key):
    records = rows()
    records["test"][0][key] = records["train"][0][key]
    with pytest.raises(ValueError):
        audit_splits(records)


def test_split_audit_accepts_multiple_rois_of_same_image_within_one_split():
    records = rows()
    records["train"].append(record("second-roi", "train", "video-train", "hash-train"))
    assert audit_splits(records)["train"]["samples"] == 2


def test_split_audit_rejects_wrong_label_contract():
    records = rows()
    records["train"][0]["target_name"] = "WRITE"
    with pytest.raises(ValueError, match="Class label"):
        audit_splits(records)


def test_validation_selection_keeps_original_unless_both_metrics_pass():
    baseline = {"accuracy": 0.45, "macro_f1": 0.46}
    assert select_arm({"higher_f1": {"accuracy": 0.44, "macro_f1": 0.5}}, baseline) == "original"
    assert not eligible(baseline.copy(), baseline)
    candidates = {"lower": {"accuracy": 0.46, "macro_f1": 0.47},
                  "higher": {"accuracy": 0.46, "macro_f1": 0.48}}
    assert select_arm(candidates, baseline) == "higher"


def test_valid_epoch_survives_later_higher_f1_with_accuracy_regression():
    baseline = {"accuracy": 0.45, "macro_f1": 0.46}
    valid_epoch = {"accuracy": 0.46, "macro_f1": 0.47}
    invalid_epoch = {"accuracy": 0.44, "macro_f1": 0.48}
    assert checkpoint_rank(valid_epoch, baseline) > checkpoint_rank(invalid_epoch, baseline)


def test_score_reports_phone_metrics_and_product_probability_sum():
    # Four-way argmax is PHONE, but READ+WRITE wins in the product space.
    probabilities = np.array([[0.30, 0.25, 0.40, 0.05],
                              [0.02, 0.02, 0.94, 0.02]], dtype=np.float32)
    result = score(np.log(probabilities), np.array([0, 2]))
    assert result["accuracy"] == 0.5
    assert result["product_accuracy"] == 1.0
    assert result["per_class"]["PHONE_INTERACTION"]["recall"] == 1.0
    assert result["phone_interaction_auprc"] == 1.0


def test_reused_cache_requires_same_manifests_and_completed_images(tmp_path):
    records = rows()
    hashes = {split: f"manifest-{split}" for split in records}
    metadata = {"manifest_sha256": hashes, "roi_expansion": 1.1, "labels": list(CLASS_NAMES)}
    (tmp_path / "plan.json").write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="incomplete"):
        verify_prepared_cache(tmp_path, records, hashes)
    (tmp_path / "roi_cache").mkdir()
    for split_records in records.values():
        for row in split_records:
            Image.new("RGB", (224, 224)).save(cache_path(tmp_path, row))
    verify_prepared_cache(tmp_path, records, hashes)
    hashes["test"] = "different-manifest"
    with pytest.raises(ValueError, match="contract mismatch"):
        verify_prepared_cache(tmp_path, records, hashes)


def test_reused_cache_rejects_wrong_dimensions_and_corrupt_png(tmp_path):
    records = {"train": rows()["train"]}
    hashes = {"train": "digest"}
    metadata = {"manifest_sha256": hashes, "roi_expansion": 1.1, "labels": list(CLASS_NAMES)}
    (tmp_path / "plan.json").write_text(json.dumps(metadata))
    (tmp_path / "roi_cache").mkdir()
    path = cache_path(tmp_path, records["train"][0])
    Image.new("RGB", (32, 32)).save(path)
    with pytest.raises(ValueError, match="image contract"):
        verify_prepared_cache(tmp_path, records, hashes)
    path.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="corrupt"):
        verify_prepared_cache(tmp_path, records, hashes)


@pytest.mark.parametrize("epochs", [0, 7])
def test_experiment_rejects_epochs_outside_bounded_run(epochs):
    with pytest.raises(ValueError, match="training bounds"):
        run_experiment(SimpleNamespace(epochs=epochs))

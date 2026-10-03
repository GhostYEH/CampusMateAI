from copy import deepcopy
import hashlib

import numpy as np
import pytest
import torch
from PIL import Image

from behavior_recognition.constants import CLASS_NAMES
from behavior_recognition.l2sp_experiment import cache_path, prepare_cache
from behavior_recognition.sav_replay_experiment import (
    partial_label_loss, set_report, validation_eligible, validation_rank, verify_replay_pixels,
)


def test_partial_set_loss_matches_ce_and_preserves_ambiguous_gradient():
    logits = torch.tensor([[0.0, 1.0, 2.0, 3.0]], requires_grad=True)
    single = torch.tensor([[True, False, False, False]])
    torch.testing.assert_close(partial_label_loss(logits, single),
                               torch.nn.functional.cross_entropy(logits, torch.tensor([0])))
    both = torch.tensor([[True, True, False, False]])
    loss = partial_label_loss(logits, both)
    expected = -torch.log(logits.softmax(1)[0, :2].sum())
    torch.testing.assert_close(loss, expected)
    loss.backward()
    assert (logits.grad[0, :2] < 0).all() and (logits.grad[0, 2:] > 0).all()


def test_partial_set_loss_rejects_empty_allowed_classes():
    with pytest.raises(ValueError, match="nonempty"):
        partial_label_loss(torch.zeros(1, 4), torch.zeros(1, 4, dtype=torch.bool))


def test_video_balanced_score_is_not_dominated_by_many_student_rois():
    rows = [{"source_video_key": "a", "class_mask": [True, False, False, False]} for _ in range(3)]
    rows += [{"source_video_key": "b", "class_mask": [True, True, False, False]}]
    logits = np.array([[10., 0., 0., 0.]] * 3 + [[0., 0., 10., 0.]])
    report = set_report(logits, rows)
    assert report["acceptable_top1_rate"] == 0.75
    assert report["source_mean_acceptable_top1_rate"] == 0.5
    assert report["read_or_write_samples"] == 1


def validation():
    return {"scb": {"accuracy": 0.5, "macro_f1": 0.4, "phone_interaction_auprc": 0.6,
                    "per_class": {name: {"f1": 0.4, "recall": 0.3} for name in CLASS_NAMES}},
            "sav": {"source_mean_acceptable_top1_rate": 0.7, "source_mean_partial_nll": 1.0}}


@pytest.mark.parametrize("metric", ["accuracy", "macro_f1", "phone_interaction_auprc", "phone_f1", "phone_recall", "write_f1"])
def test_sav_improvement_cannot_override_replay_regression(metric):
    baseline = validation()
    candidate = deepcopy(baseline)
    candidate["sav"]["source_mean_partial_nll"] = 0.8
    assert validation_eligible(candidate, baseline)
    if metric in candidate["scb"]:
        candidate["scb"][metric] -= 0.01
    else:
        label = "WRITE" if metric == "write_f1" else "PHONE_INTERACTION"
        key = "recall" if metric == "phone_recall" else "f1"
        candidate["scb"]["per_class"][label][key] -= 0.01
    assert not validation_eligible(candidate, baseline)


def test_eligible_checkpoint_ranks_before_later_ineligible_gain():
    baseline = validation()
    good = deepcopy(baseline); good["sav"]["source_mean_partial_nll"] = 0.9
    bad = deepcopy(good); bad["sav"]["source_mean_partial_nll"] = 0.1
    bad["scb"]["accuracy"] = 0.1
    assert validation_rank(good, baseline) > validation_rank(bad, baseline)


def test_replay_cache_rejects_valid_png_with_wrong_pixels(tmp_path):
    source = tmp_path / "source.jpg"
    Image.new("RGB", (40, 40), "red").save(source)
    row = {"sample_id": "student", "image_path": str(source),
           "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
           "center_x": 0.5, "center_y": 0.5, "width": 0.4, "height": 0.4}
    prepare_cache(tmp_path, [row], 1)
    assert verify_replay_pixels(tmp_path, {"train": [row]})["verified_rois"] == 1
    Image.new("RGB", (224, 224), "blue").save(cache_path(tmp_path, row))
    with pytest.raises(ValueError, match="pixels mismatch"):
        verify_replay_pixels(tmp_path, {"train": [row]})


def test_replay_source_fingerprint_cannot_be_stale(tmp_path):
    source = tmp_path / "source.jpg"
    Image.new("RGB", (40, 40), "red").save(source)
    row = {"sample_id": "student", "image_path": str(source), "sha256": "outdated"}
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        verify_replay_pixels(tmp_path, {"train": [row]})

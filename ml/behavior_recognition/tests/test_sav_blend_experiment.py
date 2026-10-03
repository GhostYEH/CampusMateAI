from copy import deepcopy

import numpy as np
import pytest
import torch

from behavior_recognition.constants import CLASS_NAMES
from behavior_recognition.metrics import softmax
from behavior_recognition.sav_blend_experiment import (
    blend_state, choose_blend, probability_blend_logits, verify_sav_provenance,
)


def test_weight_blending_preserves_inputs_and_exact_endpoints():
    left, right = {"w": torch.tensor([1., 4.])}, {"w": torch.tensor([5., 2.])}
    torch.testing.assert_close(blend_state(left, right, 0)["w"], left["w"], rtol=0, atol=0)
    torch.testing.assert_close(blend_state(left, right, 1)["w"], right["w"], rtol=0, atol=0)
    torch.testing.assert_close(blend_state(left, right, .25)["w"], torch.tensor([2., 3.5]))
    assert left["w"].tolist() == [1., 4.] and right["w"].tolist() == [5., 2.]


@pytest.mark.parametrize("alpha", [-.1, 1.1, float("nan"), float("inf")])
def test_blending_rejects_invalid_weights(alpha):
    with pytest.raises(ValueError): blend_state({"w": torch.ones(1)}, {"w": torch.ones(1)}, alpha)
    with pytest.raises(ValueError): probability_blend_logits(np.ones((1, 4)), np.ones((1, 4)), alpha)


def test_weight_blending_rejects_incompatible_or_nonfinite_tensors():
    with pytest.raises(ValueError): blend_state({"w": torch.ones(1)}, {"other": torch.ones(1)}, .2)
    with pytest.raises(ValueError): blend_state({"w": torch.ones(1)}, {"w": torch.ones(2)}, .2)
    with pytest.raises(ValueError): blend_state({"w": torch.ones(1)}, {"w": torch.tensor([float("nan")])}, .2)


def test_probability_fusion_is_arithmetic_mixture_not_logit_average():
    left = np.array([[4., 0., -1., -2.]])
    right = np.array([[0., 3., 1., -2.]])
    np.testing.assert_array_equal(probability_blend_logits(left, right, 0), left)
    np.testing.assert_array_equal(probability_blend_logits(left, right, 1), right)
    fused = probability_blend_logits(left, right, .3)
    np.testing.assert_allclose(softmax(fused), .7 * softmax(left) + .3 * softmax(right), atol=1e-7)
    assert not np.allclose(softmax(fused), softmax(.7 * left + .3 * right))


def test_selection_rejects_phone_regression_and_prefers_single_forward_on_tie():
    baseline = {"scb": {"accuracy": .5, "macro_f1": .4, "phone_interaction_auprc": .6,
                        "per_class": {name: {"f1": .4, "recall": .3} for name in CLASS_NAMES}},
                "sav": {"source_mean_acceptable_top1_rate": .4, "source_mean_partial_nll": 2.}}
    bad = deepcopy(baseline); bad["sav"]["source_mean_partial_nll"] = 1.
    bad["scb"]["per_class"]["PHONE_INTERACTION"]["recall"] = .29
    candidates = {"bad": {"alpha": .1, "method": "weights", "validation": bad}}
    assert choose_blend(candidates, baseline) == "original"
    good = deepcopy(baseline); good["sav"]["source_mean_partial_nll"] = 1.5
    candidates["probabilities"] = {"alpha": .2, "method": "probabilities", "validation": good}
    candidates["weights"] = {"alpha": .2, "method": "weights", "validation": good}
    assert choose_blend(candidates, baseline) == "weights"


@pytest.mark.parametrize("change", ["class_mask", "split", "annotation_hash"])
def test_saved_sav_labels_are_bound_to_official_source(monkeypatch, tmp_path, change):
    row = {"image_path": str(tmp_path / "frames" / "clip" / "img_000031.jpg"),
           "class_mask": [True, False, False, False], "split": "train"}
    truth = {split: [dict(row, split=split)] for split in ("train", "val", "test")}
    audit = {"annotation_sha256": {"label.json": "original"}}
    prior = {"plan": {"split_dates": {}, "sav_audit": deepcopy(audit)}}
    monkeypatch.setattr("behavior_recognition.sav_blend_experiment.build_sav_records",
                        lambda *args: (truth, audit))
    assert verify_sav_provenance(truth, prior)["samples"] == 3
    rows = deepcopy(truth)
    if change == "annotation_hash":
        prior["plan"]["sav_audit"]["annotation_sha256"]["label.json"] = "changed"
    elif change == "class_mask":
        rows["val"][0]["class_mask"] = [False, True, False, False]
    else:
        rows["val"][0]["split"] = "test"
    with pytest.raises(ValueError, match="fingerprints changed"):
        verify_sav_provenance(rows, prior)

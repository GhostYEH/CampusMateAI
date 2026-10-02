import torch
from torch import nn
from torch.utils.data import TensorDataset

from pathlib import Path

import numpy as np
import pytest

from behavior_recognition import evaluate
from behavior_recognition.models import build_experiment_model

from behavior_recognition.evaluate import (
    build_space_reports,
    collapsed_binary_report,
    collect_logits,
    evaluate_v32,
    expected_v32_label,
)


def test_collect_logits_preserves_dataset_order():
    """Catches evaluation shuffling labels away from their predictions."""
    model = nn.Sequential(nn.Flatten(), nn.Linear(12, 4, bias=False))
    with torch.no_grad():
        model[1].weight.fill_(0.1)
    dataset = TensorDataset(torch.arange(24, dtype=torch.float32).reshape(2, 3, 2, 2), torch.tensor([3, 1]))
    logits, labels = collect_logits(model, dataset, torch.device("cpu"), batch_size=1)
    assert logits.shape == (2, 4)
    assert labels.tolist() == [3, 1]


def test_v32_binary_expectation_keeps_phone_and_sleep_out_of_visible_study():
    """Catches an invalid comparison that maps all behavior classes to study."""
    assert expected_v32_label(0) == 1
    assert expected_v32_label(1) == 1
    assert expected_v32_label(2) == 0
    assert expected_v32_label(3) == 0


def test_v32_evaluation_respects_fixed_batch_one_contract():
    """Catches batching multiple samples into the fixed-batch packaged ONNX model."""
    repository = Path(__file__).resolve().parents[3]
    model_path = repository / "android/app/src/main/assets/models/behavior/campusmate_visible_study_v32.onnx"
    dataset = TensorDataset(torch.zeros(2, 3, 224, 224), torch.tensor([0, 2]))
    report = evaluate_v32(model_path, dataset, batch_size=2)
    assert report["sample_count"] == 2


def test_candidate_binary_collapse_matches_v32_semantics():
    """Catches four-class improvements being compared with a different binary target."""
    labels = np.array([0, 1, 2, 3])
    probabilities = np.array(
        [[0.8, 0.1, 0.05, 0.05], [0.1, 0.7, 0.1, 0.1], [0.1, 0.1, 0.7, 0.1], [0.1, 0.1, 0.2, 0.6]],
        dtype=np.float32,
    )
    report = collapsed_binary_report(labels, probabilities)
    assert report["accuracy"] == 1.0
    assert report["macro_f1"] == 1.0


def test_space_reports_include_probability_level_product_evaluation():
    """Catches product evaluation being derived from source Top-1 labels."""
    labels = np.array([0, 1, 2, 3])
    probabilities = np.array(
        [
            [0.31, 0.30, 0.39, 0.00],
            [0.20, 0.70, 0.10, 0.00],
            [0.10, 0.10, 0.70, 0.10],
            [0.10, 0.10, 0.10, 0.70],
        ],
        dtype=np.float32,
    )

    report = build_space_reports(labels, probabilities, probabilities)

    assert report["test_calibrated"]["accuracy"] == 0.75
    assert report["test_product_calibrated"]["accuracy"] == 1.0
    assert report["product_class_names"] == [
        "STUDY_ACTIVITY",
        "PHONE_INTERACTION",
        "NO_VISIBLE_STUDY",
    ]


def test_space_reports_can_label_validation_without_reusing_test_keys():
    """Catches offline selection accidentally reading locked test metrics."""
    labels = np.array([0, 1, 2, 3])
    probabilities = np.eye(4, dtype=np.float32)

    report = build_space_reports(
        labels,
        probabilities,
        probabilities,
        split="validation",
    )

    assert "validation_product_calibrated" in report
    assert "test_product_calibrated" not in report


@pytest.mark.parametrize("variant", ["mobilenet_v3_small", "local_cue"])
def test_checkpoint_evaluation_restores_experiment_variant_without_pretrained_download(
    tmp_path, monkeypatch, variant
):
    config = {"model_variant": variant, "input_mode": "roi", "pretrained": True}
    model = build_experiment_model({**config, "pretrained": False})
    checkpoint = tmp_path / "candidate.pt"
    torch.save({"config": config, "model_state": model.state_dict(), "epoch": 1}, checkpoint)
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    for name in ("val.csv", "test.csv"):
        (manifests / name).write_text("sample_id,image_path\n", encoding="utf-8")
    labels = torch.arange(4)
    dataset = TensorDataset(torch.zeros(4, 3, 2, 2), labels)
    monkeypatch.setattr(evaluate, "BehaviorDataset", lambda *args, **kwargs: dataset)
    monkeypatch.setattr(evaluate, "materialize_roi_cache", lambda *args: 0)
    monkeypatch.setattr(
        evaluate, "collect_logits",
        lambda *args: (np.eye(4, dtype=np.float32) * 3., labels.numpy()),
    )
    restored_configs = []

    def restore_model(resolved_config, num_classes):
        restored_configs.append(resolved_config)
        return build_experiment_model(resolved_config, num_classes)

    monkeypatch.setattr(evaluate, "build_experiment_model", restore_model)
    report = evaluate.evaluate_checkpoint(checkpoint, manifests, tmp_path / "report.json")
    assert restored_configs == [{**config, "pretrained": False}]
    assert report["validation_sample_count"] == report["test_sample_count"] == 4

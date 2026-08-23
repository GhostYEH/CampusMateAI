import torch
from torch import nn
from torch.utils.data import TensorDataset

from pathlib import Path

import numpy as np

from behavior_recognition.evaluate import (
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

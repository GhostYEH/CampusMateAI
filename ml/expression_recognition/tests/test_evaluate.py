import numpy as np
import pytest
import torch
from argparse import Namespace
from torch.utils.data import DataLoader, TensorDataset

from expression_recognition.evaluate import benchmark_model, collect_predictions, evaluate
from expression_recognition.export_litert import evaluate_litert


@pytest.mark.parametrize("batch_size", [1, 2, 5])
def test_evaluation_loss_uses_all_samples_even_with_short_final_batch(batch_size) -> None:
    logits = torch.tensor([[3., 0.], [1., 0.], [0., 3.], [0., 1.], [5., 0.]])
    labels = torch.tensor([0, 0, 1, 1, 1])
    loader = DataLoader(TensorDataset(logits, labels), batch_size=batch_size)
    probabilities, targets, loss = collect_predictions(torch.nn.Identity(), loader, torch.device("cpu"))
    assert loss == pytest.approx(torch.nn.functional.cross_entropy(logits, labels).item(), abs=1e-7)
    np.testing.assert_allclose(probabilities, logits.softmax(1).numpy())
    np.testing.assert_array_equal(targets, labels.numpy())


@pytest.mark.parametrize("split", ["validation", "test"])
@pytest.mark.parametrize("horizontal_flip_tta", [False, True])
def test_pytorch_evaluation_only_fits_validation_gates(tmp_path, monkeypatch, split, horizontal_flip_tta):
    linear = torch.nn.Linear(7, 7, bias=False)
    linear.weight.data.copy_(torch.eye(7))
    model = torch.nn.Sequential(torch.nn.Flatten(), linear)
    config = {"model": "fixture", "input_size": 1, "input_channels": 7, "normalization": {}}
    checkpoint = tmp_path / "checkpoint.pt"
    torch.save({"config": config, "model_state": model.state_dict()}, checkpoint)
    loader = DataLoader(TensorDataset((torch.eye(7) * 10).reshape(7, 7, 1, 1), torch.arange(7)), batch_size=3)
    monkeypatch.setattr("expression_recognition.evaluate.build_model", lambda *args, **kwargs: model)
    monkeypatch.setattr("expression_recognition.evaluate.create_loader", lambda *args, **kwargs: (None, loader))
    benchmark_strategies = []
    def benchmark_fixture(*args):
        benchmark_strategies.append(args[-1])
        return {}
    monkeypatch.setattr("expression_recognition.evaluate.benchmark_model", benchmark_fixture)
    monkeypatch.setattr("expression_recognition.evaluate.plot_confusion", lambda *args: None)
    monkeypatch.setattr("expression_recognition.evaluate.plot_history", lambda *args: None)

    metrics = evaluate(Namespace(
        checkpoint=checkpoint, manifest=tmp_path / "unused.csv", split=split,
        output_dir=tmp_path / "report", batch_size=3, cpu=True,
        horizontal_flip_tta=horizontal_flip_tta,
    ))
    assert metrics["accuracy"] == 1.0
    assert ("class_thresholds" in metrics) == (split == "validation")
    assert metrics["inference_strategy"] == ("horizontal_flip_probability_mean" if horizontal_flip_tta else "single")
    assert benchmark_strategies == [horizontal_flip_tta]


class LeftPixelClassifier(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.seen = []

    def forward(self, inputs):
        self.seen.append(inputs.detach().clone())
        left = inputs[:, 0, 0, 0]
        return torch.stack((left, torch.zeros_like(left)), dim=1)


@pytest.mark.parametrize("batch_size", [1, 2, 3])
def test_flip_tta_averages_probabilities_and_uses_mixture_nll(batch_size):
    inputs = torch.tensor([[[[4., 0.]]], [[[2., -1.]]], [[[0., -3.]]]])
    labels = torch.tensor([0, 1, 1])
    model = LeftPixelClassifier()
    loader = DataLoader(TensorDataset(inputs, labels), batch_size=batch_size)
    probabilities, targets, loss = collect_predictions(model, loader, torch.device("cpu"), True)
    original_logits = torch.stack((inputs[:, 0, 0, 0], torch.zeros(3)), dim=1)
    flipped_logits = torch.stack((inputs[:, 0, 0, 1], torch.zeros(3)), dim=1)
    expected = (original_logits.softmax(1) + flipped_logits.softmax(1)) * .5
    np.testing.assert_allclose(probabilities, expected.numpy(), atol=1e-7)
    assert not np.allclose(probabilities, ((original_logits + flipped_logits) * .5).softmax(1).numpy())
    assert loss == pytest.approx(-expected[torch.arange(3), labels].log().mean().item(), abs=1e-7)
    np.testing.assert_array_equal(targets, labels.numpy())
    for original, flipped in zip(model.seen[::2], model.seen[1::2]):
        torch.testing.assert_close(flipped, original.flip(-1))


def test_default_strategy_equals_explicit_single_and_keeps_extreme_loss_finite():
    inputs = torch.tensor([[[[1000., -5.]]], [[[3., 0.]]]])
    labels = torch.tensor([1, 0])
    loader = DataLoader(TensorDataset(inputs, labels), batch_size=2)
    default_model, explicit_model = LeftPixelClassifier(), LeftPixelClassifier()
    default = collect_predictions(default_model, loader, torch.device("cpu"))
    explicit = collect_predictions(explicit_model, loader, torch.device("cpu"), False)
    np.testing.assert_array_equal(default[0], explicit[0])
    np.testing.assert_array_equal(default[1], explicit[1])
    assert default[2] == explicit[2]
    logits = torch.tensor([[1000., 0.], [3., 0.]])
    assert default[2] == pytest.approx(torch.nn.functional.cross_entropy(logits, labels).item())
    assert len(default_model.seen) == len(explicit_model.seen) == 1


@pytest.mark.parametrize("horizontal_flip_tta", [False, True])
def test_benchmark_runs_selected_strategy(horizontal_flip_tta):
    model = LeftPixelClassifier()
    result = benchmark_model(model, {"input_channels": 1, "input_size": 2}, torch.device("cpu"), horizontal_flip_tta)
    assert len(model.seen) == 180 * (2 if horizontal_flip_tta else 1)
    assert set(result) == {"batch_1", "batch_32"}
    assert all(row["mean_latency_ms"] > 0 for row in result.values())


@pytest.mark.parametrize("split", ["validation", "test"])
def test_litert_evaluation_only_fits_validation_gates(tmp_path, monkeypatch, split):
    # Exercise the export evaluator without a TensorFlow installation/model.
    inputs = (torch.eye(7) * 10).reshape(7, 7, 1, 1)
    loader = DataLoader(TensorDataset(inputs, torch.arange(7)), batch_size=1)
    monkeypatch.setattr("expression_recognition.export_litert.create_loader", lambda *args, **kwargs: (None, loader))
    monkeypatch.setattr("expression_recognition.export_litert.create_interpreter", lambda *args: object())
    monkeypatch.setattr("expression_recognition.export_litert.run_interpreter", lambda _, data: data.reshape(1, 7))

    metrics = evaluate_litert(tmp_path / "unused.tflite", tmp_path / "unused.csv", {}, split)
    assert metrics["accuracy"] == 1.0
    assert ("class_thresholds" in metrics) == (split == "validation")

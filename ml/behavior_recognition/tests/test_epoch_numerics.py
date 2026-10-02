import numpy as np
import pytest
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from behavior_recognition import temporal_train, train


class _IdentityEncoder:
    def encode(self, inputs):
        return np.asarray(inputs).reshape(len(inputs), -1)


def _run(runner, model, inputs, labels, criterion, device, **kwargs):
    if runner == "onnx":
        inputs = inputs.reshape(len(inputs), 1, inputs.shape[-1], 1, 1)
    loader = DataLoader(TensorDataset(inputs, labels), batch_size=kwargs.pop("batch_size", 2))
    if runner == "onnx":
        return temporal_train._run_onnx_epoch(
            model, _IdentityEncoder(), loader, criterion, device, **kwargs
        )
    epoch = train._run_epoch if runner == "image" else temporal_train._run_epoch
    return epoch(model, loader, criterion, device, **kwargs)


@pytest.mark.parametrize("runner", ["image", "temporal", "onnx"])
@pytest.mark.parametrize("weighted", [False, True])
def test_epoch_loss_matches_global_cross_entropy_across_batch_sizes(runner, weighted):
    logits = torch.tensor([
        [3., 0., 0., 0.], [1., 2., 0., 0.], [0., 0., 4., 0.],
        [0., 2., 0., 3.], [0., 0., 1., 0.],
    ])
    labels = torch.tensor([0, 0, 2, 3, 3])
    weight = torch.tensor([0.05, 0.10, 0.35, 0.55]) if weighted else None
    criterion = nn.CrossEntropyLoss(weight=weight, label_smoothing=0.05)
    reference = float(criterion(logits, labels))
    for batch_size in (1, 2, 5):
        loss, _ = _run(
            runner, nn.Flatten(1), logits, labels, criterion,
            torch.device("cpu"), batch_size=batch_size,
        )
        assert loss == pytest.approx(reference, abs=1e-6)


@pytest.mark.parametrize("runner", ["image", "temporal", "onnx"])
def test_gradient_clipping_uses_unscaled_gradients(runner):
    states = []
    for enabled in (False, True):
        model = nn.Sequential(nn.Flatten(1), nn.Linear(1, 4, bias=False))
        nn.init.zeros_(model[1].weight)
        optimizer = torch.optim.SGD(model.parameters(), lr=0.1)
        scaler = torch.amp.GradScaler("cpu", enabled=enabled, init_scale=128.)
        _run(
            runner, model, torch.ones(2, 1), torch.zeros(2, dtype=torch.long),
            nn.CrossEntropyLoss(), torch.device("cpu"), optimizer=optimizer,
            scaler=scaler, gradient_clip_norm=0.1,
        )
        states.append(model[1].weight.detach().clone())
    torch.testing.assert_close(states[0], states[1])
    assert states[1].norm().item() == pytest.approx(0.01, abs=1e-6)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required to exercise float16 AMP")
@pytest.mark.parametrize("runner", ["image", "temporal", "onnx"])
def test_amp_preserves_small_gradient_updates(runner):
    model = nn.Sequential(nn.Flatten(1), nn.Linear(1, 4, bias=False)).cuda()
    nn.init.zeros_(model[1].weight)
    optimizer = torch.optim.SGD(model.parameters(), lr=100000.)
    _run(
        runner, model, torch.full((2, 1), 1e-7), torch.zeros(2, dtype=torch.long),
        nn.CrossEntropyLoss(), torch.device("cuda"), optimizer=optimizer, amp=True,
    )
    weights = model[1].weight.detach().cpu().flatten()
    assert weights[0] > 0
    assert (weights[1:] < 0).all()  # Without loss scaling these updates underflow to zero.
    torch.testing.assert_close(
        weights, torch.tensor([0.0075, -0.0025, -0.0025, -0.0025]), rtol=0.25, atol=0,
    )


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required to exercise float16 AMP")
@pytest.mark.parametrize("runner", ["image", "temporal", "onnx"])
def test_amp_skips_nonfinite_update_and_reduces_scale(runner):
    model = nn.Sequential(nn.Flatten(1), nn.Linear(1, 4, bias=False)).cuda()
    nn.init.zeros_(model[1].weight)
    before = model[1].weight.detach().clone()
    optimizer = torch.optim.SGD(model.parameters(), lr=0.1)
    scaler = torch.amp.GradScaler("cuda", init_scale=65536.)
    _run(
        runner, model, torch.full((2, 1), 10000.), torch.zeros(2, dtype=torch.long),
        nn.CrossEntropyLoss(), torch.device("cuda"), optimizer=optimizer, amp=True,
        scaler=scaler,
    )
    torch.testing.assert_close(model[1].weight, before)
    assert scaler.get_scale() == 32768.

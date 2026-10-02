import numpy as np
import pytest
import torch
from torch.utils.data import DataLoader, TensorDataset

from expression_recognition.evaluate import collect_predictions


@pytest.mark.parametrize("batch_size", [1, 2, 5])
def test_evaluation_loss_uses_all_samples_even_with_short_final_batch(batch_size) -> None:
    logits = torch.tensor([[3., 0.], [1., 0.], [0., 3.], [0., 1.], [5., 0.]])
    labels = torch.tensor([0, 0, 1, 1, 1])
    loader = DataLoader(TensorDataset(logits, labels), batch_size=batch_size)
    probabilities, targets, loss = collect_predictions(torch.nn.Identity(), loader, torch.device("cpu"))
    assert loss == pytest.approx(torch.nn.functional.cross_entropy(logits, labels).item(), abs=1e-7)
    np.testing.assert_allclose(probabilities, logits.softmax(1).numpy())
    np.testing.assert_array_equal(targets, labels.numpy())

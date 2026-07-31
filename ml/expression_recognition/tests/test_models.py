import pytest
import torch

from expression_recognition.models import build_model


@pytest.mark.parametrize(
    ("name", "channels", "size"),
    [
        ("baseline_cnn", 1, 48),
        ("resnet18", 3, 96),
        ("mobilenet_v3_small", 3, 96),
    ],
)
def test_model_output_shape(name, channels, size):
    model = build_model({"model": name, "pretrained": False}, allow_download=False).eval()
    with torch.no_grad():
        result = model(torch.zeros(2, channels, size, size))
    assert result.shape == (2, 7)

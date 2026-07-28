"""模型前向传播、输出维度、标签顺序测试（需要 torch）。

torch 未安装时整文件跳过。
"""

import pytest

torch = pytest.importorskip("torch")

from expression_recognition.config import InputConfig, ModelConfig
from expression_recognition.constants import NUM_CLASSES, EXPRESSION_LABELS
from expression_recognition.models.build import build_model, count_parameters, dummy_input
from expression_recognition.models.custom_cnn import CustomCNN


def test_custom_cnn_output_shape():
    cfg = ModelConfig(name="custom_cnn", num_classes=NUM_CLASSES, pretrained=False,
                      freeze_backbone=False, dropout=0.1)
    inp = InputConfig(size=48, channels=1, mean=(0.5,), std=(0.5,))
    model = build_model(cfg, inp)
    x = dummy_input(inp)
    out = model(x)
    assert out.shape == (1, NUM_CLASSES)
    assert out.dtype == torch.float32


def test_custom_cnn_direct():
    model = CustomCNN(num_classes=7, dropout=0.1, in_channels=1)
    x = torch.zeros(4, 1, 48, 48)
    out = model(x)
    assert out.shape == (4, 7)


def test_resnet18_output_shape():
    torchvision = pytest.importorskip("torchvision")
    cfg = ModelConfig(name="resnet18", num_classes=NUM_CLASSES, pretrained=False,
                      freeze_backbone=True, dropout=0.2)
    inp = InputConfig(size=224, channels=3, mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5))
    model = build_model(cfg, inp)
    x = dummy_input(inp)
    out = model(x)
    assert out.shape == (1, NUM_CLASSES)


def test_mobilenet_v3_small_output_shape():
    torchvision = pytest.importorskip("torchvision")
    cfg = ModelConfig(name="mobilenet_v3_small", num_classes=NUM_CLASSES, pretrained=False,
                      freeze_backbone=True, dropout=0.2)
    inp = InputConfig(size=224, channels=3, mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5))
    model = build_model(cfg, inp)
    x = dummy_input(inp)
    out = model(x)
    assert out.shape == (1, NUM_CLASSES)


def test_freeze_backbone_reduces_trainable_params():
    torchvision = pytest.importorskip("torchvision")
    from expression_recognition.models.build import freeze_model_backbone, unfreeze_model_backbone

    cfg = ModelConfig(name="mobilenet_v3_small", num_classes=NUM_CLASSES, pretrained=False,
                      freeze_backbone=False, dropout=0.2)
    inp = InputConfig(size=224, channels=3, mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5))
    model = build_model(cfg, inp)
    n_full = count_parameters(model)["trainable"]
    freeze_model_backbone(model, "mobilenet_v3_small")
    n_frozen = count_parameters(model)["trainable"]
    assert n_frozen < n_full
    unfreeze_model_backbone(model, "mobilenet_v3_small")
    assert count_parameters(model)["trainable"] == n_full


def test_output_columns_match_label_count():
    """模型输出列数必须等于标签数 7。"""
    cfg = ModelConfig(name="custom_cnn", num_classes=NUM_CLASSES, pretrained=False,
                      freeze_backbone=False, dropout=0.0)
    inp = InputConfig(size=48, channels=1, mean=(0.5,), std=(0.5,))
    model = build_model(cfg, inp)
    out = model(dummy_input(inp))
    assert out.shape[1] == len(EXPRESSION_LABELS) == 7


def test_unknown_model_rejected():
    cfg = ModelConfig(name="unknown", num_classes=7, pretrained=False)
    inp = InputConfig(size=48, channels=1, mean=(0.5,), std=(0.5,))
    with pytest.raises(ValueError):
        build_model(cfg, inp)

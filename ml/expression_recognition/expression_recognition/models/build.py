"""模型工厂：按名称构造模型，统一处理冻结/解冻。

build_model 是对外唯一入口，根据 ModelConfig.name 构造对应模型：
- custom_cnn：自定义浅层 CNN（1 通道 48x48）。
- resnet18：ResNet18 迁移学习（3 通道 224x224）。
- mobilenet_v3_small：MobileNetV3-Small 迁移学习（3 通道 224x224，主部署候选）。
"""

from __future__ import annotations

import torch
from torch import nn

from ..config import ModelConfig, InputConfig
from ..constants import NUM_CLASSES
from .custom_cnn import CustomCNN
from . import resnet18 as resnet18_mod
from . import mobilenet_v3 as mobilenet_mod

MODEL_NAMES = ("custom_cnn", "resnet18", "mobilenet_v3_small")


def build_model(
    model_cfg: ModelConfig,
    input_cfg: InputConfig,
) -> nn.Module:
    """根据配置构造模型。

    Args:
        model_cfg: 模型配置。
        input_cfg: 输入配置（决定通道数，迁移学习模型强制 3 通道）。

    Returns:
        nn.Module，输出 (N, 7) logits。
    """
    num_classes = NUM_CLASSES  # 强制 7 类，忽略配置中的 num_classes 之外值
    if model_cfg.num_classes != num_classes:
        # 已在 config.validate 校验，这里再防御一次。
        raise ValueError(f"num_classes 必须为 {num_classes}")

    name = model_cfg.name
    if name == "custom_cnn":
        # 自定义 CNN 用单通道；若配置给了 3 通道，仍构造单通道并提示。
        in_channels = input_cfg.channels if input_cfg.channels == 1 else 1
        model = CustomCNN(
            num_classes=num_classes,
            dropout=model_cfg.dropout,
            in_channels=in_channels,
        )
    elif name == "resnet18":
        model = resnet18_mod.build_resnet18(
            num_classes=num_classes,
            pretrained=model_cfg.pretrained,
            dropout=model_cfg.dropout,
        )
        if model_cfg.freeze_backbone:
            resnet18_mod.freeze_backbone(model)
    elif name == "mobilenet_v3_small":
        model = mobilenet_mod.build_mobilenet_v3_small(
            num_classes=num_classes,
            pretrained=model_cfg.pretrained,
            dropout=model_cfg.dropout,
        )
        if model_cfg.freeze_backbone:
            mobilenet_mod.freeze_backbone(model)
    else:
        raise ValueError(
            f"未知模型名: {name}（支持 {MODEL_NAMES}）"
        )

    return model


def unfreeze_model_backbone(model: nn.Module, name: str) -> None:
    """按模型名解冻骨干，用于逐步解冻。"""
    if name == "resnet18":
        resnet18_mod.unfreeze_backbone(model)
    elif name == "mobilenet_v3_small":
        mobilenet_mod.unfreeze_backbone(model)
    # custom_cnn 无预训练骨干，不解冻。


def freeze_model_backbone(model: nn.Module, name: str) -> None:
    """按模型名冻结骨干。"""
    if name == "resnet18":
        resnet18_mod.freeze_backbone(model)
    elif name == "mobilenet_v3_small":
        mobilenet_mod.freeze_backbone(model)


def count_parameters(model: nn.Module) -> dict[str, int]:
    """统计模型参数量。

    Returns:
        {"total": 总参数, "trainable": 可训练参数, "non_trainable": 冻结参数}
    """
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return {
        "total": int(total),
        "trainable": int(trainable),
        "non_trainable": int(total - trainable),
    }


def get_input_shape(input_cfg: InputConfig) -> tuple[int, int, int]:
    """返回 (C, H, W)。"""
    return (input_cfg.channels, input_cfg.size, input_cfg.size)


def dummy_input(input_cfg: InputConfig) -> torch.Tensor:
    """构造一个 batch=1 的虚拟输入，用于导出与测试。"""
    c, h, w = get_input_shape(input_cfg)
    return torch.zeros(1, c, h, w, dtype=torch.float32)

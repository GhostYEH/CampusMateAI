"""ResNet18 迁移学习。

使用 torchvision.models.resnet18 加载 ImageNet 预训练权重，
替换第一层卷积以接受 3 通道输入（ResNet 本就是 3 通道，这里保留），
替换最终全连接层为 7 类输出。

输入约定：3 通道 224x224，归一化用 ImageNet mean/std。
"""

from __future__ import annotations

import torch
from torch import nn


def build_resnet18(num_classes: int = 7, pretrained: bool = True, dropout: float = 0.3) -> nn.Module:
    """构造 ResNet18 迁移学习模型。

    Args:
        num_classes: 输出类别数（固定 7）。
        pretrained: 是否加载 ImageNet 预训练权重。
        dropout: 分类头 dropout。
    """
    try:
        from torchvision import models
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "构建 ResNet18 需要 torchvision，请安装: pip install torchvision"
        ) from e

    weights = models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
    model = models.resnet18(weights=weights)

    # 替换分类头：加 dropout + Linear。
    in_features = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Dropout(dropout),
        nn.Linear(in_features, num_classes),
    )
    return model


def freeze_backbone(model: nn.Module) -> None:
    """冻结 ResNet18 骨干（除 fc 外所有参数）。"""
    for name, param in model.named_parameters():
        if not name.startswith("fc."):
            param.requires_grad = False


def unfreeze_backbone(model: nn.Module) -> None:
    """解冻 ResNet18 骨干。"""
    for param in model.parameters():
        param.requires_grad = True

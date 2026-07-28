"""MobileNetV3-Small 迁移学习（主部署候选）。

使用 torchvision.models.mobilenet_v3_small 加载 ImageNet 预训练权重，
替换分类头为 7 类输出。MobileNetV3-Small 参数量小、推理快，适合移动端部署。

输入约定：3 通道 224x224，归一化用 ImageNet mean/std。
"""

from __future__ import annotations

import torch
from torch import nn


def build_mobilenet_v3_small(
    num_classes: int = 7, pretrained: bool = True, dropout: float = 0.3
) -> nn.Module:
    """构造 MobileNetV3-Small 迁移学习模型。

    Args:
        num_classes: 输出类别数（固定 7）。
        pretrained: 是否加载 ImageNet 预训练权重。
        dropout: 分类头 dropout。
    """
    try:
        from torchvision import models
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "构建 MobileNetV3-Small 需要 torchvision，请安装: pip install torchvision"
        ) from e

    weights = models.MobileNet_V3_Small_Weights.IMAGENET1K_V1 if pretrained else None
    model = models.mobilenet_v3_small(weights=weights)

    # MobileNetV3-Small 的分类头是 Sequential(classifier):
    #   [0] Linear(576->1024), [1] Hardswish, [2] Dropout, [3] Linear(1024->1000)
    # 只替换最后的 Linear。
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, num_classes)
    # 在最后 Linear 前插入 Dropout（若已有则替换）。
    # 这里简化：直接在 classifier 末尾用新结构。
    model.classifier = nn.Sequential(
        *list(model.classifier.children())[:-1],
        nn.Dropout(dropout),
        nn.Linear(in_features, num_classes),
    )
    return model


def freeze_backbone(model: nn.Module) -> None:
    """冻结 MobileNetV3 骨干（features 部分），只训练 classifier。"""
    for name, param in model.named_parameters():
        if name.startswith("classifier."):
            param.requires_grad = True
        else:
            param.requires_grad = False


def unfreeze_backbone(model: nn.Module) -> None:
    """解冻 MobileNetV3 骨干。"""
    for param in model.parameters():
        param.requires_grad = True

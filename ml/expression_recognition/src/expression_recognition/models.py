from __future__ import annotations

import torch
from torch import nn
from torchvision.models import (
    EfficientNet_B0_Weights,
    MobileNet_V3_Small_Weights,
    ResNet18_Weights,
    efficientnet_b0,
    mobilenet_v3_small,
    resnet18,
)

from .constants import NUM_CLASSES


class BaselineExpressionCnn(nn.Module):
    def __init__(self, num_classes: int = NUM_CLASSES):
        super().__init__()
        self.features = nn.Sequential(
            self._block(1, 32),
            nn.MaxPool2d(2),
            self._block(32, 64),
            nn.MaxPool2d(2),
            self._block(64, 128),
            nn.MaxPool2d(2),
            self._block(128, 192),
            nn.AdaptiveAvgPool2d(1),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(0.35),
            nn.Linear(192, num_classes),
        )

    @staticmethod
    def _block(in_channels: int, out_channels: int) -> nn.Sequential:
        return nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=False),
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=False),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(inputs))


def build_model(config: dict, allow_download: bool = True) -> nn.Module:
    name = config["model"]
    pretrained = bool(config.get("pretrained", False)) and allow_download
    if name == "baseline_cnn":
        return BaselineExpressionCnn()
    if name == "resnet18":
        weights = ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
        model = resnet18(weights=weights)
        model.fc = nn.Linear(model.fc.in_features, NUM_CLASSES)
        return model
    if name == "mobilenet_v3_small":
        weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1 if pretrained else None
        model = mobilenet_v3_small(weights=weights)
        last = model.classifier[-1]
        model.classifier[-1] = nn.Linear(last.in_features, NUM_CLASSES)
        return model
    if name == "efficientnet_b0":
        weights = EfficientNet_B0_Weights.IMAGENET1K_V1 if pretrained else None
        model = efficientnet_b0(weights=weights)
        last = model.classifier[-1]
        model.classifier[-1] = nn.Linear(last.in_features, NUM_CLASSES)
        return model
    raise ValueError(f"Unsupported model: {name}")


def parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())

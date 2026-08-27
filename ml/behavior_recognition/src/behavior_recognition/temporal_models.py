from __future__ import annotations

import torch
from torch import nn
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small


class MobileNetFrameEncoder(nn.Module):
    def __init__(self, pretrained: bool = True):
        super().__init__()
        weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1 if pretrained else None
        backbone = mobilenet_v3_small(weights=weights)
        self.features = backbone.features
        self.avgpool = backbone.avgpool
        self.projection = nn.Sequential(*list(backbone.classifier.children())[:-1])
        self.output_size = backbone.classifier[-1].in_features

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        features = self.features(inputs)
        features = self.avgpool(features)
        features = torch.flatten(features, 1)
        return self.projection(features)


class TemporalBehaviorModel(nn.Module):
    def __init__(
        self,
        num_classes: int = 4,
        hidden_size: int = 256,
        pretrained: bool = True,
    ):
        super().__init__()
        self.encoder = MobileNetFrameEncoder(pretrained=pretrained)
        self.gru = nn.GRU(self.encoder.output_size, hidden_size, batch_first=True)
        self.classifier = nn.Linear(hidden_size, num_classes)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        if inputs.ndim != 5:
            raise ValueError("Expected input shape [batch, time, channels, height, width]")
        batch, time, channels, height, width = inputs.shape
        embeddings = self.encoder(inputs.reshape(batch * time, channels, height, width))
        sequence = embeddings.reshape(batch, time, -1)
        outputs, _ = self.gru(sequence)
        return self.classifier(outputs[:, -1])


class TemporalGRUHead(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 256, num_classes: int = 4):
        super().__init__()
        self.gru = nn.GRU(input_size, hidden_size, batch_first=True)
        self.classifier = nn.Linear(hidden_size, num_classes)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        if features.ndim != 3:
            raise ValueError("Expected feature shape [batch, time, features]")
        outputs, _ = self.gru(features)
        return self.classifier(outputs[:, -1])


def freeze_encoder(model: TemporalBehaviorModel) -> None:
    for parameter in model.encoder.parameters():
        parameter.requires_grad = False


def unfreeze_encoder_tail(model: TemporalBehaviorModel, blocks: int = 2) -> None:
    freeze_encoder(model)
    if blocks < 1:
        return
    for block in list(model.encoder.features.children())[-blocks:]:
        for parameter in block.parameters():
            parameter.requires_grad = True

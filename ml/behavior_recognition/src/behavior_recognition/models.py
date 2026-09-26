from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small


def build_model(num_classes: int = 4, pretrained: bool = True) -> nn.Module:
    weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1 if pretrained else None
    model = mobilenet_v3_small(weights=weights)
    last = model.classifier[-1]
    model.classifier[-1] = nn.Linear(last.in_features, num_classes)
    return model


class LocalCueBehaviorModel(nn.Module):
    """Offline two-view ablation: full student ROI plus likely hand/desk region.

    Both views share a MobileNetV3 encoder. The extra crop is an image prior,
    not a phone detector; target-domain evaluation must establish its utility.
    """

    def __init__(self, num_classes: int = 4, pretrained: bool = True):
        super().__init__()
        backbone = build_model(num_classes, pretrained)
        self.features = backbone.features
        self.avgpool = backbone.avgpool
        feature_size = backbone.classifier[0].in_features
        self.classifier = nn.Linear(feature_size * 2, num_classes)

    def _encode(self, images: torch.Tensor) -> torch.Tensor:
        return torch.flatten(self.avgpool(self.features(images)), 1)

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        if images.ndim != 4 or images.shape[2] < 4 or images.shape[3] < 4:
            raise ValueError("Expected NCHW student ROI images")
        height, width = images.shape[-2:]
        local = images[:, :, round(height * 0.32):round(height * 0.90), round(width * 0.12):round(width * 0.88)]
        local = F.interpolate(local, size=(height, width), mode="bilinear", align_corners=False)
        features = self._encode(torch.cat((images, local), dim=0))
        full_features, local_features = features.chunk(2, dim=0)
        return self.classifier(torch.cat((full_features, local_features), dim=1))


def build_experiment_model(config: dict, num_classes: int = 4) -> nn.Module:
    variant = config.get("model_variant", "mobilenet_v3_small")
    pretrained = bool(config.get("pretrained", True))
    if variant == "mobilenet_v3_small":
        return build_model(num_classes, pretrained)
    if variant == "local_cue":
        if config.get("input_mode", "roi") != "roi":
            raise ValueError("Local-cue behavior model requires ROI input")
        return LocalCueBehaviorModel(num_classes, pretrained)
    raise ValueError(f"Unsupported behavior model variant: {variant}")


def parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())

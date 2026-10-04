"""Shared ResNet18 for seven expressions and three independent DAiSEE states."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import torch
from torch import nn

from .constants import CLASS_NAMES
from .learning_state_model import validate_expression_contract
from .models import build_model

STATE_NAMES = ("boredom", "confusion", "frustration")
MULTITASK_CLASS_ORDER = tuple(CLASS_NAMES) + STATE_NAMES
MULTITASK_VERSION = "multitask-expression-states-v1"
STATE_POSITIVE_DEFINITION = "DAiSEE level >= 2"


def validate_multitask_checkpoint(checkpoint: dict[str, Any]) -> None:
    if checkpoint.get("checkpoint_version") != MULTITASK_VERSION:
        raise ValueError("Checkpoint is not a supported multitask expression/state checkpoint")
    if checkpoint.get("class_order") != list(MULTITASK_CLASS_ORDER):
        raise ValueError("Checkpoint class_order differs from the required ten-label order")
    if checkpoint.get("state_positive_definition") != STATE_POSITIVE_DEFINITION:
        raise ValueError("Checkpoint has an incompatible DAiSEE binary state definition")
    if not isinstance(checkpoint.get("config"), dict) or not isinstance(checkpoint.get("model_state"), dict):
        raise ValueError("Checkpoint is missing model configuration or weights")
    validate_expression_contract(checkpoint["config"])


class MultiTaskExpressionModel(nn.Module):
    """Partially fine-tuned ResNet18 with a 7-way softmax and 3 binary logits.

    The shared visual trunk is initialized from the original seven-expression
    checkpoint. ``layer4`` (optionally also ``layer3``), the original seven-class
    ``fc``, and the new independent state heads are trainable. Earlier layers and all BatchNorm
    running statistics remain frozen. Clip inputs pool frame features and
    average per-frame expression logits, matching the four-frame DAiSEE path.
    """

    def __init__(self, backbone: nn.Module, config: dict[str, Any]):
        super().__init__()
        validate_expression_contract(config)
        if not isinstance(getattr(backbone, "fc", None), nn.Linear):
            raise ValueError("Expression backbone must have a linear ResNet18 fc")
        if backbone.fc.in_features != 512 or backbone.fc.out_features != len(CLASS_NAMES):
            raise ValueError("Expression backbone must have a 512-to-7 classifier")
        if not all(hasattr(backbone, name) for name in ("layer4", "avgpool")):
            raise ValueError("Expression backbone must be ResNet18-shaped")
        self.config = copy.deepcopy(config)
        self.confidence_calibration: dict[str, Any] | None = None
        self.backbone = backbone
        self.state_head = nn.Linear(512, len(STATE_NAMES))
        self.set_trainable_blocks(self.config.get("trainable_blocks", ("layer4",)))

    def set_trainable_blocks(self, blocks) -> "MultiTaskExpressionModel":
        """Fine-tune a contiguous suffix without changing weights or label format."""
        blocks = tuple(blocks)
        if blocks not in (("layer4",), ("layer3", "layer4")):
            raise ValueError("trainable_blocks must be layer4 or layer3 followed by layer4")
        if not all(hasattr(self.backbone, name) for name in blocks):
            raise ValueError("The selected trainable blocks are missing from the backbone")
        self.backbone.requires_grad_(False)
        for name in blocks:
            getattr(self.backbone, name).requires_grad_(True)
        self.backbone.fc.requires_grad_(True)
        self.state_head.requires_grad_(True)
        self.trainable_blocks = blocks
        self.config["trainable_blocks"] = list(blocks)
        self._set_batch_norm_eval()
        return self

    @classmethod
    def from_expression_checkpoint(cls, path: str | Path) -> "MultiTaskExpressionModel":
        """Initialize from a local original checkpoint without downloading weights."""
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
        config = checkpoint["config"]
        validate_expression_contract(config)
        if "class_names" in checkpoint and list(checkpoint["class_names"]) != CLASS_NAMES:
            raise ValueError("Source checkpoint class_names differ from the seven-class contract")
        backbone = build_model(config, allow_download=False)
        backbone.load_state_dict(checkpoint["model_state"], strict=True)
        return cls(backbone, config)

    @classmethod
    def from_checkpoint(cls, path: str | Path) -> "MultiTaskExpressionModel":
        """Load a versioned multitask checkpoint with a strict ten-label contract."""
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
        validate_multitask_checkpoint(checkpoint)
        backbone = build_model(checkpoint["config"], allow_download=False)
        model = cls(backbone, checkpoint["config"])
        model.load_state_dict(checkpoint["model_state"], strict=True)
        model.confidence_calibration = copy.deepcopy(checkpoint.get("confidence_calibration"))
        return model

    def _set_batch_norm_eval(self) -> None:
        for module in self.backbone.modules():
            if isinstance(module, nn.modules.batchnorm._BatchNorm):
                module.eval()

    def train(self, mode: bool = True) -> "MultiTaskExpressionModel":
        super().train(mode)
        self._set_batch_norm_eval()
        return self

    def forward(self, inputs: torch.Tensor) -> dict[str, torch.Tensor]:
        if inputs.ndim not in (4, 5) or tuple(inputs.shape[-3:]) != (3, 96, 96):
            raise ValueError("Inputs must be [B,3,96,96] or [B,T,3,96,96]")
        batch = inputs.shape[0]
        frames = inputs.shape[1] if inputs.ndim == 5 else 1
        if batch < 1 or frames < 1:
            raise ValueError("Images and clips must have nonempty batch and frame dimensions")
        flat = inputs.reshape(batch * frames, 3, 96, 96)
        features = self.backbone.conv1(flat)
        features = self.backbone.bn1(features)
        features = self.backbone.relu(features)
        features = self.backbone.maxpool(features)
        # Frozen prefix avoids building an unnecessary autograd graph.
        with torch.no_grad():
            features = self.backbone.layer1(features)
            features = self.backbone.layer2(features)
            if "layer3" not in self.trainable_blocks:
                features = self.backbone.layer3(features)
        if "layer3" in self.trainable_blocks:
            features = self.backbone.layer3(features)
        features = self.backbone.layer4(features)
        features = torch.flatten(self.backbone.avgpool(features), 1)
        per_frame_expression = self.backbone.fc(features)
        pooled = features.reshape(batch, frames, 512).mean(dim=1)
        expression_logits = per_frame_expression.reshape(batch, frames, len(CLASS_NAMES)).mean(dim=1)
        state_logits = self.state_head(pooled)
        return {"expression_logits": expression_logits, "state_logits": state_logits}

    @staticmethod
    def probabilities_from_logits(expression_logits: torch.Tensor, state_logits: torch.Tensor) -> torch.Tensor:
        if expression_logits.ndim != 2 or expression_logits.shape[1] != 7:
            raise ValueError("expression_logits must have shape [B,7]")
        if state_logits.shape != (len(expression_logits), len(STATE_NAMES)):
            raise ValueError("state_logits must have shape [B,3]")
        # Independent states do not compete with the seven expression classes.
        return torch.cat((expression_logits.softmax(dim=1), state_logits.sigmoid()), dim=1)

    def probabilities(self, inputs: torch.Tensor) -> torch.Tensor:
        outputs = self(inputs)
        if self.confidence_calibration is not None:
            from .multitask_confidence import confidence_probabilities
            return confidence_probabilities(outputs, self.confidence_calibration)
        return self.probabilities_from_logits(outputs["expression_logits"], outputs["state_logits"])


# Stable public spelling used by the joint-training entry point and clients.
MultitaskExpressionStateModel = MultiTaskExpressionModel

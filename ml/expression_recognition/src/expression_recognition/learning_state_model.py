"""Offline DAiSEE heads attached to the unchanged seven-class expression model.

The three learning states are independent ordinal labels, not three extra
mutually exclusive expression classes. Training these heads never updates the
expression backbone, its batch-normalization statistics, or its classifier.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

from .constants import CLASS_NAMES
from .models import build_model


STATE_NAMES = ("boredom", "confusion", "frustration")
NUM_STATE_LEVELS = 4
_MEAN = [0.485, 0.456, 0.406]
_STD = [0.229, 0.224, 0.225]


def validate_expression_contract(config: dict[str, Any]) -> None:
    """Reject sources with a different image or expression-label contract."""
    if config.get("model") != "resnet18":
        raise ValueError("Learning-state heads require a resnet18 expression checkpoint")
    if config.get("input_size") != 96 or config.get("input_channels") != 3:
        raise ValueError("Expression checkpoint must use 96x96 RGB inputs")
    normalization = config.get("normalization", {})
    if normalization.get("mean") != _MEAN or normalization.get("std") != _STD:
        raise ValueError("Expression checkpoint must use the existing ImageNet normalization")
    if "class_names" in config and list(config["class_names"]) != CLASS_NAMES:
        raise ValueError("Expression checkpoint class_names differ from the seven-class contract")


class FrozenExpressionLearningStateModel(nn.Module):
    """Frozen ResNet18 plus three trainable four-level linear heads.

    Inputs are normalized ``[B,3,96,96]`` images or
    ``[B,T,3,96,96]`` clips. Clips use the mean of their frame features;
    expression logits use the mean of the original frame expression logits.
    """

    def __init__(self, backbone: nn.Module, config: dict[str, Any]):
        super().__init__()
        validate_expression_contract(config)
        if not isinstance(getattr(backbone, "fc", None), nn.Linear):
            raise ValueError("Expression backbone must have a linear ResNet18 fc")
        if backbone.fc.in_features != 512 or backbone.fc.out_features != len(CLASS_NAMES):
            raise ValueError("Expression backbone must have a 512-to-7 classifier")
        self.config = copy.deepcopy(config)
        self.backbone = backbone
        self.backbone.requires_grad_(False)
        self.backbone.eval()
        self.state_heads = nn.ModuleList(
            nn.Linear(512, NUM_STATE_LEVELS) for _ in STATE_NAMES
        )

    @classmethod
    def from_expression_checkpoint(cls, path: str | Path) -> FrozenExpressionLearningStateModel:
        """Load a local original checkpoint strictly, without weight downloads."""
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
        config = checkpoint["config"]
        validate_expression_contract(config)
        if "class_names" in checkpoint and list(checkpoint["class_names"]) != CLASS_NAMES:
            raise ValueError("Expression checkpoint class_names differ from the seven-class contract")
        backbone = build_model(config, allow_download=False)
        backbone.load_state_dict(checkpoint["model_state"], strict=True)
        return cls(backbone, config)

    def train(self, mode: bool = True) -> FrozenExpressionLearningStateModel:
        super().train(mode)
        self.backbone.eval()
        return self

    def _frame_features(self, inputs: torch.Tensor) -> tuple[torch.Tensor, int, int]:
        if inputs.ndim not in (4, 5) or tuple(inputs.shape[-3:]) != (3, 96, 96):
            raise ValueError("Inputs must be [B,3,96,96] or [B,T,3,96,96]")
        batch = inputs.shape[0]
        frames = inputs.shape[1] if inputs.ndim == 5 else 1
        if batch < 1 or frames < 1:
            raise ValueError("Images and clips must have nonempty batch and frame dimensions")
        self.backbone.eval()
        with torch.no_grad():
            features = inputs.reshape(batch * frames, 3, 96, 96)
            # Use the original ResNet modules in their original forward order.
            for child in list(self.backbone.children())[:-1]:
                features = child(features)
            features = torch.flatten(features, 1)
        return features, batch, frames

    def extract_features(self, inputs: torch.Tensor) -> torch.Tensor:
        """Extract frozen, temporally averaged ``[B,512]`` visual features."""
        features, batch, frames = self._frame_features(inputs)
        return features.reshape(batch, frames, 512).mean(dim=1)

    def state_logits_from_features(self, features: torch.Tensor) -> torch.Tensor:
        """Predict independent ``[B,3,4]`` state logits from cached features."""
        if features.ndim != 2 or features.shape[1] != 512:
            raise ValueError("Learning-state features must have shape [B,512]")
        return torch.stack([head(features.detach()) for head in self.state_heads], dim=1)

    def forward(self, inputs: torch.Tensor) -> dict[str, torch.Tensor]:
        features, batch, frames = self._frame_features(inputs)
        with torch.no_grad():
            expression_logits = self.backbone.fc(features).reshape(batch, frames, 7).mean(dim=1)
        pooled = features.reshape(batch, frames, 512).mean(dim=1)
        return {
            "expression_logits": expression_logits,
            "state_logits": self.state_logits_from_features(pooled),
        }


def _label_array(values: Any, name: str) -> np.ndarray:
    if isinstance(values, torch.Tensor):
        values = values.detach().cpu().numpy()
    result = np.asarray(values)
    if result.ndim != 2 or result.shape[1] != len(STATE_NAMES) or len(result) == 0:
        raise ValueError(f"{name} must be a nonempty [N,3] label array")
    if not np.issubdtype(result.dtype, np.integer) or (result < 0).any() or (result >= NUM_STATE_LEVELS).any():
        raise ValueError(f"{name} must contain integer DAiSEE levels 0..3")
    return result


def _state_metrics(targets: np.ndarray, predictions: np.ndarray) -> dict[str, Any]:
    labels = list(range(NUM_STATE_LEVELS))
    matrix = confusion_matrix(targets, predictions, labels=labels)
    support = matrix.sum(axis=1)
    recalls = np.divide(matrix.diagonal(), support, out=np.zeros(4, dtype=float), where=support > 0)
    return {
        "accuracy": float(accuracy_score(targets, predictions)),
        "macro_f1": float(f1_score(targets, predictions, labels=labels, average="macro", zero_division=0)),
        # Balanced accuracy follows the usual mean recall over true classes
        # present in this split; macro-F1 always includes all four levels.
        "balanced_accuracy": float(recalls[support > 0].mean()),
        "balanced_accuracy_definition": "mean_recall_over_levels_present_in_targets",
        "confusion_matrix": matrix.tolist(),
        "per_class": classification_report(
            targets, predictions, labels=labels, output_dict=True, zero_division=0
        ),
        "support": support.tolist(),
    }


def learning_state_metrics(
    targets: Any, predictions: Any, train_targets: Any | None = None
) -> dict[str, Any]:
    """Fixed-four-level metrics and optional training-only majority baseline.

    ``predictions`` contains three argmax labels per clip, not logits. Model
    selection uses the mean of the three fixed-label macro-F1 values. The
    optional majority predictor is fitted only to the provided training labels.
    """
    targets = _label_array(targets, "targets")
    predictions = _label_array(predictions, "predictions")
    if targets.shape != predictions.shape:
        raise ValueError("Targets and predictions must have the same shape")
    result: dict[str, Any] = {
        "state_names": list(STATE_NAMES),
        "levels": list(range(NUM_STATE_LEVELS)),
        "sample_count": len(targets),
        "states": {
            state: _state_metrics(targets[:, index], predictions[:, index])
            for index, state in enumerate(STATE_NAMES)
        },
    }
    result["mean_macro_f1"] = float(np.mean([value["macro_f1"] for value in result["states"].values()]))
    result["selection_score"] = result["mean_macro_f1"]
    if train_targets is not None:
        train_targets = _label_array(train_targets, "train_targets")
        majority = [
            int(np.bincount(train_targets[:, index], minlength=NUM_STATE_LEVELS).argmax())
            for index in range(len(STATE_NAMES))
        ]
        baseline = learning_state_metrics(targets, np.tile(majority, (len(targets), 1)))
        baseline["majority_levels"] = dict(zip(STATE_NAMES, majority))
        baseline["fitted_on"] = "train"
        result["majority_baseline"] = baseline
    return result

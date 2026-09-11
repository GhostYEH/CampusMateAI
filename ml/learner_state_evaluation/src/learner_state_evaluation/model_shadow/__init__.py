"""Synthetic, offline-only CampusMate-LM capability evaluation."""

from .dataset import DATASET_VERSION, build_shadow_dataset, validate_shadow_dataset
from .metrics import EVALUATOR_VERSION, evaluate_shadow_predictions
from .promotion import THRESHOLD_VERSION, evaluate_promotion

__all__ = [
    "DATASET_VERSION", "EVALUATOR_VERSION", "THRESHOLD_VERSION",
    "build_shadow_dataset", "evaluate_promotion", "evaluate_shadow_predictions",
    "validate_shadow_dataset",
]

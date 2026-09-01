from __future__ import annotations

import numpy as np
from sklearn.metrics import f1_score

from .metrics import apply_rejection


def search_rejection_thresholds(
    probabilities: np.ndarray,
    labels: np.ndarray,
    min_coverage: float = 0.70,
) -> dict:
    class_count = probabilities.shape[1]
    fallback_thresholds = np.full(class_count, 0.35, dtype=np.float32)
    fallback_margin = 0.05
    fallback_predictions = apply_rejection(
        probabilities,
        fallback_thresholds,
        fallback_margin,
    )
    fallback_accepted = fallback_predictions >= 0
    best = {
        "class_thresholds": fallback_thresholds.tolist(),
        "margin_threshold": fallback_margin,
        "coverage": float(fallback_accepted.mean()),
        "accepted_macro_f1": float(
            f1_score(
                labels[fallback_accepted],
                fallback_predictions[fallback_accepted],
                labels=list(range(class_count)),
                average="macro",
                zero_division=0,
            )
        )
        if fallback_accepted.any()
        else 0.0,
    }
    best_score = (-1.0, -1.0)
    for threshold in (0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60):
        thresholds = np.full(class_count, threshold, dtype=np.float32)
        for margin in (0.0, 0.05, 0.10, 0.15, 0.20):
            predictions = apply_rejection(probabilities, thresholds, margin)
            accepted = predictions >= 0
            coverage = float(accepted.mean())
            if coverage < min_coverage or not accepted.any():
                continue
            macro_f1 = float(
                f1_score(
                    labels[accepted],
                    predictions[accepted],
                    labels=list(range(class_count)),
                    average="macro",
                    zero_division=0,
                )
            )
            score = (macro_f1, coverage)
            if score > best_score:
                best_score = score
                best = {
                    "class_thresholds": thresholds.tolist(),
                    "margin_threshold": margin,
                    "coverage": coverage,
                    "accepted_macro_f1": macro_f1,
                }
    return best

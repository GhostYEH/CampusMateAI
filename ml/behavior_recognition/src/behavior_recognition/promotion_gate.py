"""Production promotion gate for target-domain behavior candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class PromotionDecision:
    approved: bool
    failed_gates: list[str]
    metrics: dict[str, float]


MINIMUMS = {
    "event_macro_f1": 0.70,
    "phone_precision": 0.80,
    "phone_recall": 0.75,
    "no_visible_study_f1": 0.65,
    "quality_coverage": 0.70,
}
MAXIMUMS = {
    "false_reminders_per_hour": 1.0,
    "phone_detection_p95_ms": 3000.0,
}


def evaluate_promotion(
    metrics: Mapping[str, float],
    *,
    device_groups: Mapping[str, Mapping[str, float]] | None = None,
) -> PromotionDecision:
    failed: list[str] = []
    for name, minimum in MINIMUMS.items():
        value = metrics.get(name)
        if value is None or value < minimum:
            failed.append(name)
    for name, maximum in MAXIMUMS.items():
        value = metrics.get(name)
        if value is None or value > maximum:
            failed.append(name)
    for group_name, group_metrics in sorted((device_groups or {}).items()):
        precision = group_metrics.get("phone_precision")
        if precision is None or precision < 0.75:
            failed.append(f"device_group:{group_name}:phone_precision")
    return PromotionDecision(
        approved=not failed,
        failed_gates=failed,
        metrics={name: float(value) for name, value in metrics.items()},
    )

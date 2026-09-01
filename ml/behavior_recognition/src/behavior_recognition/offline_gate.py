"""Validation-only gate for deciding whether an offline candidate merits more experiments."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Mapping


@dataclass(frozen=True)
class OfflinePolicy:
    minimum_product_macro_f1_delta: float = 0.005
    maximum_phone_auprc_regression: float = 0.01
    maximum_ece_regression: float = 0.01
    minimum_rejection_coverage: float = 0.70


@dataclass(frozen=True)
class OfflineDecision:
    advanced: bool
    failed_checks: list[str]
    candidate_metrics: dict[str, float]
    baseline_metrics: dict[str, float]
    deltas: dict[str, float]
    stage: str = "offline_experiment"
    production_approved: bool = field(default=False, init=False)


def _finite_metric(container: Mapping[str, Any], path: tuple[str, ...]) -> float:
    value: Any = container
    for part in path:
        if not isinstance(value, Mapping) or part not in value:
            raise ValueError(f"missing required metric: {'.'.join(path)}")
        value = value[part]
    try:
        metric = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"metric must be numeric: {'.'.join(path)}") from error
    if not isfinite(metric):
        raise ValueError(f"metric must be finite: {'.'.join(path)}")
    return metric


def _extract_metrics(report: Mapping[str, Any]) -> dict[str, float]:
    product_path = ("validation_product_calibrated",)
    return {
        "product_macro_f1": _finite_metric(report, product_path + ("macro_f1",)),
        "phone_interaction_auprc": _finite_metric(
            report,
            product_path + ("phone_interaction_auprc",),
        ),
        "ece": _finite_metric(report, product_path + ("ece",)),
        "rejection_coverage": _finite_metric(report, ("rejection", "coverage")),
    }


def compare_offline_candidate(
    candidate: Mapping[str, Any],
    baseline: Mapping[str, Any],
    policy: OfflinePolicy = OfflinePolicy(),
) -> OfflineDecision:
    """Compare validation evidence without granting production promotion."""
    candidate_metrics = _extract_metrics(candidate)
    baseline_metrics = _extract_metrics(baseline)
    deltas = {
        name: candidate_metrics[name] - baseline_metrics[name]
        for name in candidate_metrics
    }
    failed: list[str] = []
    if deltas["product_macro_f1"] < policy.minimum_product_macro_f1_delta:
        failed.append("product_macro_f1")
    if deltas["phone_interaction_auprc"] < -policy.maximum_phone_auprc_regression:
        failed.append("phone_interaction_auprc")
    if deltas["ece"] > policy.maximum_ece_regression:
        failed.append("ece")
    if candidate_metrics["rejection_coverage"] < policy.minimum_rejection_coverage:
        failed.append("rejection_coverage")
    return OfflineDecision(
        advanced=not failed,
        failed_checks=failed,
        candidate_metrics=candidate_metrics,
        baseline_metrics=baseline_metrics,
        deltas=deltas,
    )

"""Leave-one-participant-out training, calibration and threshold selection."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .features import FEATURE_SETS
from .metrics import (
    alert_metrics,
    classification_metrics,
    evaluate_by_participant,
    evaluate_groups,
    participant_summary,
    pooled_metrics,
)
from .model import (
    build_model,
    fit_platt,
    oof_logits,
    predict_probability,
    predict_rows,
    training_rows,
)
from .schema import ContractError

DEFAULT_THRESHOLD_GRID = tuple(round(0.20 + step * 0.01, 2) for step in range(71))
MIN_RELEASE_COVERAGE = 0.80
MAX_RELEASE_FALSE_ALERTS_PER_HOUR = 1.0
MIN_RELEASE_KAPPA = 0.70
MIN_RELEASE_PARTICIPANTS = 5


def _key(row: dict[str, Any]) -> tuple[str, str, int]:
    return (row["participant_id"], row["session_id"], int(row["index"]))


def _oof_probabilities(
    rows: list[dict[str, Any]],
    feature_set: str,
) -> tuple[dict[tuple[str, str, int], float], tuple[float, float]]:
    logits, labels = oof_logits(rows, feature_set, sorted({row["participant_id"] for row in rows}))
    a, b = fit_platt(logits, labels)
    prepared = training_rows(rows, feature_set)
    probabilities: dict[tuple[str, str, int], float] = {}
    for position, participant in enumerate(prepared.participant):
        key = (participant, prepared.session[position], prepared.index[position])
        probabilities[key] = predict_probability(
            float(logits[position]), {"type": "platt", "a": a, "b": b}
        )
    return probabilities, (a, b)


def _predictions_for_all_rows(
    rows: list[dict[str, Any]],
    probabilities: dict[tuple[str, str, int], float],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        key = _key(row)
        probability = probabilities.get(key, 0.0)
        result.append(
            {
                "participant_id": row["participant_id"],
                "session_id": row["session_id"],
                "window_index": int(row["index"]),
                "start_offset_ms": int(row["start_offset_ms"]),
                "duration_ms": int(row.get("duration_ms", 10_000)),
                "label": row.get("label"),
                "observable": bool(row.get("observable")),
                "dominant_stage": row.get("dominant_stage"),
                "probability": probability,
            }
        )
    return result


def choose_threshold(
    rows: list[dict[str, Any]],
    probabilities: dict[tuple[str, str, int], float],
    *,
    grid: tuple[float, ...] = DEFAULT_THRESHOLD_GRID,
) -> tuple[float, dict[str, Any]]:
    """Select on training-fold OOF probabilities only.

    First satisfy the pre-registered false-alert budget (<= 1/hour), then
    maximize off-task recall, then minimize false alerts and threshold.
    """
    predictions = _predictions_for_all_rows(rows, probabilities)
    best: tuple[tuple[Any, ...], float, dict[str, Any]] | None = None
    for threshold in grid:
        metrics = alert_metrics(rows, predictions, threshold)
        classification = classification_metrics(rows, predictions, threshold)
        false_rate = metrics["false_alerts_per_hour"]
        budget_ok = false_rate is not None and false_rate <= MAX_RELEASE_FALSE_ALERTS_PER_HOUR
        macro_f1 = classification.get("macro_f1") or 0.0
        recall = metrics.get("true_alerts", 0) / max(1, metrics.get("off_task_segments", 0))
        score = (
            1 if budget_ok else 0,
            macro_f1,
            recall,
            -float(false_rate) if false_rate is not None else -999.0,
            -threshold,
        )
        if best is None or score > best[0]:
            best = (score, threshold, metrics)
    assert best is not None
    return best[1], best[2]


def train_fold(
    train_rows: list[dict[str, Any]],
    *,
    feature_set: str,
    model_version: str,
    data_source: str,
    annotation_kappa: float | None,
) -> dict[str, Any]:
    if not train_rows:
        raise ContractError("训练折为空")
    probabilities, calibration = _oof_probabilities(train_rows, feature_set)
    threshold, selection_metrics = choose_threshold(train_rows, probabilities)
    participants = len({row["participant_id"] for row in train_rows})
    release = {
        "eligible": False,
        "reason": "not_evaluated",
        "required": {
            "min_valid_observation_coverage": MIN_RELEASE_COVERAGE,
            "max_false_alerts_per_hour": MAX_RELEASE_FALSE_ALERTS_PER_HOUR,
            "min_annotation_kappa": MIN_RELEASE_KAPPA,
            "min_participants": MIN_RELEASE_PARTICIPANTS,
        },
    }
    model = build_model(
        train_rows,
        feature_set=feature_set,
        model_version=model_version,
        calibration=calibration,
        threshold=threshold,
        training_metadata={
            "participants": participants,
            "windows": len(train_rows),
            "positive": sum(1 for row in train_rows if row["label"] == "off_task"),
            "negative": sum(1 for row in train_rows if row["label"] == "on_task"),
            "data_source": data_source,
            "annotation_kappa": annotation_kappa,
            "threshold_selection": {
                "false_alerts_per_hour": selection_metrics.get("false_alerts_per_hour"),
                "off_task_segments": selection_metrics.get("off_task_segments"),
                "true_alerts": selection_metrics.get("true_alerts"),
            },
        },
        release=release,
    )
    return model


def train_and_evaluate(
    rows: list[dict[str, Any]],
    *,
    feature_set: str,
    seed: int,
    model_version: str,
    data_source: str,
    annotation_kappa: float | None,
) -> dict[str, Any]:
    participants = sorted({row["participant_id"] for row in rows})
    if len(participants) < 2:
        raise ContractError("LOPO 至少需要 2 名参与者")
    prediction_map: dict[tuple[str, str, int], dict[str, Any]] = {}
    per_participant: dict[str, Any] = {}
    for participant in participants:
        train_rows = [row for row in rows if row["participant_id"] != participant]
        test_rows = [row for row in rows if row["participant_id"] == participant]
        model = train_fold(
            train_rows,
            feature_set=feature_set,
            model_version=f"{model_version}-fold-{participant}",
            data_source=data_source,
            annotation_kappa=annotation_kappa,
        )
        fold_predictions = predict_rows(model, test_rows)
        for prediction in fold_predictions:
            prediction_map[
                (prediction["participant_id"], prediction["session_id"], prediction["window_index"])
            ] = prediction
        per_participant[participant] = _fold_metrics(test_rows, fold_predictions, model)
    predictions = [
        prediction_map[_key(row)]
        for row in rows
    ]
    # Each fold keeps its own threshold for per-participant metrics; the pooled
    # view reports the median threshold as a scalar.
    thresholds = [item["threshold"] for item in per_participant.values()]
    reporting_threshold = float(np.median(thresholds))
    pooled = pooled_metrics(rows, predictions, reporting_threshold)
    groups = {
        field: evaluate_groups(rows, predictions, reporting_threshold, field)
        for field in ("glasses", "lighting", "device", "context")
    }
    summary = participant_summary(per_participant)

    coverage = pooled.get("observation_coverage")
    false_rate = pooled.get("false_alerts_per_hour")
    release_ok = (
        data_source == "real"
        and coverage is not None
        and coverage >= MIN_RELEASE_COVERAGE
        and false_rate is not None
        and false_rate <= MAX_RELEASE_FALSE_ALERTS_PER_HOUR
        and annotation_kappa is not None
        and annotation_kappa >= MIN_RELEASE_KAPPA
        and len(participants) >= MIN_RELEASE_PARTICIPANTS
    )
    reasons: list[str] = []
    if data_source != "real":
        reasons.append("synthetic_or_non_pilot_data")
    if coverage is None or coverage < MIN_RELEASE_COVERAGE:
        reasons.append("observation_coverage_below_0.80")
    if false_rate is None or false_rate > MAX_RELEASE_FALSE_ALERTS_PER_HOUR:
        reasons.append("false_alerts_above_1_per_hour")
    if annotation_kappa is None or annotation_kappa < MIN_RELEASE_KAPPA:
        reasons.append("missing_or_low_annotation_kappa")
    if len(participants) < MIN_RELEASE_PARTICIPANTS:
        reasons.append("participants_below_5")
    release = {
        "eligible": release_ok,
        "reason": "all_conditions_met" if release_ok else "|".join(reasons),
        "required": {
            "min_valid_observation_coverage": MIN_RELEASE_COVERAGE,
            "max_false_alerts_per_hour": MAX_RELEASE_FALSE_ALERTS_PER_HOUR,
            "min_annotation_kappa": MIN_RELEASE_KAPPA,
            "min_participants": MIN_RELEASE_PARTICIPANTS,
            "real_pilot_data": True,
        },
    }

    final_model = train_fold(
        rows,
        feature_set=feature_set,
        model_version=model_version,
        data_source=data_source,
        annotation_kappa=annotation_kappa,
    )
    final_model["release"] = release
    result = {
        "feature_set": feature_set,
        "seed": seed,
        "data_source": data_source,
        "annotation_kappa": annotation_kappa,
        "participants": participants,
        "pooled": pooled,
        "per_participant": per_participant,
        "participant_summary": summary,
        "groups": groups,
        "release": release,
        "reporting_threshold": reporting_threshold,
        "model": final_model,
        "prediction_map_size": len(prediction_map),
    }
    return result


def _fold_metrics(
    rows: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    model: dict[str, Any],
) -> dict[str, Any]:
    result = {
        "threshold": float(model["decision_threshold"]),
        **classification_metrics(rows, predictions, model["decision_threshold"]),
        **alert_metrics(rows, predictions, model["decision_threshold"]),
    }
    return result


def compare_feature_sets(
    rows: list[dict[str, Any]],
    *,
    seed: int,
    model_version_prefix: str,
    data_source: str,
    annotation_kappa: float | None,
) -> dict[str, Any]:
    runs: dict[str, Any] = {}
    for feature_set in ("baseline", "headpose"):
        runs[feature_set] = train_and_evaluate(
            rows,
            feature_set=feature_set,
            seed=seed,
            model_version=f"{model_version_prefix}-{feature_set}",
            data_source=data_source,
            annotation_kappa=annotation_kappa,
        )
    baseline = runs["baseline"]["pooled"]
    headpose = runs["headpose"]["pooled"]

    def delta(key: str) -> float | None:
        left = baseline.get(key)
        right = headpose.get(key)
        if left is None or right is None:
            return None
        return right - left

    return {
        "seed": seed,
        "data_source": data_source,
        "baseline": runs["baseline"],
        "headpose": runs["headpose"],
        "comparison": {
            # 两组共用同一可观察性门槛与同一批窗口，因此这里是等覆盖率比较；
            # 报告各自阈值和误提示率，便于确认差异不是放宽门槛换来的。
            "matched_on": "coverage_gate",
            "coverage_gate_equal": (
                runs["baseline"]["model"]["coverage_gate"]
                == runs["headpose"]["model"]["coverage_gate"]
            ),
            "coverage_gate": runs["headpose"]["model"]["coverage_gate"],
            "baseline_threshold": runs["baseline"].get("reporting_threshold"),
            "headpose_threshold": runs["headpose"].get("reporting_threshold"),
            "baseline_false_alerts_per_hour": baseline.get("false_alerts_per_hour"),
            "headpose_false_alerts_per_hour": headpose.get("false_alerts_per_hour"),
            "macro_f1_delta": delta("macro_f1"),
            "off_task_recall_delta": delta("off_task_recall"),
            "off_task_precision_delta": delta("off_task_precision"),
            "auprc_delta": delta("auprc"),
            "ece_delta": delta("ece"),
            "coverage_delta": delta("model_coverage"),
            "false_alerts_per_hour_delta": delta("false_alerts_per_hour"),
            "delay_median_seconds_delta": delta("delay_median_seconds"),
            "headpose_incremental": (
                (delta("macro_f1") or 0.0) > 0.0
                and (delta("off_task_recall") or 0.0) >= 0.0
                and (delta("false_alerts_per_hour") or 0.0) <= 0.0
            ),
        },
    }

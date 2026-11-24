"""Metrics for window labels, selective prediction and reminder behaviour."""

from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np

ALERT_CONSECUTIVE_WINDOWS = 2
ALERT_COOLDOWN_MS = 120_000
SUPPRESS_STAGES = {"lecture", "quiz"}


def _f1(tp: int, fp: int, fn: int) -> float:
    if tp == 0:
        return 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def auprc(labels: list[int], scores: list[float]) -> float | None:
    if not labels or len(labels) != len(scores):
        return None
    if len(set(labels)) < 2:
        return None
    order = sorted(range(len(labels)), key=lambda index: scores[index], reverse=True)
    positives = sum(labels)
    tp = 0
    fp = 0
    points: list[tuple[float, float]] = [(0.0, 1.0)]
    for index in order:
        if labels[index] == 1:
            tp += 1
        else:
            fp += 1
        points.append((tp / positives, tp / (tp + fp)))
    area = 0.0
    for (recall_a, precision_a), (recall_b, precision_b) in zip(points, points[1:]):
        area += (recall_b - recall_a) * (precision_b + precision_a) / 2.0
    return area


def ece(labels: list[int], probabilities: list[float], bins: int = 10) -> float | None:
    if not labels or len(labels) != len(probabilities):
        return None
    bucket_total = [0] * bins
    bucket_positive = [0] * bins
    bucket_confidence = [0.0] * bins
    for label, probability in zip(labels, probabilities):
        bucket = min(bins - 1, max(0, int(probability * bins)))
        bucket_total[bucket] += 1
        bucket_positive[bucket] += label
        bucket_confidence[bucket] += probability
    total = len(labels)
    error = 0.0
    for bucket in range(bins):
        if bucket_total[bucket] == 0:
            continue
        accuracy = bucket_positive[bucket] / bucket_total[bucket]
        confidence = bucket_confidence[bucket] / bucket_total[bucket]
        error += bucket_total[bucket] / total * abs(accuracy - confidence)
    return error


def brier(labels: list[int], probabilities: list[float]) -> float | None:
    if not labels:
        return None
    return float(np.mean((np.asarray(probabilities) - np.asarray(labels)) ** 2))


def _is_off_task(prediction: dict[str, Any], threshold: float | None) -> bool:
    if threshold is None:
        return prediction["predicted"] == "off_task"
    return float(prediction["probability"]) >= threshold


def classification_metrics(
    rows: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    threshold: float | None,
) -> dict[str, Any]:
    completed = [row for row in rows if row.get("complete", True)]
    labelled = [row for row in completed if row.get("label") in ("on_task", "off_task")]
    covered_pairs = [
        (row, prediction)
        for row, prediction in zip(rows, predictions)
        if row.get("complete", True)
        and row.get("label") in ("on_task", "off_task")
        and row.get("observable")
    ]
    labels = [1 if row["label"] == "off_task" else 0 for row, _ in covered_pairs]
    scores = [float(prediction["probability"]) for _, prediction in covered_pairs]
    predicted = [int(_is_off_task(prediction, threshold)) for _, prediction in covered_pairs]
    tp = sum(1 for label, guess in zip(labels, predicted) if label == 1 and guess == 1)
    fp = sum(1 for label, guess in zip(labels, predicted) if label == 0 and guess == 1)
    fn = sum(1 for label, guess in zip(labels, predicted) if label == 1 and guess == 0)
    tn = sum(1 for label, guess in zip(labels, predicted) if label == 0 and guess == 0)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    macro_f1 = (
        (_f1(tp, fp, fn) + _f1(tn, fn, fp)) / 2.0 if labels else None
    )
    return {
        "n_labelled_windows": len(labelled),
        "n_covered_windows": len(covered_pairs),
        "observation_coverage": (
            sum(1 for row in completed if row.get("observable")) / len(completed)
            if completed
            else None
        ),
        "model_coverage": len(covered_pairs) / len(labelled) if labelled else None,
        "positive_rate": sum(labels) / len(labels) if labels else None,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "off_task_precision": precision,
        "off_task_recall": recall,
        "macro_f1": macro_f1,
        "auprc": auprc(labels, scores),
        "ece": ece(labels, scores),
        "brier": brier(labels, scores),
    }


def simulate_alerts(
    rows: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    threshold: float | None,
    *,
    consecutive: int = ALERT_CONSECUTIVE_WINDOWS,
    cooldown_ms: int = ALERT_COOLDOWN_MS,
) -> list[dict[str, Any]]:
    """Deterministic reminder policy used by both offline evaluation and Android."""
    alerts: list[dict[str, Any]] = []
    by_session: dict[tuple[str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for row, prediction in zip(rows, predictions):
        if row.get("complete", True):
            key = (row["participant_id"], row["session_id"])
            by_session.setdefault(key, []).append((row, prediction))
    for _, pairs in sorted(by_session.items()):
        candidate_run = 0
        last_alert_end = None
        previous_end = None
        for row, prediction in sorted(pairs, key=lambda pair: pair[0]["start_offset_ms"]):
            start = int(row["start_offset_ms"])
            if previous_end is not None and start < previous_end:
                continue
            if start != previous_end:
                candidate_run = 0
            duration = int(row.get("duration_ms", 10_000))
            alert_time = start + duration
            previous_end = alert_time
            stage = row.get("dominant_stage")
            eligible = (
                row.get("observable")
                and _is_off_task(prediction, threshold)
                and stage not in SUPPRESS_STAGES
            )
            if not eligible:
                candidate_run = 0
                continue
            candidate_run += 1
            if candidate_run < consecutive:
                continue
            if last_alert_end is not None and alert_time < last_alert_end + cooldown_ms:
                continue
            alerts.append(
                {
                    "participant_id": row["participant_id"],
                    "session_id": row["session_id"],
                    "window_index": int(row["index"]),
                    "start_offset_ms": start,
                    "alert_offset_ms": alert_time,
                    "duration_ms": duration,
                    "ground_truth": row.get("label"),
                    "probability": float(prediction["probability"]),
                }
            )
            last_alert_end = alert_time
            candidate_run = 0
    return alerts


def alert_metrics(
    rows: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    threshold: float | None,
) -> dict[str, Any]:
    alerts = simulate_alerts(rows, predictions, threshold)
    hours = sum(
        float(row.get("duration_ms", 10_000))
        for row in rows
        if row.get("complete", True) and row.get("label") is not None
    ) / 3_600_000.0
    false_alerts = [
        alert
        for alert in alerts
        if alert["ground_truth"] in ("on_task", "unobservable")
    ]
    unresolved_alerts = [alert for alert in alerts if alert["ground_truth"] is None]
    true_alerts = [alert for alert in alerts if alert["ground_truth"] == "off_task"]

    segments: list[dict[str, Any]] = []
    by_session: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("complete", True):
            by_session.setdefault((row["participant_id"], row["session_id"]), []).append(row)
    for _, session_rows in sorted(by_session.items()):
        current: list[dict[str, Any]] = []
        previous_end = None
        for row in sorted(session_rows, key=lambda item: item["start_offset_ms"]):
            start = int(row["start_offset_ms"])
            if previous_end is not None and start < previous_end:
                continue
            off_task = row.get("label") == "off_task"
            if current and (not off_task or start != previous_end):
                segments.append(_segment(current))
                current = []
            if off_task:
                current.append(row)
            previous_end = start + int(row.get("duration_ms", 10_000))
        if current:
            segments.append(_segment(current))

    delays: list[float] = []
    missed = 0
    for segment in segments:
        hits = [
            alert
            for alert in true_alerts
            if alert["participant_id"] == segment["participant_id"]
            and alert["session_id"] == segment["session_id"]
            and segment["start_offset_ms"] < alert["alert_offset_ms"] <= segment["end_offset_ms"]
        ]
        if hits:
            alert_time = hits[0]["alert_offset_ms"]
            delays.append((alert_time - segment["start_offset_ms"]) / 1000.0)
        else:
            missed += 1

    return {
        "observed_hours": hours,
        "alerts": len(alerts),
        "true_alerts": len(true_alerts),
        "false_alerts": len(false_alerts),
        "unresolved_alerts": len(unresolved_alerts),
        "false_alerts_per_hour": len(false_alerts) / hours if hours > 0 else None,
        "alert_precision": (
            len(true_alerts) / (len(true_alerts) + len(false_alerts))
            if len(true_alerts) + len(false_alerts)
            else None
        ),
        "off_task_segments": len(segments),
        "missed_off_task_segments": missed,
        "off_task_segment_recall": len(delays) / len(segments) if segments else None,
        "missed_per_hour": missed / hours if hours > 0 else None,
        "delay_median_seconds": _percentile(delays, 0.5),
        "delay_p90_seconds": _percentile(delays, 0.9),
        "alert_details": alerts[:200],
    }


def _segment(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "participant_id": rows[0]["participant_id"],
        "session_id": rows[0]["session_id"],
        "start_offset_ms": int(rows[0]["start_offset_ms"]),
        "end_offset_ms": int(rows[-1]["start_offset_ms"]) + int(rows[-1].get("duration_ms", 10_000)),
        "windows": len(rows),
    }


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return ordered[low]
    return ordered[low] * (high - position) + ordered[high] * (position - low)


def evaluate_by_participant(
    rows: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    threshold: float,
) -> dict[str, Any]:
    participants = sorted({row["participant_id"] for row in rows})
    result: dict[str, Any] = {}
    for participant in participants:
        mask = [row["participant_id"] == participant for row in rows]
        part_rows = [row for row, keep in zip(rows, mask) if keep]
        part_predictions = [pred for pred, keep in zip(predictions, mask) if keep]
        result[participant] = {
            **classification_metrics(part_rows, part_predictions, threshold),
            **alert_metrics(part_rows, part_predictions, threshold),
        }
    return result


def evaluate_groups(
    rows: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    threshold: float | None,
    group_field: str,
) -> dict[str, Any]:
    values = sorted({str(row.get(group_field, "unknown")) for row in rows})
    result: dict[str, Any] = {}
    for value in values:
        mask = [str(row.get(group_field, "unknown")) == value for row in rows]
        group_rows = [row for row, keep in zip(rows, mask) if keep]
        group_predictions = [pred for pred, keep in zip(predictions, mask) if keep]
        participants = len({row["participant_id"] for row in group_rows})
        result[value] = {
            "participants": participants,
            **classification_metrics(group_rows, group_predictions, threshold),
            **alert_metrics(group_rows, group_predictions, threshold),
            "descriptive_only": participants < 3,
        }
    return result


def pooled_metrics(
    rows: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    threshold: float | None,
) -> dict[str, Any]:
    return {
        **classification_metrics(rows, predictions, threshold),
        **alert_metrics(rows, predictions, threshold),
        "participants": len({row["participant_id"] for row in rows}),
    }


def participant_summary(per_participant: dict[str, dict[str, Any]]) -> dict[str, Any]:
    def values(key: str) -> list[float]:
        return [
            float(item[key])
            for item in per_participant.values()
            if item.get(key) is not None
        ]

    summary: dict[str, Any] = {}
    for key in (
        "model_coverage",
        "macro_f1",
        "off_task_precision",
        "off_task_recall",
        "auprc",
        "ece",
        "false_alerts_per_hour",
        "off_task_segment_recall",
        "missed_per_hour",
        "delay_median_seconds",
        "delay_p90_seconds",
    ):
        items = values(key)
        summary[key] = {
            "median": _percentile(items, 0.5),
            "p25": _percentile(items, 0.25),
            "p75": _percentile(items, 0.75),
            "n": len(items),
        }
    return summary

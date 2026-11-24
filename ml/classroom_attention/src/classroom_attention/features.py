"""Window-level feature extraction.

Features mirror the facts exported by `ClassroomObservationExport`; no raw
frame, face embedding or identity data is used. Missing head-pose values stay
`None` and are imputed with training-fold medians only.
"""

from __future__ import annotations

from typing import Any

SAMPLE_INTERVAL_MS = 250

BASELINE_FEATURES = (
    "face_visible_ratio",
    "valid_coverage",
    "invalid_ratio",
    "manual_page_turns",
    "quiz_submissions",
    "questions",
    "stage_quiz",
    "stage_lecture",
)

HEADPOSE_FEATURES = BASELINE_FEATURES + (
    "yaw_mean",
    "yaw_std",
    "yaw_range",
    "pitch_mean",
    "pitch_std",
    "pitch_range",
)

FEATURE_SETS = {
    "baseline": BASELINE_FEATURES,
    "headpose": HEADPOSE_FEATURES,
}

FEATURE_LABELS = {
    "face_visible_ratio": "人脸可见比例",
    "valid_coverage": "有效采样覆盖率",
    "invalid_ratio": "无效采样比例",
    "manual_page_turns": "主动翻页次数",
    "quiz_submissions": "主动交卷次数",
    "questions": "主动提问次数",
    "stage_quiz": "测验页",
    "stage_lecture": "讲解态",
    "yaw_mean": "偏航均值",
    "yaw_std": "偏航标准差",
    "yaw_range": "偏航极差",
    "pitch_mean": "俯仰均值",
    "pitch_std": "俯仰标准差",
    "pitch_range": "俯仰极差",
}


def extract_features(window: dict[str, Any]) -> dict[str, float | None]:
    duration = max(0, int(window["end_offset_ms"]) - int(window["start_offset_ms"]))
    expected = max(1, duration // SAMPLE_INTERVAL_MS)
    valid = float(window["valid_samples"])
    invalid = float(window["invalid_samples"])
    face = float(window["face_visible_samples"])
    samples = valid + invalid
    yaw = window.get("yaw")
    pitch = window.get("pitch")
    return {
        "face_visible_ratio": float(window["face_visible_ratio"]),
        "valid_coverage": min(1.0, valid / expected),
        "invalid_ratio": invalid / samples if samples > 0 else None,
        "manual_page_turns": float(window["manual_page_turns"]),
        "quiz_submissions": float(window["quiz_submissions"]),
        "questions": float(window["questions"]),
        "stage_quiz": 1.0 if window.get("dominant_stage") == "quiz" else 0.0,
        "stage_lecture": 1.0 if window.get("dominant_stage") == "lecture" else 0.0,
        "yaw_mean": float(yaw["mean"]) if yaw else None,
        "yaw_std": float(yaw["standard_deviation"]) if yaw else None,
        "yaw_range": float(yaw["max"]) - float(yaw["min"]) if yaw else None,
        "pitch_mean": float(pitch["mean"]) if pitch else None,
        "pitch_std": float(pitch["standard_deviation"]) if pitch else None,
        "pitch_range": float(pitch["max"]) - float(pitch["min"]) if pitch else None,
    }


def gate(row: dict[str, Any]) -> bool:
    """Same observability gate as the device-side window verdict."""
    return (
        row.get("verdict") == "observable"
        and float(row["face_visible_ratio"]) >= 0.2
        and float(row.get("valid_coverage", 0.0)) >= 0.5
    )

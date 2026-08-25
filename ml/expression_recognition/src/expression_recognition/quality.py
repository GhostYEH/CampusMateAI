"""Platform-neutral face quality gate used before expression inference."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FaceQualityMetrics:
    face_ratio: float
    sharpness: float
    pitch: float
    yaw: float
    roll: float
    brightness: float
    face_count: int


@dataclass(frozen=True)
class FaceQualityDecision:
    accepted: bool
    reason: str
    score: float


@dataclass(frozen=True)
class FaceQualityConfig:
    minimum_face_ratio: float = 0.12
    minimum_sharpness: float = 18.0
    maximum_abs_pose: float = 25.0
    minimum_brightness: float = 40.0
    maximum_brightness: float = 225.0


def assess_face_quality(
    metrics: FaceQualityMetrics,
    config: FaceQualityConfig = FaceQualityConfig(),
) -> FaceQualityDecision:
    """Return the first stable rejection reason in platform contract order."""
    if metrics.face_count == 0:
        return FaceQualityDecision(False, "NO_FACE", 0.0)
    if metrics.face_count > 1:
        return FaceQualityDecision(False, "MULTIPLE_FACES", 0.0)
    if metrics.face_ratio < config.minimum_face_ratio:
        return FaceQualityDecision(False, "TOO_SMALL", 0.0)
    if max(abs(metrics.pitch), abs(metrics.yaw), abs(metrics.roll)) > config.maximum_abs_pose:
        return FaceQualityDecision(False, "EXTREME_POSE", 0.0)
    if metrics.sharpness < config.minimum_sharpness:
        return FaceQualityDecision(False, "BLUR", 0.0)
    if not config.minimum_brightness <= metrics.brightness <= config.maximum_brightness:
        return FaceQualityDecision(False, "LOW_LIGHT", 0.0)

    size_score = min(1.0, metrics.face_ratio / config.minimum_face_ratio)
    sharpness_score = min(1.0, metrics.sharpness / config.minimum_sharpness)
    pose_score = max(0.0, 1.0 - max(abs(metrics.pitch), abs(metrics.yaw), abs(metrics.roll)) / config.maximum_abs_pose)
    exposure_midpoint = (config.minimum_brightness + config.maximum_brightness) / 2.0
    exposure_half_range = (config.maximum_brightness - config.minimum_brightness) / 2.0
    exposure_score = max(0.0, 1.0 - abs(metrics.brightness - exposure_midpoint) / exposure_half_range)
    return FaceQualityDecision(True, "ACCEPTED", min(size_score, sharpness_score, pose_score, exposure_score))

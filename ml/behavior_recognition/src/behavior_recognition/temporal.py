"""Reference temporal event rules shared by mobile behavior implementations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FramePrediction:
    timestamp_ms: int
    label: str
    confidence: float
    quality_accepted: bool


@dataclass(frozen=True)
class BehaviorEvent:
    label: str
    started_at_ms: int
    ended_at_ms: int | None
    confidence: float
    active: bool
    reminder_allowed: bool


class BehaviorEventAggregator:
    """Apply entry/exit hysteresis and reminder cooldown to PHONE evidence."""

    def __init__(
        self,
        *,
        phone_enter_ms: int = 2000,
        exit_ms: int = 1000,
        reminder_cooldown_ms: int = 600_000,
        minimum_confidence: float = 0.5,
    ) -> None:
        self.phone_enter_ms = phone_enter_ms
        self.exit_ms = exit_ms
        self.reminder_cooldown_ms = reminder_cooldown_ms
        self.minimum_confidence = minimum_confidence
        self._candidate_started_at: int | None = None
        self._candidate_confidences: list[float] = []
        self._active_started_at: int | None = None
        self._exit_started_at: int | None = None
        self._active_confidence = 0.0
        self._last_reminder_at: int | None = None

    def update(self, frame: FramePrediction) -> list[BehaviorEvent]:
        if frame.timestamp_ms < 0:
            return []
        if not frame.quality_accepted or frame.label == "UNCERTAIN":
            return []

        phone = frame.label == "PHONE_INTERACTION" and frame.confidence >= self.minimum_confidence
        if phone:
            self._exit_started_at = None
            if self._active_started_at is not None:
                return []
            if self._candidate_started_at is None:
                self._candidate_started_at = frame.timestamp_ms
                self._candidate_confidences = [frame.confidence]
                return []
            self._candidate_confidences.append(frame.confidence)
            if frame.timestamp_ms - self._candidate_started_at < self.phone_enter_ms:
                return []
            self._active_started_at = self._candidate_started_at
            self._active_confidence = sum(self._candidate_confidences) / len(self._candidate_confidences)
            reminder_allowed = (
                self._last_reminder_at is None
                or frame.timestamp_ms - self._last_reminder_at >= self.reminder_cooldown_ms
            )
            if reminder_allowed:
                self._last_reminder_at = frame.timestamp_ms
            return [BehaviorEvent(
                label="PHONE_INTERACTION",
                started_at_ms=self._active_started_at,
                ended_at_ms=None,
                confidence=self._active_confidence,
                active=True,
                reminder_allowed=reminder_allowed,
            )]

        self._candidate_started_at = None
        self._candidate_confidences = []
        if self._active_started_at is None:
            self._exit_started_at = None
            return []
        if self._exit_started_at is None:
            self._exit_started_at = frame.timestamp_ms
            return []
        if frame.timestamp_ms - self._exit_started_at < self.exit_ms:
            return []

        event = BehaviorEvent(
            label="PHONE_INTERACTION",
            started_at_ms=self._active_started_at,
            ended_at_ms=frame.timestamp_ms,
            confidence=self._active_confidence,
            active=False,
            reminder_allowed=False,
        )
        self._active_started_at = None
        self._exit_started_at = None
        self._active_confidence = 0.0
        return [event]

    def reset(self) -> None:
        self._candidate_started_at = None
        self._candidate_confidences = []
        self._active_started_at = None
        self._exit_started_at = None
        self._active_confidence = 0.0
        self._last_reminder_at = None

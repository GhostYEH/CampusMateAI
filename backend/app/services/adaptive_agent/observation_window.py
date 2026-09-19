"""Deterministic, centrally configured outcome-observation timing."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

DEFAULT_OBSERVATION_DAYS = 7
OBSERVATION_GRACE_HOURS = 24


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class ObservationWindowPolicy:
    default_days: int = DEFAULT_OBSERVATION_DAYS
    grace_hours: int = OBSERVATION_GRACE_HOURS

    def due_at(self, *, planned_end: str | None, generated_at: datetime) -> datetime:
        generated_at = generated_at.astimezone(timezone.utc).replace(microsecond=0)
        end = _parse(planned_end)
        if end is not None:
            return end + timedelta(hours=self.grace_hours)
        return generated_at + timedelta(days=self.default_days)

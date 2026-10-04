"""ISO time helpers with explicit policies for timestamps without a timezone.

Internal legacy timestamps use UTC. Provenance requires an explicit offset.
Chaoxing wall-clock timestamps use Shanghai time; agenda output retains offsets.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

SHANGHAI = timezone(timedelta(hours=8))


def _parse_iso(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        return None


def as_utc_assume_utc(moment: datetime) -> datetime:
    """Normalize an internal instant; legacy naive values denote UTC."""
    if moment.utcoffset() is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def parse_iso_assume_utc(value: Any) -> datetime | None:
    """Parse an internal ISO timestamp, interpreting legacy naive values as UTC."""
    parsed = _parse_iso(value)
    return as_utc_assume_utc(parsed) if parsed is not None else None


def parse_iso_require_timezone(value: Any) -> datetime | None:
    """Parse a provenance instant; missing timezone evidence remains unknown."""
    parsed = _parse_iso(value)
    if parsed is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def parse_iso_assume_shanghai(value: Any) -> datetime | None:
    """Parse a local Chaoxing timestamp, retaining an explicitly supplied offset."""
    parsed = _parse_iso(value)
    if parsed is not None and parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed


def iso_utc(moment: datetime) -> str:
    """Serialize internal instants consistently for persisted lease comparisons."""
    return as_utc_assume_utc(moment).isoformat()


def iso_preserve_offset(moment: datetime | None) -> str | None:
    """Serialize a presentation timestamp without changing its original offset."""
    return moment.isoformat() if moment is not None else None

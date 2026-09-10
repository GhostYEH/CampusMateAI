from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional


def _safe_json_object(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


@dataclass
class LearnerEventRow:
    event_id: str
    user_id: str
    occurred_at: str
    received_at: str
    source: str
    event_type: str
    course_id: Optional[str] = None
    subject_type: Optional[str] = None
    subject_id: Optional[str] = None
    external_ref: Optional[str] = None
    outcome: Optional[str] = None
    duration_seconds: Optional[int] = None
    evidence_reference: dict[str, Any] | None = None
    data_quality: str = ""
    consent_scope: str = ""
    source_version: Optional[str] = None
    dedupe_key: str = ""
    payload: Optional[dict[str, Any]] = None
    created_at: str = ""

    @classmethod
    def from_row(cls, row) -> "LearnerEventRow":
        data = dict(row)
        evidence_raw = data.pop("evidence_reference_json", None)
        payload_raw = data.pop("payload_json", None)
        return cls(
            event_id=data.get("event_id", ""),
            user_id=data.get("user_id", ""),
            occurred_at=data.get("occurred_at", ""),
            received_at=data.get("received_at", ""),
            source=data.get("source", ""),
            event_type=data.get("event_type", ""),
            course_id=data.get("course_id"),
            subject_type=data.get("subject_type"),
            subject_id=data.get("subject_id"),
            external_ref=data.get("external_ref"),
            outcome=data.get("outcome"),
            duration_seconds=data.get("duration_seconds"),
            evidence_reference=_safe_json_object(evidence_raw),
            data_quality=data.get("data_quality", ""),
            consent_scope=data.get("consent_scope", ""),
            source_version=data.get("source_version"),
            dedupe_key=data.get("dedupe_key", ""),
            payload=_safe_json_object(payload_raw) or None,
            created_at=data.get("created_at", ""),
        )

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "user_id": self.user_id,
            "occurred_at": self.occurred_at,
            "received_at": self.received_at,
            "source": self.source,
            "event_type": self.event_type,
            "course_id": self.course_id,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "external_ref": self.external_ref,
            "outcome": self.outcome,
            "duration_seconds": self.duration_seconds,
            "evidence_reference": dict(self.evidence_reference or {}),
            "data_quality": self.data_quality,
            "consent_scope": self.consent_scope,
            "source_version": self.source_version,
            "dedupe_key": self.dedupe_key,
            "payload": dict(self.payload or {}),
            "created_at": self.created_at,
        }


__all__ = ["LearnerEventRow"]

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import InitErrorDetails, PydanticCustomError
from pydantic_core import ValidationError as CoreValidationError

WritableSource = Literal["study", "personal_task", "chaoxing", "practice"]
WritableEventType = Literal[
    "study_session_finished",
    "task_completed",
    "course_synced",
    "chapter_completed",
    "assignment_discovered",
    "assignment_submitted",
    "notice_synced",
    "practice_answered",
]
ReservedSource = Literal["edu"]
ReservedEventType = Literal[
    "edu_grade_synced",
]
EventOutcome = Literal["completed", "synced", "discovered", "observed_completed"]
DataQuality = Literal["verified", "partial"]
ConsentScope = Literal["core_learning_record", "connected_learning_platform"]

SOURCE_EVENT_TYPES: dict[str, set[str]] = {
    "study": {"study_session_finished"},
    "personal_task": {"task_completed"},
    "chaoxing": {
        "course_synced",
        "chapter_completed",
        "assignment_discovered",
        "assignment_submitted",
        "notice_synced",
    },
    "practice": {"practice_answered"},
}

EVENT_OUTCOMES: dict[str, str] = {
    "study_session_finished": "completed",
    "task_completed": "completed",
    "course_synced": "synced",
    "assignment_discovered": "discovered",
    "assignment_submitted": "observed_completed",
    "notice_synced": "synced",
    "chapter_completed": "observed_completed",
    "practice_answered": "observed_completed",
}

SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "cookie",
        "cookies",
        "token",
        "accesstoken",
        "refreshtoken",
        "authorization",
        "secret",
        "apikey",
        "code",
        "sourcecode",
        "rawcode",
        "answer",
        "rawanswer",
        "stdout",
        "stderr",
        "compileroutput",
        "prompt",
        "title",
        "body",
        "url",
    }
)


def _normalize_key(key: str) -> str:
    return "".join(ch for ch in key.lower() if ch.isalnum())


def _assert_payload_safe(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if _normalize_key(str(key)) in SENSITIVE_KEYS:
                raise ValueError("payload contains sensitive key")
            _assert_payload_safe(item)
    elif isinstance(value, list):
        for item in value:
            _assert_payload_safe(item)


def _raise_safe_payload_error(message: str) -> None:
    error = InitErrorDetails(
        type=PydanticCustomError("learner_event_payload", message),
        loc=(),
        input=None,
        ctx={},
    )
    raise CoreValidationError.from_exception_data(
        "LearnerEventPayload", [error], hide_input=True
    )


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(..., min_length=1, max_length=64)
    table: str = Field(..., min_length=1, max_length=128)
    row_id: str = Field(..., min_length=1, max_length=128)
    external_id: Optional[str] = Field(None, max_length=256)


class LearnerEventCreate(BaseModel):
    # Payload 校验失败时不能把原始输入(可能含凭据)回显到 ValidationError。
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    source: WritableSource
    event_type: WritableEventType
    occurred_at: datetime
    course_id: Optional[str] = Field(None, max_length=128)
    subject_type: Optional[str] = Field(None, max_length=64)
    subject_id: Optional[str] = Field(None, max_length=128)
    external_ref: Optional[str] = Field(None, max_length=256)
    outcome: EventOutcome = "completed"
    duration_seconds: Optional[int] = Field(None, ge=0, le=86400 * 30)
    evidence_reference: EvidenceReference
    data_quality: DataQuality = "verified"
    consent_scope: ConsentScope = "core_learning_record"
    source_version: Optional[str] = Field(None, max_length=64)
    dedupe_key: str = Field(..., min_length=1, max_length=256)
    payload: Optional[dict[str, Any]] = Field(None, max_length=32)

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must carry timezone")
        return value.astimezone(timezone.utc)

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if value is None:
            return None
        try:
            raw = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            _raise_safe_payload_error("payload is not JSON serializable")
        if len(raw) > 4096:
            _raise_safe_payload_error("payload too large")
        try:
            _assert_payload_safe(value)
        except ValueError:
            _raise_safe_payload_error("payload contains sensitive key")
        return value

    @model_validator(mode="after")
    def validate_source_event_combination(self) -> "LearnerEventCreate":
        allowed = SOURCE_EVENT_TYPES.get(self.source, set())
        if self.event_type not in allowed:
            raise ValueError("illegal source and event_type combination")
        if self.outcome != EVENT_OUTCOMES[self.event_type]:
            raise ValueError("outcome does not match event type")
        expected_consent = (
            "connected_learning_platform"
            if self.source == "chaoxing"
            else "core_learning_record"
        )
        if self.consent_scope != expected_consent:
            raise ValueError("consent_scope does not match event source")
        return self


class LearnerEventOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    user_id: str
    occurred_at: datetime
    received_at: datetime
    source: str
    event_type: str
    course_id: Optional[str] = None
    subject_type: Optional[str] = None
    subject_id: Optional[str] = None
    external_ref: Optional[str] = None
    outcome: Optional[str] = None
    duration_seconds: Optional[int] = None
    evidence_reference: dict[str, Any] = Field(default_factory=dict)
    data_quality: str
    consent_scope: str
    source_version: Optional[str] = None
    dedupe_key: str
    payload: Optional[dict[str, Any]] = None
    created_at: datetime


class LearnerEventAppendResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    created: bool


__all__ = [
    "EvidenceReference",
    "LearnerEventAppendResult",
    "LearnerEventCreate",
    "LearnerEventOut",
    "SOURCE_EVENT_TYPES",
]

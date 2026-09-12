from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .c_knowledge import KnowledgeMasteryValue

SnapshotDataQuality = Literal["verified", "partial", "stale", "unavailable"]
ScopeType = Literal["USER", "COURSE", "TASK", "SOURCE", "KNOWLEDGE_COMPONENT"]
StateType = Literal[
    "observed_learning_activity",
    "task_workload",
    "deadline_exposure",
    "course_participation",
    "data_source_health",
    "knowledge_mastery_estimate",
]
ChangeType = Literal["ADDED", "UPDATED", "REMOVED", "UNCHANGED"]


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("datetime must carry timezone")
    return value


class ObservedLearningActivityValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_sessions_7d: int = Field(ge=0)
    observed_sessions_30d: int = Field(ge=0)
    observed_study_seconds_7d: int = Field(ge=0)
    observed_study_seconds_30d: int = Field(ge=0)
    observed_completed_tasks_7d: int = Field(ge=0)
    observed_completed_tasks_30d: int = Field(ge=0)
    last_observed_activity_at: datetime | None = None

    _aware_last = field_validator("last_observed_activity_at")(_aware)


class TaskWorkloadValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    known_pending: int = Field(ge=0)
    known_overdue: int = Field(ge=0)
    known_due_24h: int = Field(ge=0)
    known_due_7d: int = Field(ge=0)
    known_later: int = Field(default=0, ge=0)
    known_without_deadline: int = Field(ge=0)
    unknown_deadline: int = Field(ge=0)


DeadlineBucket = Literal["OVERDUE", "DUE_24H", "DUE_7D", "LATER", "NO_DEADLINE", "UNKNOWN"]


class DeadlineExposureValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bucket: DeadlineBucket


class CourseParticipationValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_chapters_completed: int = Field(ge=0)
    observed_assignments_discovered: int = Field(ge=0)
    observed_assignments_completed: int = Field(ge=0)
    last_observed_course_activity_at: datetime | None = None
    evidence_quality: SnapshotDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)

    _aware_last = field_validator("last_observed_course_activity_at")(_aware)


SourceHealthStatus = Literal["FRESH", "PARTIAL", "STALE", "UNAVAILABLE"]


class DataSourceHealthValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SourceHealthStatus
    last_successful_observation_at: datetime | None = None
    valid_until: datetime | None = None
    warning_codes: list[str] = Field(default_factory=list, max_length=16)

    _aware_last = field_validator("last_successful_observation_at", "valid_until")(_aware)

    @model_validator(mode="after")
    def require_observation_for_stale(self) -> "DataSourceHealthValue":
        if self.status == "STALE" and self.last_successful_observation_at is None:
            raise ValueError("stale source health requires an observation time")
        if self.status == "FRESH" and self.last_successful_observation_at is None:
            raise ValueError("fresh source health requires an observation time")
        return self


StateValue = Annotated[
    Union[
        ObservedLearningActivityValue,
        TaskWorkloadValue,
        DeadlineExposureValue,
        CourseParticipationValue,
        DataSourceHealthValue,
        KnowledgeMasteryValue,
    ],
    Field(union_mode="smart"),
]


class LearnerStateSnapshotOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    run_id: str
    scope_type: ScopeType
    scope_id: str
    state_type: StateType
    value: StateValue
    confidence: float = Field(ge=0, le=1)
    data_quality: SnapshotDataQuality
    observed_from: datetime | None = None
    observed_through: datetime | None = None
    valid_until: datetime | None = None
    computed_at: datetime
    projection_kind: str = "CORE"
    projection_scope: str = "__user__"

    _aware_times = field_validator(
        "observed_from", "observed_through", "valid_until", "computed_at"
    )(_aware)

    @model_validator(mode="after")
    def validate_value_for_state(self) -> "LearnerStateSnapshotOut":
        expected = {
            "observed_learning_activity": ObservedLearningActivityValue,
            "task_workload": TaskWorkloadValue,
            "deadline_exposure": DeadlineExposureValue,
            "course_participation": CourseParticipationValue,
            "data_source_health": DataSourceHealthValue,
            "knowledge_mastery_estimate": KnowledgeMasteryValue,
        }[self.state_type]
        if not isinstance(self.value, expected):
            raise ValueError("value does not match state_type")
        if self.data_quality == "unavailable" and self.confidence != 0:
            raise ValueError("unavailable state confidence must be zero")
        if self.data_quality == "stale" and self.confidence > 0.25:
            raise ValueError("stale state confidence is capped at 0.25")
        if self.data_quality == "partial" and self.confidence > 0.6:
            raise ValueError("partial state confidence is capped at 0.6")
        return self


class LearnerStateSnapshotPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LearnerStateSnapshotOut]
    total: int
    page: int
    page_size: int
    has_more: bool


class LearnerStateEvidenceOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_kind: Literal["EVENT", "SOURCE_ROW", "SYNC_STATUS"]
    source_category: Literal[
        "study_session", "personal_task", "practice_attempt", "course_content", "course_sync",
        "core_learning_record", "chaoxing", "unknown"
    ]
    event_id: str | None = None
    event_type: str | None = None
    occurred_at: datetime | None = None
    data_quality: SnapshotDataQuality | None = None
    role: Literal["SUPPORTS", "LIMITS", "INVALIDATES"]
    explanation_code: Literal[
        "completed_study_session", "current_pending_task", "observed_platform_completion",
        "chapter_sync_complete", "chapter_data_stale", "source_disconnected",
        "event_projection_gap", "input_truncated", "historical_submission_not_current",
        "orphan_assignment_submitted", "platform_event_observed", "state_observed", "practice_result",
    ]

    _aware_occurred = field_validator("occurred_at")(_aware)


class LearnerStateEvidencePage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LearnerStateEvidenceOut]
    total: int
    page: int
    page_size: int
    has_more: bool


class LearnerStateRunOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    as_of: datetime
    computed_at: datetime
    estimator_version: str
    trigger: str
    is_current: bool
    warning_codes: list[str] = Field(default_factory=list, max_length=32)
    snapshot_count: int = Field(ge=0)
    projection_kind: Literal["CORE", "KNOWLEDGE"] = "CORE"
    projection_scope: str = "__user__"

    _aware_times = field_validator("as_of", "computed_at")(_aware)


class LearnerStateRunPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LearnerStateRunOut]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    has_more: bool


ChangeExplanationCode = Literal[
    "state_added", "state_removed", "observed_value_changed", "data_quality_changed",
    "deadline_bucket_changed", "source_freshness_changed", "authoritative_task_changed",
    "event_projection_gap", "input_truncated",
]


class LearnerStateChangeOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_type: ScopeType
    scope_id: str
    state_type: StateType
    change_type: ChangeType
    previous_value: StateValue | None = None
    current_value: StateValue | None = None
    previous_quality: SnapshotDataQuality | None = None
    current_quality: SnapshotDataQuality | None = None
    previous_confidence: float | None = Field(default=None, ge=0, le=1)
    current_confidence: float | None = Field(default=None, ge=0, le=1)
    explanation_codes: list[ChangeExplanationCode] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def validate_values(self) -> "LearnerStateChangeOut":
        expected = {
            "observed_learning_activity": ObservedLearningActivityValue,
            "task_workload": TaskWorkloadValue,
            "deadline_exposure": DeadlineExposureValue,
            "course_participation": CourseParticipationValue,
            "data_source_health": DataSourceHealthValue,
        }[self.state_type]
        if self.previous_value is not None and not isinstance(self.previous_value, expected):
            raise ValueError("previous_value does not match state_type")
        if self.current_value is not None and not isinstance(self.current_value, expected):
            raise ValueError("current_value does not match state_type")
        return self


class LearnerStateChangePage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_run_id: str | None
    to_run_id: str
    estimator_changed: bool
    changes: list[LearnerStateChangeOut]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    has_more: bool


__all__ = [
    "CourseParticipationValue",
    "DataSourceHealthValue",
    "DeadlineExposureValue",
    "LearnerStateEvidenceOut",
    "LearnerStateEvidencePage",
    "LearnerStateChangeOut",
    "LearnerStateChangePage",
    "LearnerStateRunOut",
    "LearnerStateRunPage",
    "LearnerStateSnapshotOut",
    "LearnerStateSnapshotPage",
    "ObservedLearningActivityValue",
    "SnapshotDataQuality",
    "TaskWorkloadValue",
]

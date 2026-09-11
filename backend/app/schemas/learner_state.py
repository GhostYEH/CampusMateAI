from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SnapshotDataQuality = Literal["verified", "partial", "stale", "unavailable"]
ScopeType = Literal["USER", "COURSE", "TASK", "SOURCE"]
StateType = Literal[
    "observed_learning_activity",
    "task_workload",
    "deadline_exposure",
    "course_participation",
    "data_source_health",
]


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
    evidence_quality: Literal["verified", "partial"]

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

    event_id: str | None = None
    source: str | None = None
    event_type: str | None = None
    occurred_at: datetime | None = None
    data_quality: str | None = None
    role: Literal["SUPPORTS", "LIMITS", "INVALIDATES"]

    _aware_occurred = field_validator("occurred_at")(_aware)


class LearnerStateEvidencePage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LearnerStateEvidenceOut]
    total: int
    page: int
    page_size: int
    has_more: bool


__all__ = [
    "CourseParticipationValue",
    "DataSourceHealthValue",
    "DeadlineExposureValue",
    "LearnerStateEvidenceOut",
    "LearnerStateEvidencePage",
    "LearnerStateSnapshotOut",
    "LearnerStateSnapshotPage",
    "ObservedLearningActivityValue",
    "SnapshotDataQuality",
    "TaskWorkloadValue",
]

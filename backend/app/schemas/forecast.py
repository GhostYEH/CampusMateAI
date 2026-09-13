"""预测 schema — 校园生活与目标执行风险预测。

预测不是"下一道练习的正确率"，而是校园生活和目标执行的风险预测。
禁止预测心理疾病、人格、退学概率、就业成功率等高风险结论。
不得把相关关系表述成因果关系。
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ForecastDataQuality = Literal["verified", "partial", "stale", "unavailable"]
ForecastScopeType = Literal["USER", "COURSE", "TASK", "GOAL", "SEMESTER"]

ForecastType = Literal[
    "DEADLINE_COMPLETION_RISK",
    "UPCOMING_WORKLOAD",
    "SCHEDULE_CONFLICT_RISK",
    "GOAL_PROGRESS_OUTLOOK",
    "ROUTINE_CONTINUITY",
]

ForecastExplanationCode = Literal[
    "insufficient_history",
    "deadline_within_horizon",
    "deadline_outside_horizon",
    "high_pending_density",
    "low_pending_density",
    "exam_collision",
    "schedule_overlap",
    "goal_active",
    "goal_archived",
    "routine_stable",
    "routine_variable",
    "input_truncated",
    "no_observed_sessions",
    "no_observed_tasks",
    "no_observed_goals",
    "no_observed_schedule",
    "projection_failed",
    "stale_input_rejected",
    "horizon_too_short",
    "horizon_too_long",
]

ForecastLimitationCode = Literal[
    "baseline_estimator_only",
    "no_causal_claim",
    "correlation_not_causation",
    "short_history",
    "single_user_scope",
    "no_psychological_inference",
    "no_dropout_prediction",
    "no_employment_prediction",
    "no_personality_prediction",
    "synthetic_calibration_only",
    "not_measured_against_real_outcomes",
]


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("datetime must carry timezone")
    return value


class ForecastEvidenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_session_count: int = Field(default=0, ge=0)
    observed_task_count: int = Field(default=0, ge=0)
    observed_goal_count: int = Field(default=0, ge=0)
    observed_schedule_count: int = Field(default=0, ge=0)
    observed_exam_count: int = Field(default=0, ge=0)
    history_window_days: int = Field(default=0, ge=0)


class DeadlineCompletionRiskValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pending_task_count: int = Field(ge=0)
    overdue_task_count: int = Field(ge=0)
    tasks_within_horizon: int = Field(ge=0)
    risk_band: Literal["LOW", "MODERATE", "HIGH", "VERY_HIGH"]
    data_completeness: ForecastDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


class UpcomingWorkloadValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_count: int = Field(ge=0)
    exam_count: int = Field(ge=0)
    estimated_total_minutes: int = Field(ge=0)
    pressure_band: Literal["LOW", "MODERATE", "HIGH", "VERY_HIGH"]
    concentrated_dates: list[str] = Field(default_factory=list, max_length=16)
    data_completeness: ForecastDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


class ScheduleConflictRiskValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflict_count: int = Field(ge=0)
    exam_collision_count: int = Field(ge=0)
    schedule_overlap_count: int = Field(ge=0)
    available_window_count: int = Field(ge=0)
    risk_band: Literal["LOW", "MODERATE", "HIGH", "VERY_HIGH"]
    data_completeness: ForecastDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


class GoalProgressOutlookValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_goal_count: int = Field(ge=0)
    average_progress_percent: float = Field(ge=0, le=100)
    goals_with_recent_progress: int = Field(ge=0)
    outlook_band: Literal["rising", "steady", "declining", "insufficient_data"]
    data_completeness: ForecastDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


class RoutineContinuityValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_session_count: int = Field(ge=0)
    median_interval_hours: float = Field(ge=0)
    continuity_band: Literal["stable", "variable", "unknown"]
    data_completeness: ForecastDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


ForecastValue = Annotated[
    Union[
        DeadlineCompletionRiskValue,
        UpcomingWorkloadValue,
        ScheduleConflictRiskValue,
        GoalProgressOutlookValue,
        RoutineContinuityValue,
    ],
    Field(union_mode="smart"),
]


class ForecastOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    forecast_id: str
    forecast_type: ForecastType
    scope_type: ForecastScopeType
    scope_id: str
    horizon_start: datetime
    horizon_end: datetime
    probability: float | None = Field(default=None, ge=0, le=1)
    value: ForecastValue
    confidence: float = Field(ge=0, le=1)
    data_quality: ForecastDataQuality
    estimator_version: str
    input_digest: str
    as_of: datetime
    valid_until: datetime
    explanation_codes: list[ForecastExplanationCode] = Field(default_factory=list, max_length=16)
    evidence_summary: ForecastEvidenceSummary
    limitations: list[ForecastLimitationCode] = Field(default_factory=list, max_length=16)

    _aware_times = field_validator(
        "horizon_start", "horizon_end", "as_of", "valid_until"
    )(_aware)

    @model_validator(mode="after")
    def validate_value_for_type(self) -> "ForecastOut":
        expected = {
            "DEADLINE_COMPLETION_RISK": DeadlineCompletionRiskValue,
            "UPCOMING_WORKLOAD": UpcomingWorkloadValue,
            "SCHEDULE_CONFLICT_RISK": ScheduleConflictRiskValue,
            "GOAL_PROGRESS_OUTLOOK": GoalProgressOutlookValue,
            "ROUTINE_CONTINUITY": RoutineContinuityValue,
        }[self.forecast_type]
        if not isinstance(self.value, expected):
            raise ValueError("value does not match forecast_type")
        if self.data_quality == "unavailable":
            if self.confidence != 0:
                raise ValueError("unavailable forecast confidence must be zero")
            if self.probability is not None:
                raise ValueError("unavailable forecast must not carry a probability")
        if self.data_quality == "stale" and self.confidence > 0.25:
            raise ValueError("stale forecast confidence is capped at 0.25")
        if self.data_quality == "partial" and self.confidence > 0.6:
            raise ValueError("partial forecast confidence is capped at 0.6")
        if self.horizon_end <= self.horizon_start:
            raise ValueError("horizon_end must be after horizon_start")
        return self


class ForecastPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ForecastOut]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    has_more: bool


class CalibrationMetricOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_name: Literal[
        "brier_score", "expected_calibration_error", "coverage",
        "abstention_rate", "schema_validity", "evidence_coverage",
        "stale_input_rejection",
    ]
    value: float = Field(ge=0, le=1)
    sample_size: int = Field(ge=0)
    label_source: Literal["real_outcomes", "synthetic", "not_measured"]
    note: str | None = None


class CalibrationReportOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estimator_version: str
    forecast_type: ForecastType | None = None
    as_of: datetime
    metrics: list[CalibrationMetricOut] = Field(default_factory=list, max_length=16)
    overall_label_source: Literal["real_outcomes", "synthetic", "not_measured"]

    _aware_as_of = field_validator("as_of")(_aware)


__all__ = [
    "ForecastDataQuality",
    "ForecastScopeType",
    "ForecastType",
    "ForecastExplanationCode",
    "ForecastLimitationCode",
    "ForecastEvidenceSummary",
    "DeadlineCompletionRiskValue",
    "UpcomingWorkloadValue",
    "ScheduleConflictRiskValue",
    "GoalProgressOutlookValue",
    "RoutineContinuityValue",
    "ForecastValue",
    "ForecastOut",
    "ForecastPage",
    "CalibrationMetricOut",
    "CalibrationReportOut",
]
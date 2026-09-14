from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SnapshotDataQuality = Literal["verified", "partial", "stale", "unavailable"]
ScopeType = Literal["USER", "COURSE", "TASK", "SOURCE", "SEMESTER"]
StateType = Literal[
    "observed_learning_activity",
    "task_workload",
    "deadline_exposure",
    "course_participation",
    "data_source_health",
    "academic_course_load",
    "grade_observation",
    "knowledge_mastery_observation",
    "credit_progress",
    "exam_exposure",
    "schedule_load",
    "goal_state",
    "workload_pressure",
    "schedule_conflict",
    "academic_progress",
    "focus_rhythm",
    "goal_progress",
    "execution_consistency",
    "growth_momentum",
    "preference_profile",
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


class AcademicCourseLoadValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_semester_course_count: int = Field(ge=0)
    effective_credit_load: float = Field(ge=0)
    data_completeness: SnapshotDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


class GradeObservationValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_grade_count: int = Field(ge=0)
    # 观测来源拆分: 教务成绩是权威来源，学习通作业得分是平台观测。
    edu_grade_count: int = Field(default=0, ge=0)
    platform_grade_count: int = Field(default=0, ge=0)
    score_band_distribution: dict[str, int] = Field(default_factory=dict)
    has_observed_grades: bool
    data_completeness: SnapshotDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


class CreditProgressValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_credits: float = Field(ge=0)
    current_semester_credits: float = Field(ge=0)
    total_required_credits: float | None = None
    data_completeness: SnapshotDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


class ExamExposureValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upcoming_exam_count: int = Field(ge=0)
    # 观测来源拆分: 教务考试安排 vs 学习通考试。
    edu_exam_count: int = Field(default=0, ge=0)
    platform_exam_count: int = Field(default=0, ge=0)
    time_bucket_distribution: dict[str, int] = Field(default_factory=dict)
    unknown_time_exam_count: int = Field(ge=0)
    data_completeness: SnapshotDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


class ScheduleLoadValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    future_7d_course_density: float = Field(ge=0)
    high_density_periods: list[str] = Field(default_factory=list, max_length=16)
    density_description: str = Field(default="observed", max_length=64)
    data_completeness: SnapshotDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


GoalSourceLabel = Literal["student_initiated", "system_suggested", "plan_accepted"]


class GoalStateValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_daily_goals: int = Field(ge=0)
    session_goals_summary: dict[str, int] = Field(default_factory=dict)
    accepted_plan_goals: int = Field(ge=0)
    source_labels: list[GoalSourceLabel] = Field(default_factory=list, max_length=16)
    data_completeness: SnapshotDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


WorkloadPressureBand = Literal["LOW", "MODERATE", "HIGH", "VERY_HIGH"]


class WorkloadPressureValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_days: int = Field(ge=1, le=30)
    task_count: int = Field(ge=0)
    exam_count: int = Field(ge=0)
    estimated_total_minutes: int = Field(ge=0)
    pressure_band: WorkloadPressureBand
    concentrated_dates: list[str] = Field(default_factory=list, max_length=16)
    data_completeness: SnapshotDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


class ScheduleConflictItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["overlap", "gap"]
    start: datetime
    end: datetime
    overlap_minutes: int = Field(ge=0)

    _aware_start = field_validator("start", "end")(_aware)


class ScheduleConflictValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflict_count: int = Field(ge=0)
    conflicts: list[ScheduleConflictItem] = Field(default_factory=list, max_length=16)
    available_window_count: int = Field(ge=0)
    data_completeness: SnapshotDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


class AcademicProgressValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_course_count: int = Field(ge=0)
    observed_credit_count: float = Field(ge=0)
    observed_passed_count: int = Field(ge=0)
    # 学习通作业得分贡献的补充观测(无学分信息，只有分数)。
    platform_grade_count: int = Field(default=0, ge=0)
    platform_average_score: float | None = None
    data_completeness: SnapshotDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


class KnowledgeMasteryObservationValue(BaseModel):
    """课程知识图谱观测 —— 知识点体系与掌握率(来自学习通课程图谱页)。

    与 C 时代被删除的"平台自造知识点推断"不同: 这里是课程/学校发布的
    知识点体系 + 平台统计的真实掌握率，属于外部数据源观测。
    """

    model_config = ConfigDict(extra="forbid")

    knowledge_point_count: int = Field(ge=0)
    own_mastery_rate: float | None = None
    class_mastery_rate: float | None = None
    # 与班级平均的差距(正数表示领先)，用于发现"个人强于班级"的科目。
    mastery_gap_vs_class: float | None = None
    own_completion_rate: float | None = None
    class_completion_rate: float | None = None
    data_completeness: SnapshotDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


FocusRhythmStability = Literal["stable", "variable", "unknown"]


class FocusRhythmValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_session_count: int = Field(ge=0)
    common_time_slots: list[str] = Field(default_factory=list, max_length=8)
    median_duration_minutes: int = Field(ge=0)
    rhythm_stability: FocusRhythmStability
    data_completeness: SnapshotDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


class GoalProgressValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_goal_count: int = Field(ge=0)
    archived_goal_count: int = Field(ge=0)
    goals_with_milestones: int = Field(ge=0)
    average_progress_percent: float = Field(ge=0, le=100)
    data_completeness: SnapshotDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


ExecutionConsistencyBand = Literal["none", "low", "moderate", "high", "no_plan"]


class ExecutionConsistencyValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planned_task_count: int = Field(ge=0)
    executed_task_count: int = Field(ge=0)
    consistency_ratio: float = Field(ge=0, le=1)
    consistency_band: ExecutionConsistencyBand
    data_completeness: SnapshotDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


GrowthMomentumBand = Literal["rising", "steady", "declining", "insufficient_data"]


class GrowthMomentumValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal_count: int = Field(ge=0)
    goals_with_recent_progress: int = Field(ge=0)
    momentum_band: GrowthMomentumBand
    data_completeness: SnapshotDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


PreferenceReminderFrequency = Literal["unset", "minimal", "normal", "frequent"]
PreferenceFocusSlot = Literal["unset", "morning", "afternoon", "evening", "night"]
PreferenceDetailLevel = Literal["unset", "brief", "standard", "detailed"]


class PreferenceProfileValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reminder_frequency: PreferenceReminderFrequency = "unset"
    quiet_hours_enabled: bool = False
    daily_plan_capacity_minutes: int = Field(default=0, ge=0, le=1440)
    preferred_focus_slot: PreferenceFocusSlot = "unset"
    detail_level: PreferenceDetailLevel = "unset"
    data_completeness: SnapshotDataQuality
    warning_codes: list[str] = Field(default_factory=list, max_length=16)


StateValue = Annotated[
    Union[
        ObservedLearningActivityValue,
        TaskWorkloadValue,
        DeadlineExposureValue,
        CourseParticipationValue,
        DataSourceHealthValue,
        AcademicCourseLoadValue,
        GradeObservationValue,
        CreditProgressValue,
        ExamExposureValue,
        ScheduleLoadValue,
        GoalStateValue,
        WorkloadPressureValue,
        ScheduleConflictValue,
        AcademicProgressValue,
        FocusRhythmValue,
        GoalProgressValue,
        ExecutionConsistencyValue,
        GrowthMomentumValue,
        PreferenceProfileValue,
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
    estimator_version: str = ""
    projection_kind: Literal["CORE", "ACADEMIC", "WORLD"] = "CORE"
    projection_scope: str = "__user__"
    input_digest: str = ""
    as_of: datetime | None = None
    warning_codes: list[str] = Field(default_factory=list, max_length=32)
    evidence_count: int = Field(default=0, ge=0)

    _aware_times = field_validator(
        "observed_from", "observed_through", "valid_until", "computed_at", "as_of"
    )(_aware)

    @model_validator(mode="after")
    def validate_value_for_state(self) -> "LearnerStateSnapshotOut":
        expected = {
            "observed_learning_activity": ObservedLearningActivityValue,
            "task_workload": TaskWorkloadValue,
            "deadline_exposure": DeadlineExposureValue,
            "course_participation": CourseParticipationValue,
            "data_source_health": DataSourceHealthValue,
            "academic_course_load": AcademicCourseLoadValue,
            "grade_observation": GradeObservationValue,
            "knowledge_mastery_observation": KnowledgeMasteryObservationValue,
            "credit_progress": CreditProgressValue,
            "exam_exposure": ExamExposureValue,
            "schedule_load": ScheduleLoadValue,
            "goal_state": GoalStateValue,
            "workload_pressure": WorkloadPressureValue,
            "schedule_conflict": ScheduleConflictValue,
            "academic_progress": AcademicProgressValue,
            "focus_rhythm": FocusRhythmValue,
            "goal_progress": GoalProgressValue,
            "execution_consistency": ExecutionConsistencyValue,
            "growth_momentum": GrowthMomentumValue,
            "preference_profile": PreferenceProfileValue,
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
        "study_session", "personal_task", "course_content", "course_sync",
        "core_learning_record", "chaoxing", "edu_schedule", "edu_grade", "edu_exam",
        "self_report", "ai_learning_feedback", "unknown"
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
        "orphan_assignment_submitted", "platform_event_observed", "state_observed",
        "edu_schedule_observed", "edu_grade_observed", "edu_exam_observed",
        "academic_data_unavailable", "goal_student_initiated", "goal_system_suggested",
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
    projection_kind: Literal["CORE", "ACADEMIC", "WORLD"] = "CORE"
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
            "academic_course_load": AcademicCourseLoadValue,
            "grade_observation": GradeObservationValue,
            "knowledge_mastery_observation": KnowledgeMasteryObservationValue,
            "credit_progress": CreditProgressValue,
            "exam_exposure": ExamExposureValue,
            "schedule_load": ScheduleLoadValue,
            "goal_state": GoalStateValue,
            "workload_pressure": WorkloadPressureValue,
            "schedule_conflict": ScheduleConflictValue,
            "academic_progress": AcademicProgressValue,
            "focus_rhythm": FocusRhythmValue,
            "goal_progress": GoalProgressValue,
            "execution_consistency": ExecutionConsistencyValue,
            "growth_momentum": GrowthMomentumValue,
            "preference_profile": PreferenceProfileValue,
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
    "AcademicCourseLoadValue",
    "AcademicProgressValue",
    "CourseParticipationValue",
    "CreditProgressValue",
    "DataSourceHealthValue",
    "DeadlineExposureValue",
    "ExamExposureValue",
    "ExecutionConsistencyValue",
    "FocusRhythmValue",
    "GoalProgressValue",
    "GoalStateValue",
    "GradeObservationValue",
    "GrowthMomentumValue",
    "LearnerStateEvidenceOut",
    "LearnerStateEvidencePage",
    "LearnerStateChangeOut",
    "LearnerStateChangePage",
    "LearnerStateRunOut",
    "LearnerStateRunPage",
    "LearnerStateSnapshotOut",
    "LearnerStateSnapshotPage",
    "ObservedLearningActivityValue",
    "PreferenceProfileValue",
    "ScheduleConflictValue",
    "ScheduleLoadValue",
    "SnapshotDataQuality",
    "TaskWorkloadValue",
    "WorkloadPressureValue",
]

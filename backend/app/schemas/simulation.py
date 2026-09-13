"""反事实方案模拟 schema — 只读地比较校园行动方案的影响。

模拟是"方案估计，不是因果保证"。
完全只读：不创建任务、不修改目标、不执行计划、不暂停真实数据源。
intervention 通过 Pydantic discriminated union 和白名单受控，客户端无法注入任意工具名或参数。
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

SimulationDataQuality = Literal["verified", "partial", "stale", "unavailable"]

InterventionType = Literal[
    "ALLOCATE_FOCUS_MINUTES",
    "RESCHEDULE_TASK",
    "ACCEPT_PLAN",
    "REDUCE_DAILY_LOAD",
    "PAUSE_DATA_SOURCE",
    "ADJUST_GOAL_DEADLINE",
]

DataSourceCategory = Literal["academic", "chaoxing", "notice", "study_session", "manual"]

SimulationLimitationCode = Literal[
    "baseline_estimator_only",
    "no_causal_claim",
    "correlation_not_causation",
    "counterfactual_estimate_not_cause",
    "single_user_scope",
    "no_psychological_inference",
    "no_dropout_prediction",
    "no_employment_prediction",
    "no_personality_prediction",
    "synthetic_calibration_only",
    "not_measured_against_real_outcomes",
    "intervention_not_executed",
    "missing_baseline_data",
    "plan_not_simulatable",
    "plan_expired",
    "no_movable_tasks",
    "simulation_no_change",
]

SimulationAssumptionCode = Literal[
    "intervention_applied_in_memory_only",
    "baseline_state_unchanged",
    "linear_local_response",
    "no_second_order_effects",
    "plan_acceptance_assumed",
    "source_pause_assumed",
]


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("datetime must carry timezone")
    return value


class AllocateFocusMinutesIntervention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intervention_type: Literal["ALLOCATE_FOCUS_MINUTES"] = "ALLOCATE_FOCUS_MINUTES"
    focus_minutes: int = Field(ge=0, le=480)
    target_date: datetime | None = Field(default=None)

    _aware_target = field_validator("target_date")(_aware)


class RescheduleTaskIntervention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intervention_type: Literal["RESCHEDULE_TASK"] = "RESCHEDULE_TASK"
    task_id: str = Field(min_length=1, max_length=128)
    new_deadline: datetime

    _aware_deadline = field_validator("new_deadline")(_aware)


class AcceptPlanIntervention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intervention_type: Literal["ACCEPT_PLAN"] = "ACCEPT_PLAN"
    plan_id: str = Field(min_length=1, max_length=128)


class ReduceDailyLoadIntervention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intervention_type: Literal["REDUCE_DAILY_LOAD"] = "REDUCE_DAILY_LOAD"
    reduce_minutes_per_day: int = Field(ge=0, le=480)
    target_date: datetime | None = Field(default=None)
    movable_task_policy: Literal["PERSONAL_ONLY"] = "PERSONAL_ONLY"

    _aware_target = field_validator("target_date")(_aware)


class PauseDataSourceIntervention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intervention_type: Literal["PAUSE_DATA_SOURCE"] = "PAUSE_DATA_SOURCE"
    source_category: DataSourceCategory


class AdjustGoalDeadlineIntervention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intervention_type: Literal["ADJUST_GOAL_DEADLINE"] = "ADJUST_GOAL_DEADLINE"
    goal_id: str = Field(min_length=1, max_length=128)
    new_target_date: datetime

    _aware_target = field_validator("new_target_date")(_aware)


Intervention = Annotated[
    Union[
        AllocateFocusMinutesIntervention,
        RescheduleTaskIntervention,
        AcceptPlanIntervention,
        ReduceDailyLoadIntervention,
        PauseDataSourceIntervention,
        AdjustGoalDeadlineIntervention,
    ],
    Field(discriminator="intervention_type"),
]


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_run_id: str | None = Field(default=None, min_length=1, max_length=128)
    intervention: Intervention
    horizon_days: int = Field(default=7, ge=1, le=30)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class ChangedForecastSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    forecast_type: str
    scope_type: str
    scope_id: str
    baseline_probability: float | None = Field(default=None, ge=0, le=1)
    intervention_probability: float | None = Field(default=None, ge=0, le=1)
    baseline_risk_band: str | None = None
    intervention_risk_band: str | None = None
    baseline_value: dict[str, Any] | None = None
    intervention_value: dict[str, Any] | None = None
    delta: dict[str, float] = Field(default_factory=dict, max_length=16)
    direction: Literal["increased", "decreased", "unchanged", "unknown"]
    magnitude: float = Field(default=0.0, ge=-1, le=1)
    explanation_codes: list[str] = Field(default_factory=list, max_length=16)


class ChangedStateEstimateSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_type: str
    scope_type: str
    scope_id: str
    change_type: Literal["updated", "added", "removed", "degraded"]
    baseline_value: dict[str, Any] | None = None
    intervention_value: dict[str, Any] | None = None
    baseline_data_quality: SimulationDataQuality | None = None
    intervention_data_quality: SimulationDataQuality | None = None
    explanation_codes: list[str] = Field(default_factory=list, max_length=16)


class UnchangedStateSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_type: str
    scope_type: str
    scope_id: str
    data_quality: SimulationDataQuality


class SimulationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    simulation_id: str
    baseline_digest: str
    intervention: Intervention
    changed_forecasts: list[ChangedForecastSummary] = Field(default_factory=list, max_length=32)
    changed_state_estimates: list[ChangedStateEstimateSummary] = Field(default_factory=list, max_length=64)
    unchanged_states: list[UnchangedStateSummary] = Field(default_factory=list, max_length=128)
    assumptions: list[SimulationAssumptionCode] = Field(default_factory=list, max_length=16)
    limitations: list[SimulationLimitationCode] = Field(default_factory=list, max_length=16)
    confidence: float = Field(ge=0, le=1)
    data_quality: SimulationDataQuality
    estimator_version: str
    expires_at: datetime
    causal_claim: Literal[False] = False

    _aware_expires = field_validator("expires_at")(_aware)


__all__ = [
    "SimulationDataQuality",
    "InterventionType",
    "DataSourceCategory",
    "SimulationLimitationCode",
    "SimulationAssumptionCode",
    "AllocateFocusMinutesIntervention",
    "RescheduleTaskIntervention",
    "AcceptPlanIntervention",
    "ReduceDailyLoadIntervention",
    "PauseDataSourceIntervention",
    "AdjustGoalDeadlineIntervention",
    "Intervention",
    "SimulationRequest",
    "SimulationResponse",
    "ChangedForecastSummary",
    "ChangedStateEstimateSummary",
    "UnchangedStateSummary",
]

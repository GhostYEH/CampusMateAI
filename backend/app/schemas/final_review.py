from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CampaignCreate(Strict):
    exam_id: str = Field(min_length=1, max_length=128)
    daily_capacity_minutes: int = Field(default=90, ge=15, le=480)


class CampaignOut(Strict):
    campaign_id: str
    exam_id: str
    status: str
    active_version: int | None
    daily_capacity_minutes: int
    created_at: str
    updated_at: str
    # 运行关联（可选）：仅有 Runtime 运行存在时才有值，旧客户端可忽略。
    job_id: str | None = None
    run_id: str | None = None
    run_status: str | None = None
    run_phase: str | None = None
    pending_approval_id: str | None = None


class PlanVersionOut(Strict):
    plan_version_id: str
    campaign_id: str
    version: int
    parent_version_id: str | None
    content: dict
    content_hash: str
    change_reason: str
    created_at: str
    job_id: str | None = None
    run_id: str | None = None
    approval_id: str | None = None


class RuntimeStepOut(Strict):
    step_id: str
    sequence: int
    role: str
    status: str
    summary: str
    started_at: str | None = None
    finished_at: str | None = None


class CampaignRunOut(Strict):
    campaign_id: str
    job_id: str | None = None
    run_id: str | None = None
    status: str | None = None
    phase: str | None = None
    progress_current: int = 0
    progress_total: int = 0
    approval_id: str | None = None
    approval_status: str | None = None
    approval_summary: str | None = None
    approval_expires_at: str | None = None
    approval_decided_at: str | None = None
    steps: list[RuntimeStepOut] = []


class DailyItemOut(Strict):
    item_id: str
    title: str
    duration_minutes: int
    status: str
    external_task_id: str | None


class DailyAgendaOut(Strict):
    agenda_id: str
    campaign_id: str
    plan_version: int
    agenda_date: str
    items: list[DailyItemOut]


class DailyCheckinCreate(Strict):
    completion_percent: int = Field(ge=0, le=100)
    actual_minutes: int = Field(ge=0, le=1440)
    difficulty_code: str | None = Field(default=None, max_length=64)


class AdjustmentDecision(Strict):
    decision: str = Field(pattern=r"^(APPROVED|REJECTED)$")

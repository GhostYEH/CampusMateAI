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


class PlanVersionOut(Strict):
    plan_version_id: str
    campaign_id: str
    version: int
    parent_version_id: str | None
    content: dict
    content_hash: str
    change_reason: str
    created_at: str


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

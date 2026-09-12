"""期末复习 Pydantic 契约模型。

所有模型使用 `extra="forbid"` 防止隐藏字段泄漏。
对应 §9.3 final-review 端点。
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .agent_contract_enums import RiskLevel


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ===== Campaign =====


class FinalReviewCampaignIn(_StrictModel):
    """创建 campaign 请求。exam_ids 只接受 server /student/exams 返回的字符串。"""

    exam_ids: list[str] = Field(..., min_length=1, max_length=20)
    daily_capacity_minutes: int = Field(..., ge=15, le=600)
    preferred_periods: list[str] = Field(default_factory=list, max_length=10)
    rest_days: list[str] = Field(default_factory=list, max_length=7)
    intensity: str = Field("medium", pattern="^(low|medium|high)$")
    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


class FinalReviewCampaignOut(_StrictModel):
    campaign_id: str
    user_id: str
    exam_ids: list[str]
    daily_capacity_minutes: int
    preferred_periods: list[str]
    rest_days: list[str]
    intensity: str
    status: str
    active_version: Optional[int] = None
    created_at: str
    updated_at: str


# ===== Plan generate =====


class PlanGenerateIn(_StrictModel):
    """生成计划请求。可选编辑偏好。"""

    user_edits: Optional[dict[str, Any]] = None
    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


class PlanVersionOut(_StrictModel):
    campaign_id: str
    version: int
    plan: dict[str, Any]
    source_snapshot_id: Optional[str] = None
    model_provider: str
    route_policy: str
    risk_level: str
    approval_id: Optional[str] = None
    supersedes_version: Optional[int] = None
    created_at: str


class PlanGenerateOut(_StrictModel):
    """生成计划结果。可能需要审批。"""

    run_id: str
    version: int
    plan: dict[str, Any]
    risk_level: str
    requires_approval: bool
    approval_id: Optional[str] = None


# ===== Activate =====


class ActivateIn(_StrictModel):
    version: int = Field(..., ge=1)
    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


class ActivateOut(_StrictModel):
    campaign_id: str
    active_version: int
    activated: bool


# ===== Daily agenda =====


class DailyItemOut(_StrictModel):
    item_id: str
    title: str
    course_name: Optional[str] = None
    scheduled_minutes: int
    sort_order: int
    status: str
    personal_task_id: Optional[str] = None
    difficulty: Optional[str] = None


class DailyAgendaOut(_StrictModel):
    agenda_id: str
    campaign_id: str
    plan_version: int
    agenda_date: str
    total_minutes: int
    items: list[DailyItemOut]


class CompleteItemIn(_StrictModel):
    difficulty: Optional[str] = Field(None, pattern="^(easy|medium|hard)$")
    feedback: Optional[str] = Field(None, max_length=500)
    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


class CompleteItemOut(_StrictModel):
    item_id: str
    status: str
    completed_at: str


# ===== Daily check-in =====


class DailyCheckinIn(_StrictModel):
    """每日签到/晚间反馈。"""

    report_date: str = Field(..., min_length=1, max_length=32)
    completed_item_ids: list[str] = Field(default_factory=list)
    insufficient_time: bool = False
    difficulty_notes: Optional[str] = Field(None, max_length=500)
    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


class DailyCheckinOut(_StrictModel):
    recorded: bool
    evidence_count: int


# ===== Adjustment =====


class AdjustmentAnalyzeIn(_StrictModel):
    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


class AdjustmentProposalOut(_StrictModel):
    proposal_id: str
    campaign_id: str
    source_version: int
    proposal: dict[str, Any]
    risk_level: str
    status: str
    approval_id: Optional[str] = None
    target_version: Optional[int] = None
    reason: Optional[str] = None
    created_at: str


class AdjustmentAnalyzeOut(_StrictModel):
    """Analyzer 结果。只产生 proposal,不直接改 active plan。"""

    run_id: str
    proposal_id: str
    risk_level: str
    requires_approval: bool
    approval_id: Optional[str] = None


class AdjustmentDecisionIn(_StrictModel):
    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    reason: Optional[str] = Field(None, max_length=256)
    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


class AdjustmentDecisionOut(_StrictModel):
    """审批决策结果。APPROVED 时创建新版本。"""

    proposal_id: str
    status: str
    new_version: Optional[int] = None
    active_version: Optional[int] = None


__all__ = [
    "ActivateIn",
    "ActivateOut",
    "AdjustmentAnalyzeIn",
    "AdjustmentAnalyzeOut",
    "AdjustmentDecisionIn",
    "AdjustmentDecisionOut",
    "AdjustmentProposalOut",
    "CompleteItemIn",
    "CompleteItemOut",
    "DailyAgendaOut",
    "DailyCheckinIn",
    "DailyCheckinOut",
    "DailyItemOut",
    "FinalReviewCampaignIn",
    "FinalReviewCampaignOut",
    "PlanGenerateIn",
    "PlanGenerateOut",
    "PlanVersionOut",
]
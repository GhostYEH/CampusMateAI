"""期末复习数据行模型(纯数据容器,无 ORM)。

对应 §7.2 五张表:
- final_review_campaigns
- final_review_plan_versions(不可变)
- final_review_daily_agendas
- final_review_daily_items
- final_review_adjustment_proposals

Plan versions 不可变:应用 adjustment 创建新版本而非覆盖旧版本。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FinalReviewCampaignRow:
    """final_review_campaigns 行。"""

    campaign_id: str
    user_id: str
    exam_ids_json: str  # JSON 数组字符串,只接受 server /student/exams 返回的 exam_id
    daily_capacity_minutes: int
    preferred_periods_json: str  # JSON 数组
    rest_days_json: str  # JSON 数组
    intensity: str  # low / medium / high
    status: str  # draft / active / archived / cancelled
    active_version: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""
    idempotency_key: Optional[str] = None


@dataclass
class FinalReviewPlanVersionRow:
    """final_review_plan_versions 行(不可变)。

    `plan_json` 包含完整计划结构(daily schedule、items、load)。
    `source_snapshot_id` 引用 agent_context_snapshots。
    `supersedes_version` 指向被替代的版本(adjustment 应用后)。
    """

    campaign_id: str
    version: int
    user_id: str
    plan_json: str
    source_snapshot_id: Optional[str]
    model_provider: str
    route_policy: str
    risk_level: str
    approval_id: Optional[str] = None
    supersedes_version: Optional[int] = None
    created_at: str = ""


@dataclass
class FinalReviewDailyAgendaRow:
    """final_review_daily_agendas 行。"""

    agenda_id: str
    campaign_id: str
    plan_version: int
    user_id: str
    agenda_date: str  # ISO date
    total_minutes: int = 0
    created_at: str = ""


@dataclass
class FinalReviewDailyItemRow:
    """final_review_daily_items 行。"""

    item_id: str
    agenda_id: str
    campaign_id: str
    user_id: str
    title: str
    course_name: Optional[str] = None
    scheduled_minutes: int = 0
    sort_order: int = 0
    status: str = "pending"  # pending / completed / skipped
    personal_task_id: Optional[str] = None  # 物化的 personal_tasks.id
    completed_at: Optional[str] = None
    difficulty: Optional[str] = None  # easy / medium / hard
    feedback: Optional[str] = None


@dataclass
class FinalReviewAdjustmentProposalRow:
    """final_review_adjustment_proposals 行。

    Analyzer 只产生 proposal,不直接修改 active plan。
    `proposal_json` 包含调整建议(新增/移动/删除任务、负荷变化)。
    `risk_level` 由 RiskEngine 评定。
    `status`: pending / approved / rejected / expired。
    `target_version` 为应用后创建的新版本号。
    """

    proposal_id: str
    campaign_id: str
    user_id: str
    source_version: int
    proposal_json: str
    risk_level: str  # AUTO_SAFE / CONFIRM_REQUIRED / MANUAL_ONLY
    status: str = "pending"  # pending / approved / rejected / expired
    approval_id: Optional[str] = None
    target_version: Optional[int] = None
    model_provider: Optional[str] = None
    route_policy: Optional[str] = None
    reason: Optional[str] = None
    created_at: str = ""
    resolved_at: Optional[str] = None


__all__ = [
    "FinalReviewCampaignRow",
    "FinalReviewPlanVersionRow",
    "FinalReviewDailyAgendaRow",
    "FinalReviewDailyItemRow",
    "FinalReviewAdjustmentProposalRow",
]
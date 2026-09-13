"""Phase 6A: 学生世界模型控制 API 的 Pydantic 契约。

涵盖状态纠正、数据源控制、世界模型删除和安全导出摘要。
所有输出严格排除内部表名、source_id、任务正文、课程材料正文、
对话原文、模型 Prompt、凭据和原始异常信息。
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ===== 状态纠正 =====

CorrectionType = Literal[
    "MARK_INACCURATE",
    "NOT_APPLICABLE",
    "SOURCE_OUTDATED",
    "ALREADY_RESOLVED",
    "REQUEST_RECOMPUTE",
]

ReasonCode = Literal[
    "TASK_ALREADY_COMPLETED",
    "DEADLINE_CHANGED",
    "COURSE_NO_LONGER_ACTIVE",
    "KNOWLEDGE_ESTIMATE_TOO_HIGH",
    "KNOWLEDGE_ESTIMATE_TOO_LOW",
    "EVIDENCE_NOT_RELEVANT",
    "SOURCE_DATA_STALE",
    "OTHER_CONTROLLED_REASON",
]

ProjectionKind = Literal["CORE", "KNOWLEDGE"]
ScopeType = Literal["USER", "COURSE", "TASK", "SOURCE", "KNOWLEDGE_COMPONENT"]
StateType = Literal[
    "observed_learning_activity",
    "task_workload",
    "deadline_exposure",
    "course_participation",
    "data_source_health",
    "academic_course_load",
    "grade_observation",
    "credit_progress",
    "exam_exposure",
    "schedule_load",
    "goal_state",
]
CorrectionStatus = Literal["ACTIVE", "REVOKED"]


class CorrectionCreate(BaseModel):
    projection_kind: ProjectionKind = Field(..., description="投影类型")
    projection_scope: str = Field(..., min_length=1, max_length=128, description="投影范围标识")
    scope_type: ScopeType = Field(..., description="快照 scope 类型")
    scope_id: str = Field(..., min_length=1, max_length=128, description="快照 scope 标识")
    state_type: StateType = Field(..., description="被纠正的状态类型")
    target_snapshot_id: str = Field(..., min_length=1, max_length=128, description="目标快照 ID")
    correction_type: CorrectionType = Field(..., description="纠正类型")
    reason_code: ReasonCode = Field(..., description="纠正原因码")
    idempotency_key: str = Field(..., min_length=1, max_length=128, description="幂等键")


class CorrectionOut(BaseModel):
    correction_id: str
    projection_kind: ProjectionKind
    projection_scope: str
    scope_type: ScopeType
    scope_id: str
    state_type: StateType
    target_snapshot_id: str
    correction_type: CorrectionType
    reason_code: ReasonCode
    status: CorrectionStatus
    created_at: datetime
    revoked_at: Optional[datetime] = None
    correction_version: int


class CorrectionPage(BaseModel):
    items: list[CorrectionOut]
    total: int
    page: int
    page_size: int
    has_more: bool


class CorrectionRevokeRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=128, description="幂等键")


# ===== 数据源控制 =====

SourceKey = Literal[
    "CORE_STUDY",
    "PERSONAL_TASK",
    "CHAOXING",
    "EDU",
    "PRACTICE",
    "MODEL_SHADOW",
    "PROACTIVE_SUGGESTIONS",
]

SourceStatus = Literal["ENABLED", "PAUSED", "DISCONNECTED", "DELETE_REQUESTED"]


class DataSourceControlOut(BaseModel):
    source_key: SourceKey
    status: SourceStatus
    updated_at: datetime
    can_pause: bool = True
    can_resume: bool = True


class DataSourceControlList(BaseModel):
    items: list[DataSourceControlOut]


class DataSourceControlUpdate(BaseModel):
    status: Literal["ENABLED", "PAUSED"] = Field(..., description="新状态")
    idempotency_key: str = Field(..., min_length=1, max_length=128, description="幂等键")


# ===== 世界模型删除 =====

DeleteScope = Literal[
    "STATE_ONLY",
    "EVENTS_AND_STATE",
    "KNOWLEDGE_ONLY",
    "PLANS_ONLY",
    "MODEL_SHADOW_ONLY",
    "ALL_LEARNER_MODEL_DATA",
]


class DeleteRequestCreate(BaseModel):
    scope: DeleteScope = Field(..., description="删除范围")
    idempotency_key: str = Field(..., min_length=1, max_length=128, description="幂等键")


class DeleteCountSummary(BaseModel):
    """表意类别计数，不暴露内部表名。"""
    projection_runs: int = 0
    snapshots: int = 0
    evidence: int = 0
    learner_events: int = 0
    knowledge_snapshots: int = 0
    misconceptions: int = 0
    corrections: int = 0
    learning_plans: int = 0
    plan_items: int = 0
    plan_feedback: int = 0
    plan_evaluations: int = 0
    shadow_runs: int = 0



class DeleteRequestOut(BaseModel):
    request_id: str
    scope: DeleteScope
    status: Literal["COMPLETED", "IN_PROGRESS", "FAILED"]
    before_counts: DeleteCountSummary
    after_counts: DeleteCountSummary
    created_at: datetime
    completed_at: Optional[datetime] = None


class DeleteStatusOut(BaseModel):
    latest: Optional[DeleteRequestOut] = None
    history: list[DeleteRequestOut] = []


# ===== 安全导出摘要 =====

class DataSummaryOut(BaseModel):
    event_count: int
    snapshot_count: int
    knowledge_snapshot_count: int
    misconception_count: int
    correction_count: int
    learning_plan_count: int
    plan_feedback_count: int
    plan_evaluation_count: int
    shadow_run_count: int
    enabled_sources: list[SourceKey]
    paused_sources: list[SourceKey]
    oldest_recorded_at: Optional[datetime] = None
    newest_recorded_at: Optional[datetime] = None
    estimator_versions: list[str]
    planner_versions: list[str]
    evaluator_versions: list[str]


# ===== 模型透明度 =====

class ModelCapabilityTransparencyOut(BaseModel):
    capability_name: str
    capability_version: str
    production_method: str
    campusmate_lm_status: Literal[
        "SHADOW_ONLY",
        "BLOCKED",
        "ELIGIBLE_FOR_CANARY",
        "REVOKED",
    ]
    quality_gate_passed: bool
    performance_gate_passed: bool
    performance_measured: bool
    last_evaluated_at: Optional[datetime] = None
    uses_real_model_inference: bool
    uses_fixed_prediction_file: bool


class ModelTransparencyOut(BaseModel):
    capabilities: list[ModelCapabilityTransparencyOut]
    campusmate_lm_enabled: bool
    campusmate_lm_affects_production: bool = False
    shadow_results_modify_plans: bool = False
    read_only_canary_active: bool = False
    uses_real_model_inference: bool = False
    uses_fixed_prediction_file: bool = True
    real_inference_observed: bool = False
    last_real_inference_at: Optional[datetime] = None
    fixture_only: bool = False


__all__ = [
    "CorrectionCreate",
    "CorrectionOut",
    "CorrectionPage",
    "CorrectionRevokeRequest",
    "DataSourceControlOut",
    "DataSourceControlList",
    "DataSourceControlUpdate",
    "DeleteRequestCreate",
    "DeleteCountSummary",
    "DeleteRequestOut",
    "DeleteStatusOut",
    "DataSummaryOut",
    "ModelCapabilityTransparencyOut",
    "ModelTransparencyOut",
]
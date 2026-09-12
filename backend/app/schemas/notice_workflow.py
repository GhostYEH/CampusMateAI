"""通知工作流 Pydantic 契约模型(§7.3、§8.3、§9.4)。

所有模型使用 `extra="forbid"` 防止隐藏字段泄漏。
敏感字段(凭据、完整表单内容)绝不进入响应。
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .agent_contract_enums import RiskLevel


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ===== 枚举(字符串字面量,冻结) =====

WORKFLOW_STATUSES = (
    "CREATED",
    "ANALYZING",
    "WAITING_CONFIRMATION",
    "PROCESSING",
    "COMPLETED",
    "EXPIRED",
    "FAILED",
)
ACTION_STATUSES = (
    "PROPOSED",
    "APPROVED",
    "REJECTED",
    "EXECUTING",
    "DONE",
    "FAILED",
    "EXPIRED",
)
SOURCE_KINDS = (
    "MANUAL",
    "EMAIL",
    "OFFICIAL_ACCOUNT",
    "LEARNING_PLATFORM",
    "SYSTEM",
)
# 服务端拥有的来源代码(§7.3)
SOURCE_CODES = (
    "android_system",
    "chaoxing",
    "campus_announcement",
    "manual_input",
)


# ===== 来源 =====


class NotificationSourceOut(_StrictModel):
    source_id: str = Field(..., min_length=1, max_length=64)
    code: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., max_length=128)
    kind: str = Field(..., max_length=32)
    automation_enabled: bool = False
    permission_scope: Optional[str] = Field(None, max_length=256)


class NotificationSourcePatchIn(_StrictModel):
    automation_enabled: Optional[bool] = None
    display_name: Optional[str] = Field(None, max_length=128)


# ===== 解释结果 =====


class NoticeInterpretationOut(_StrictModel):
    """Interpreter 输出。`uncertainty` 列出无法可靠抽取的字段。"""

    title: Optional[str] = Field(None, max_length=256)
    deadline: Optional[str] = Field(None, max_length=64)
    location: Optional[str] = Field(None, max_length=256)
    audience: Optional[str] = Field(None, max_length=256)
    materials: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    source_evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    uncertainty: list[str] = Field(default_factory=list)
    extractor_mode: str = Field(..., max_length=32)


# ===== 工作流 =====


class WorkflowCreateIn(_StrictModel):
    """POST /notices/{notice_id}/workflow 请求体。"""

    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


class WorkflowStepOut(_StrictModel):
    step: str = Field(..., max_length=512)
    done: bool = False


class WorkflowActionOut(_StrictModel):
    action_id: str = Field(..., min_length=1, max_length=64)
    workflow_id: str = Field(..., min_length=1, max_length=64)
    action_type: str = Field(..., max_length=64)
    title: str = Field(..., max_length=256)
    risk_level: RiskLevel
    status: str = Field(..., max_length=16)
    external_ref: Optional[str] = Field(None, max_length=128)
    expires_at: Optional[str] = Field(None, max_length=64)
    error_code: Optional[str] = Field(None, max_length=64)
    error_message: Optional[str] = Field(None, max_length=256)
    created_at: str = Field(..., min_length=1, max_length=64)
    updated_at: str = Field(..., min_length=1, max_length=64)


class WorkflowOut(_StrictModel):
    workflow_id: str = Field(..., min_length=1, max_length=64)
    user_id: str = Field(..., min_length=1, max_length=64)
    notice_id: str = Field(..., min_length=1, max_length=64)
    source_id: Optional[str] = Field(None, max_length=64)
    status: str = Field(..., max_length=24)
    title: Optional[str] = Field(None, max_length=256)
    deadline: Optional[str] = Field(None, max_length=64)
    location: Optional[str] = Field(None, max_length=256)
    audience: Optional[str] = Field(None, max_length=256)
    materials: list[str] = Field(default_factory=list)
    steps: list[WorkflowStepOut] = Field(default_factory=list)
    source_evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    uncertainty: list[str] = Field(default_factory=list)
    error_code: Optional[str] = Field(None, max_length=64)
    error_message: Optional[str] = Field(None, max_length=256)
    created_at: str = Field(..., min_length=1, max_length=64)
    updated_at: str = Field(..., min_length=1, max_length=64)
    actions: list[WorkflowActionOut] = Field(default_factory=list)


class WorkflowReanalyzeIn(_StrictModel):
    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


# ===== Action 决策与执行 =====


class ActionDecisionIn(_StrictModel):
    """POST /notice-workflow-actions/{action_id}/decision。"""

    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    reason: Optional[str] = Field(None, max_length=256)
    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


class ActionExecuteIn(_StrictModel):
    """POST /notice-workflow-actions/{action_id}/execute。"""

    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


class ActionResultOut(_StrictModel):
    action_id: str = Field(..., min_length=1, max_length=64)
    status: str = Field(..., max_length=16)
    external_ref: Optional[str] = Field(None, max_length=128)
    result: Optional[dict[str, Any]] = None
    error_code: Optional[str] = Field(None, max_length=64)
    error_message: Optional[str] = Field(None, max_length=256)


# ===== 手动通知(返回服务端 notice_id) =====


class ManualNoticeIn(_StrictModel):
    """POST /notices/manual — 粘贴文本持久化为服务端 notice_id。"""

    title: str = Field(..., min_length=1, max_length=256)
    content: str = Field(..., min_length=1, max_length=5000)
    source_name: Optional[str] = Field(None, max_length=64)
    idempotency_key: Optional[str] = Field(None, min_length=1, max_length=128)


class ManualNoticeOut(_StrictModel):
    notice_id: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., max_length=256)
    duplicate: bool = False


__all__ = [
    "ACTION_STATUSES",
    "ActionDecisionIn",
    "ActionExecuteIn",
    "ActionResultOut",
    "ManualNoticeIn",
    "ManualNoticeOut",
    "NotificationSourceOut",
    "NotificationSourcePatchIn",
    "NoticeInterpretationOut",
    "SOURCE_CODES",
    "SOURCE_KINDS",
    "WorkflowActionOut",
    "WorkflowCreateIn",
    "WorkflowOut",
    "WorkflowReanalyzeIn",
    "WorkflowStepOut",
    "WORKFLOW_STATUSES",
]